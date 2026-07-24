import os
import sys
import time
import threading
import argparse
from datetime import datetime, timezone
from google.cloud import firestore

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from crawl_jobs.crawler import CareerVietCrawler
except ModuleNotFoundError:
    from crawler import CareerVietCrawler


SCOPE_KEYWORDS = {
    "it": (
        "backend",
        "frontend",
        "developer",
        "software",
        "lập trình",
        "lap trinh",
        "cntt",
        "công nghệ thông tin",
        "cong nghe thong tin",
        "data analyst",
        "business analyst",
        "tester",
        "qa",
        "devops",
        "it support",
    ),
    "sales": (
        "sales",
        "sale",
        "bán hàng",
        "ban hang",
        "kinh doanh",
        "business development",
        "account executive",
        "telesales",
    ),
}


def parse_args():
    parser = argparse.ArgumentParser(description="Extract CareerViet job links into Firestore.")
    parser.add_argument("--todo-collection", default="todo_careerviet")
    parser.add_argument("--scope", choices=("it", "sales", "it-sales", "all"), default="it-sales")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="Extra title keyword filter. Can be passed multiple times.",
    )
    return parser.parse_args()


def keywords_for_scope(scope: str, extra_keywords: list[str]) -> tuple[str, ...]:
    if scope == "all":
        return tuple(keyword.casefold() for keyword in extra_keywords)
    keywords: list[str] = []
    if scope in ("it", "it-sales"):
        keywords.extend(SCOPE_KEYWORDS["it"])
    if scope in ("sales", "it-sales"):
        keywords.extend(SCOPE_KEYWORDS["sales"])
    keywords.extend(extra_keywords)
    return tuple(dict.fromkeys(keyword.casefold() for keyword in keywords if keyword.strip()))


def matches_scope(title: str, keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return True
    normalized = " ".join(title.casefold().split())
    return any(keyword in normalized for keyword in keywords)

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
    for logger_name in ["selenium", "urllib3", "webdriver_manager", "wdm", "google"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Initialize Firestore client
    try:
        db = firestore.Client()
        collection_name = args.todo_collection
    except Exception as e:
        print(f"Error initializing Firestore client: {e}")
        return

    seen_ids = set()
    try:
        print(f"Fetching existing job IDs from Firestore '{collection_name}'...")
        docs = db.collection(collection_name).select([]).stream()
        seen_ids = {doc.id for doc in docs}
        print(f"Loaded {len(seen_ids)} existing links from Firestore.")
    except Exception as e:
        print(f"Error loading existing links from Firestore: {e}. Starting fresh.")

    # Threading variables
    page_lock = threading.Lock()
    seen_ids_lock = threading.Lock()
    
    current_page = args.start_page
    last_page = args.start_page + args.max_pages - 1
    empty_pages = set()
    completed_pages = set()
    stop_extraction = False
    scope_keywords = keywords_for_scope(args.scope, args.keyword)

    def check_stop_condition():
        nonlocal stop_extraction
        max_continuous = 0
        while (max_continuous + 1) in completed_pages:
            max_continuous += 1
            
        for p in range(1, max_continuous - 1):
            if p in empty_pages and (p+1) in empty_pages and (p+2) in empty_pages:
                stop_extraction = True
                return True
        return False

    def worker_thread(thread_id):
        nonlocal current_page, stop_extraction
        
        crawler = CareerVietCrawler()
        try:
            crawler.init_driver(headless=True)
        except Exception as e:
            print(f"[Worker-{thread_id}] Failed to initialize WebDriver: {e}")
            return

        try:
            while not stop_extraction:
                with page_lock:
                    if current_page > last_page:
                        stop_extraction = True
                        break
                    page = current_page
                    current_page += 1
                
                print(f"[Worker-{thread_id}] Fetching listings on Page {page}...")
                try:
                    job_links = crawler.get_job_links_from_page(page)
                except Exception as e:
                    print(f"[Worker-{thread_id}] Error fetching page {page} listing (potential block): {e}")
                    with page_lock:
                        stop_extraction = True
                    break

                new_links_count = 0
                if not job_links:
                    with page_lock:
                        empty_pages.add(page)
                        completed_pages.add(page)
                        check_stop_condition()
                    print(f"[Worker-{thread_id}] Page {page}: No job links found.")
                else:
                    for job in job_links:
                        href = job["href"]
                        title = job.get("title", "")
                        if not matches_scope(title, scope_keywords):
                            continue
                        job_id = crawler.extract_job_id(href)
                        if job_id:
                            is_new = False
                            with seen_ids_lock:
                                if job_id not in seen_ids:
                                    seen_ids.add(job_id)
                                    is_new = True
                            
                            if is_new:
                                try:
                                    db.collection(collection_name).document(job_id).set({
                                        "job_id": job_id,
                                        "href": href,
                                        "title": title,
                                        "source": "careerviet",
                                        "scope": args.scope,
                                        "discovered_at": datetime.now(timezone.utc).isoformat(),
                                    }, merge=True)
                                    new_links_count += 1
                                except Exception as fs_err:
                                    print(f"[Worker-{thread_id}] Error saving job {job_id} to Firestore: {fs_err}")
                    
                    with page_lock:
                        completed_pages.add(page)
                        check_stop_condition()

                    print(f"[Worker-{thread_id}] Page {page}: Found {len(job_links)} total links. Added {new_links_count} new unique links to Firestore.")
                
                time.sleep(2.0)
        finally:
            crawler.close()

    num_workers = max(1, args.workers)
    threads = []
    print(
        f"Starting {num_workers} extraction threads: pages={args.start_page}-{last_page}, "
        f"scope={args.scope}, keyword_filter={bool(scope_keywords)}"
    )
    for i in range(num_workers):
        t = threading.Thread(target=worker_thread, args=(i+1,), name=f"ExtractWorker-{i+1}")
        t.daemon = True
        t.start()
        threads.append(t)

    # Monitor threads
    try:
        while any(t.is_alive() for t in threads) and not stop_extraction:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Gracefully stopping workers...")
        stop_extraction = True

    # Wait for all threads to terminate
    stop_extraction = True
    for t in threads:
        t.join(timeout=5.0)

    print(f"\nLink Extraction Finished. Total unique links in Firestore: {len(seen_ids)}")

if __name__ == "__main__":
    main()
