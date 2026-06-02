import json
import os
import sys
import time
import threading
from queue import Queue, Empty
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawl_jobs.crawler import CareerVietCrawler

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    todo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todo_crawl.json")
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "first_page_jobs.json")
    
    # 1. Load todo list
    if not os.path.exists(todo_path):
        print(f"Error: {todo_path} does not exist. Please run extract_links.py first.")
        return
        
    with open(todo_path, "r", encoding="utf-8") as f:
        todo_list = json.load(f)
        
    print(f"Loaded {len(todo_list)} total jobs to crawl from {todo_path}")

    # 2. Load already scraped jobs to support resume
    scraped_jobs = []
    scraped_ids = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                scraped_jobs = json.load(f)
                scraped_ids = {job["job_id"] for job in scraped_jobs}
            print(f"Found {len(scraped_jobs)} already crawled jobs. Resuming from last attempt...")
        except Exception as e:
            print(f"Error reading existing first_page_jobs.json: {e}. Starting fresh.")

    # 3. Filter remaining jobs
    remaining_jobs = [job for job in todo_list if job["job_id"] not in scraped_ids]
    print(f"Remaining jobs to crawl: {len(remaining_jobs)}")
    
    if not remaining_jobs:
        print("All jobs from todo list have already been crawled!")
        return

    # 4. Threading variables
    file_lock = threading.Lock()
    job_queue = Queue()
    for job in remaining_jobs:
        job_queue.put(job)
        
    stop_workers = False
    
    # 5. Initialize tqdm progress bar
    pbar = tqdm(total=len(remaining_jobs), desc="Scraping progress", unit="job")
    
    def worker_thread():
        nonlocal stop_workers
        
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
                        
                        with file_lock:
                            scraped_jobs.append(detail)
                            with open(output_path, "w", encoding="utf-8") as f:
                                json.dump(scraped_jobs, f, indent=2, ensure_ascii=False)
                                
                except Exception as e:
                    is_session_dead = any(term in str(e).lower() for term in ["invalid session id", "session not created", "chrome not reachable", "disconnected", "no such window"])
                    
                    if is_session_dead:
                        # Log message printed above progress bar
                        tqdm.write(f"\n[Worker-{threading.current_thread().name}] Session died. Restarting browser for job: {title}...")
                        try:
                            crawler.close()
                            time.sleep(2)
                            crawler.init_driver(headless=True)
                            
                            # Retry
                            detail = crawler.crawl_job_detail_by_url(job_info)
                            if detail:
                                detail["job_id"] = job_id
                                with file_lock:
                                    scraped_jobs.append(detail)
                                    with open(output_path, "w", encoding="utf-8") as f:
                                        json.dump(scraped_jobs, f, indent=2, ensure_ascii=False)
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
            
    # Start 5 threads
    num_workers = 5
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
    print(f"\nDone. Successfully scraped {len(scraped_jobs)} total jobs.")
    print(f"Result file: {output_path}")

if __name__ == "__main__":
    main()
