import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawl_jobs.crawler import CareerVietCrawler

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    crawler = CareerVietCrawler()
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todo_crawl.json")
    
    todo_list = []
    seen_ids = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                todo_list = json.load(f)
                seen_ids = {item["job_id"] for item in todo_list}
            print(f"Loaded {len(todo_list)} existing links from {output_path}")
        except Exception as e:
            print(f"Error loading existing todo_crawl.json: {e}")

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
                title = job["title"]
                job_id = crawler.extract_job_id(href)
                if job_id and job_id not in seen_ids:
                    todo_list.append({
                        "job_id": job_id,
                        "title": title,
                        "href": href
                    })
                    seen_ids.add(job_id)
                    new_links_count += 1
                    
            print(f"Page {page}: Found {len(job_links)} total links. Added {new_links_count} new unique links.")
            
            # Save progress dynamically
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(todo_list, f, indent=2, ensure_ascii=False)
                
            page += 1
            time.sleep(2.0)
            
    except Exception as e:
        print(f"Crawl links job terminated due to exception: {e}")
    finally:
        crawler.close()
        print(f"\nLink Extraction Finished. Total unique links to crawl: {len(todo_list)}")
        print(f"Saved to: {output_path}")

if __name__ == "__main__":
    main()
