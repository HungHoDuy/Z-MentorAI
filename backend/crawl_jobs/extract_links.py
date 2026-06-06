import os
import sys
import time
from google.cloud import firestore

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawl_jobs.crawler import CareerVietCrawler

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    crawler = CareerVietCrawler()
    
    # Initialize Firestore client
    try:
        db = firestore.Client()
        collection_name = "todo_careerviet"
    except Exception as e:
        print(f"Error initializing Firestore client: {e}")
        return

    seen_ids = set()
    try:
        print("Fetching existing job IDs from Firestore 'todo_careerviet'...")
        docs = db.collection(collection_name).select([]).stream()
        seen_ids = {doc.id for doc in docs}
        print(f"Loaded {len(seen_ids)} existing links from Firestore.")
    except Exception as e:
        print(f"Error loading existing links from Firestore: {e}. Starting fresh.")

    try:
        crawler.init_driver(headless=True)
        print("Driver initialized successfully.")
        
        page = 1
        consecutive_empty_pages = 0
        
        while True:
            print(f"\nFetching listings on Page {page}...")
            try:
                job_links = crawler.get_job_links_from_page(page)
            except Exception as e:
                print(f"Error fetching page {page} listing (potential block): {e}")
                break
                
            if not job_links:
                consecutive_empty_pages += 1
                print(f"No job links found on Page {page}.")
                if consecutive_empty_pages >= 3:
                    print("Three consecutive empty pages. Stopping listings search.")
                    break
                page += 1
                time.sleep(2.0)
                continue
            else:
                consecutive_empty_pages = 0
                
            new_links_count = 0
            for job in job_links:
                href = job["href"]
                job_id = crawler.extract_job_id(href)
                if job_id and job_id not in seen_ids:
                    try:
                        db.collection(collection_name).document(job_id).set({
                            "job_id": job_id,
                            "href": href
                        })
                        seen_ids.add(job_id)
                        new_links_count += 1
                    except Exception as fs_err:
                        print(f"Error saving job {job_id} to Firestore: {fs_err}")
                        
            print(f"Page {page}: Found {len(job_links)} total links. Added {new_links_count} new unique links to Firestore.")
            
            page += 1
            time.sleep(2.0)
            
    except Exception as e:
        print(f"Crawl links job terminated due to exception: {e}")
    finally:
        crawler.close()
        print(f"\nLink Extraction Finished. Total unique links in Firestore: {len(seen_ids)}")

if __name__ == "__main__":
    main()
