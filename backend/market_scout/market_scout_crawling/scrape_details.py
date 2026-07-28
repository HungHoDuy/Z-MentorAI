import json
import os
import sys
import time
import threading
import argparse
from datetime import datetime, timezone
from queue import Queue, Empty
from tqdm import tqdm
from google.cloud import firestore

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from crawl_jobs.crawler import CareerVietCrawler
except ModuleNotFoundError:
    from crawler import CareerVietCrawler


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape CareerViet job details from Firestore todo links.")
    parser.add_argument("--todo-collection", default="todo_careerviet")
    parser.add_argument("--dest-collection", default="careerviet_jobs")
    parser.add_argument("--batch-id", default=None, help="Only scrape todo docs from this weekly batch id.")
    parser.add_argument("--scope", default=None, help="Only scrape todo docs with this scope value.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of remaining jobs to scrape.")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--allow-empty", action="store_true", help="Exit 0 even if no details are written.")
    return parser.parse_args()

def main():
    args = parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # Suppress verbose third-party logging
    import logging
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
    for name in ["selenium", "urllib3", "webdriver_manager", "wdm", "google"]:
        logging.getLogger(name).setLevel(logging.WARNING)


    # 1. Initialize Firestore client
    try:
        db = firestore.Client()
        src_collection_name = args.todo_collection
        dest_collection_name = args.dest_collection
    except Exception as e:
        print(f"Error initializing Firestore client: {e}")
        raise SystemExit(1) from e

    # 2. Load todo list from Firestore
    print(f"Loading todo list from Firestore '{src_collection_name}'...")
    try:
        todo_query = db.collection(src_collection_name)
        if args.batch_id:
            todo_query = todo_query.where("batch_id", "==", args.batch_id)
        elif args.scope:
            todo_query = todo_query.where("scope", "==", args.scope)
        todo_docs = todo_query.stream()
        todo_list = []
        for doc in todo_docs:
            data = doc.to_dict()
            if args.scope and args.batch_id and data.get("scope") != args.scope:
                continue
            if "job_id" in data and "href" in data:
                todo_list.append({
                    "job_id": data["job_id"],
                    "title": data.get("title", f"Job {data['job_id']}"),
                    "href": data["href"],
                    "scope": data.get("scope"),
                    "batch_id": data.get("batch_id") or args.batch_id,
                })
        print(f"Loaded {len(todo_list)} total jobs to crawl from Firestore.")
    except Exception as e:
        print(f"Error reading todo list from Firestore: {e}")
        raise SystemExit(1) from e

    if not todo_list:
        print(f"No jobs found to crawl in Firestore collection {src_collection_name!r}.")
        if args.allow_empty:
            return
        raise SystemExit(2)

    # 3. Load already scraped jobs from Firestore to support resume
    scraped_ids = set()
    print(f"Fetching already crawled job IDs from Firestore '{dest_collection_name}'...")
    try:
        scraped_docs = db.collection(dest_collection_name).select([]).stream()
        scraped_ids = {doc.id for doc in scraped_docs}
        print(f"Found {len(scraped_ids)} already crawled jobs in Firestore. Resuming from last attempt...")
    except Exception as e:
        print(f"Error reading existing jobs from Firestore: {e}. Starting fresh.")

    # 4. Filter remaining jobs
    remaining_jobs = [job for job in todo_list if job["job_id"] not in scraped_ids]
    if args.limit is not None:
        remaining_jobs = remaining_jobs[: args.limit]
    print(f"Remaining jobs to crawl: {len(remaining_jobs)}")
    
    if not remaining_jobs:
        print("All jobs from todo list have already been crawled!")
        return

    # 5. Threading variables
    file_lock = threading.Lock()
    job_queue = Queue()
    for job in remaining_jobs:
        job_queue.put(job)
        
    stop_workers = False
    saved_detail_count = 0
    
    # 6. Initialize tqdm progress bar
    pbar = tqdm(total=len(remaining_jobs), desc="Scraping progress", unit="job")
    
    def worker_thread():
        nonlocal stop_workers, saved_detail_count
        
        crawler = CareerVietCrawler()
        try:
            crawler.init_driver(headless=True)
        except Exception as e:
            print(f"\n[Worker-{threading.current_thread().name}] Failed to init Edge driver: {e}")
            return
            
        try:
            while not stop_workers:
                try:
                    job_info = job_queue.get(timeout=2.0)
                except Empty:
                    if stop_workers:
                        break
                    continue
                
                href = job_info["href"]
                title = job_info["title"]
                job_id = job_info["job_id"]
                
                # Double check under lock (though queue matches are unique)
                with file_lock:
                    if job_id in scraped_ids:
                        job_queue.task_done()
                        pbar.update(1)
                        continue
                    scraped_ids.add(job_id)
                
                try:
                    detail = crawler.crawl_job_detail_by_url(job_info)
                    if detail:
                        detail["job_id"] = job_id
                        detail["source"] = "careerviet"
                        detail["scope"] = job_info.get("scope")
                        detail["batch_id"] = job_info.get("batch_id") or args.batch_id
                        detail["crawled_at"] = datetime.now(timezone.utc).isoformat()
                        detail["source_job_id"] = job_id
                        
                        # Save to Firestore
                        try:
                            db.collection(dest_collection_name).document(job_id).set(detail, merge=True)
                            db.collection(src_collection_name).document(job_id).set({
                                "status": "scraped",
                                "scraped_at": detail["crawled_at"],
                                "dest_collection": dest_collection_name,
                            }, merge=True)
                            with file_lock:
                                saved_detail_count += 1
                        except Exception as fs_err:
                            tqdm.write(f"\n[Worker-{threading.current_thread().name}] Failed to save to Firestore for {title}: {fs_err}")

                                
                except Exception as e:
                    is_session_dead = any(term in str(e).lower() for term in ["invalid session id", "session not created", "chrome not reachable", "disconnected", "no such window"])
                    
                    if is_session_dead:
                        tqdm.write(f"\n[Worker-{threading.current_thread().name}] Session died. Restarting browser for job: {title}...")
                        try:
                            crawler.close()
                            time.sleep(2)
                            crawler.init_driver(headless=True)
                            
                            # Retry
                            detail = crawler.crawl_job_detail_by_url(job_info)
                            if detail:
                                detail["job_id"] = job_id
                                detail["source"] = "careerviet"
                                detail["scope"] = job_info.get("scope")
                                detail["batch_id"] = job_info.get("batch_id") or args.batch_id
                                detail["crawled_at"] = datetime.now(timezone.utc).isoformat()
                                detail["source_job_id"] = job_id
                                
                                try:
                                    db.collection(dest_collection_name).document(job_id).set(detail, merge=True)
                                    db.collection(src_collection_name).document(job_id).set({
                                        "status": "scraped",
                                        "scraped_at": detail["crawled_at"],
                                        "dest_collection": dest_collection_name,
                                    }, merge=True)
                                    with file_lock:
                                        saved_detail_count += 1
                                except Exception as fs_err:
                                    tqdm.write(f"\n[Worker-{threading.current_thread().name}] Failed to save to Firestore on retry: {fs_err}")

                        except Exception as restart_err:
                            tqdm.write(f"\n[Worker-{threading.current_thread().name}] Restart failed: {restart_err}. Returning job to queue.")
                            job_queue.put(job_info)
                            with file_lock:
                                if job_id in scraped_ids:
                                    scraped_ids.remove(job_id)
                            time.sleep(5)
                    elif any(term in str(e).lower() for term in ["rate limit", "cloudflare", "blocked"]):
                        tqdm.write(f"\n[Worker-{threading.current_thread().name}] Rate limit or Cloudflare block detected! Stopping workers.")
                        stop_workers = True
                        # Put back in queue to retry next run
                        job_queue.put(job_info)
                        with file_lock:
                            if job_id in scraped_ids:
                                scraped_ids.remove(job_id)
                    else:
                        tqdm.write(f"\n[Worker-{threading.current_thread().name}] Failed to scrape {title}: {e}")
                finally:
                    job_queue.task_done()
                    pbar.update(1)
                    time.sleep(1.5)
        finally:
            crawler.close()
            
    num_workers = max(1, args.workers)
    workers = []
    for i in range(num_workers):
        t = threading.Thread(target=worker_thread, name=f"Thread-{i+1}")
        t.daemon = True
        t.start()
        workers.append(t)
        
    # Wait for queue to finish
    try:
        while not job_queue.empty() and not stop_workers:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Gracefully stopping workers...")
        stop_workers = True
        
    # Set stop flag and join all
    stop_workers = True
    for t in workers:
        t.join(timeout=5.0)
        
    pbar.close()
    print(f"\nDone. Saved {saved_detail_count} job details to Firestore collection {dest_collection_name}.")
    if remaining_jobs and saved_detail_count == 0 and not args.allow_empty:
        print("No CareerViet job details were written. Failing job so Cloud Run does not report a false success.")
        raise SystemExit(3)

if __name__ == "__main__":
    main()
