import time
import re
import logging
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Suppress noisy third-party libraries
for name in ["selenium", "urllib3", "webdriver_manager", "wdm", "google"]:
    logging.getLogger(name).setLevel(logging.WARNING)

class TopCVCrawler:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.driver = None

    def init_driver(self, headless: bool = False):
        """Initializes the Edge WebDriver."""
        logger.info(f"Initializing Microsoft Edge WebDriver (headless={headless})...")
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disk-cache-size=1")
        options.add_argument("--media-cache-size=1")
        
        if headless:
            options.add_argument("--headless=new")
        
        # Prevent automation detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Disable geolocation
        prefs = {
            "profile.default_content_setting_values.geolocation": 2
        }
        options.add_experimental_option("prefs", prefs)

        try:
            service = Service(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=options)
        except Exception as e:
            logger.warning(f"webdriver-manager failed: {e}. Falling back to default system path driver.")
            self.driver = webdriver.Edge(options=options)
            
        # Bypass webdriver detection
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

    def close(self):
        if self.driver:
            logger.info("Closing WebDriver...")
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error quitting driver: {e}")
            self.driver = None

    def dismiss_popups(self):
        """Attempts to close common overlay popups on the site."""
        popup_selectors = [
            ".fancybox-close", 
            "#fancybox-close", 
            ".modal-close", 
            ".close-popup", 
            "[aria-label='Close']",
            ".pop-close",
            ".btn-close",
            ".modal-header .close"
        ]
        for sel in popup_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    if el.is_displayed():
                        el.click()
                        logger.info(f"Dismissed popup using selector: {sel}")
            except Exception:
                pass

    def extract_job_id(self, url: str) -> str:
        """Parses the unique job numeric ID from the TopCV URL."""
        if not url:
            return None
        # Pattern: /viec-lam/{slug}/{id}.html
        match = re.search(r'/(\d+)\.html$', url.split('?')[0])
        if match:
            return match.group(1)
        return None

    def get_job_links_from_page(self, page_index: int):
        """Navigates to the search page and extracts job links."""
        url = f"https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&page={page_index}&saturday_status=0&sba=1"
        logger.info(f"Navigating to page: {url}")
        self.driver.get(url)
        
        # Wait for the job list content to load
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "job-list-search-result"))
            )
        except TimeoutException:
            logger.warning("Timeout waiting for job-list-search-result to load.")
            
        self.dismiss_popups()
        time.sleep(2.0)
        
        job_links = []
        try:
            # Candidate CSS selectors for job titles and links
            selectors = [
                ".job-item-search-result h3.title a",
                ".web-job-item h3.title a",
                ".job-item-search-result .job-title a",
                ".job-list-search-result h3.title a",
                "a[href*='/viec-lam/']"
            ]
            
            elements = []
            for sel in selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elements:
                    break

            for el in elements:
                try:
                    href = el.get_attribute("href")
                    title = el.text.strip()
                    if not title:
                        title = el.get_attribute("textContent").strip()
                    
                    if href and "/viec-lam/" in href:
                        job_id = self.extract_job_id(href)
                        if job_id:
                            # Avoid duplicates
                            if not any(item["href"] == href for item in job_links):
                                job_links.append({
                                    "href": href,
                                    "title": title
                                })
                except Exception as inner_e:
                    logger.debug(f"Skipping stale or unreadable element: {inner_e}")
                    pass
            logger.info(f"Found {len(job_links)} jobs on page {page_index}.")
        except Exception as e:
            logger.error(f"Error finding job links container: {e}")
            raise e
            
        return job_links

    def scrape_current_details(self) -> dict:
        """Parses detailed job information from the current TopCV job page."""
        data = {}
        
        # 1. Job Title
        job_title = None
        for sel in ["h1.job-detail__info--title", ".job-title", "h1.title-job", "h1"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                txt = el.text.strip()
                if txt:
                    job_title = txt
                    break
            except Exception:
                pass
        data["job_title"] = job_title

        # 2. Company Name
        company = None
        for sel in [".company-sidebar a.name", ".company-info a.name", ".company-name", ".company-info .name"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                txt = el.text.strip()
                if txt:
                    company = txt
                    break
            except Exception:
                pass
        data["company"] = company

        # 3. Key info extraction from detail cards/items
        # TopCV uses a structured key-value sidebar or header section
        # Format: Mức lương, Kinh nghiệm, Địa điểm, Cấp bậc, Hình thức, Hết hạn nộp
        info_items = self.driver.find_elements(By.CSS_SELECTOR, ".job-detail__info-item, .job-detail__info--section")
        
        def find_info_by_label(label_text):
            # Check custom info blocks
            for el in info_items:
                try:
                    text = el.text.strip()
                    if label_text.lower() in text.lower():
                        # Extract the value part (often has a separate class, e.g. .job-detail__info-item-value)
                        try:
                            val_el = el.find_element(By.CSS_SELECTOR, ".job-detail__info-item-value, .value")
                            val = val_el.text.strip()
                            if val:
                                return val
                        except Exception:
                            pass
                        
                        # Fallback: strip the label prefix
                        idx = text.lower().find(label_text.lower())
                        if idx != -1:
                            val = text[idx + len(label_text):].strip()
                            val = val.lstrip(":- \t\n")
                            if val:
                                return val
                except Exception:
                    pass
            return None

        data["Lương"] = find_info_by_label("Mức lương") or find_info_by_label("Lương")
        data["Kinh nghiệm"] = find_info_by_label("Kinh nghiệm")
        data["Hình thức"] = find_info_by_label("Hình thức")
        data["Cấp bậc"] = find_info_by_label("Cấp bậc") or find_info_by_label("Chức vụ")
        data["Hết hạn nộp"] = find_info_by_label("Hạn nộp") or find_info_by_label("Hạn nộp hồ sơ")
        
        # Địa điểm làm việc
        work_loc = find_info_by_label("Địa điểm") or find_info_by_label("Địa điểm làm việc")
        if not work_loc:
            # Fallback to search list item / metadata on page
            for sel in [".job-detail__info--section .value", ".job-detail__info-item-value"]:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    txt = el.text.strip()
                    if txt and ("hà nội" in txt.lower() or "hồ chí minh" in txt.lower() or "đà nẵng" in txt.lower() or "toàn quốc" in txt.lower()):
                        work_loc = txt
                        break
                except Exception:
                    pass
        data["Địa điểm làm việc"] = work_loc

        # Standard placeholders for missing CareerViet fields to maintain exact schema
        data["Ngày cập nhật"] = None  # TopCV rarely displays "Ngày cập nhật" directly
        data["Ngành nghề"] = None     # Usually extracted from tags or set post-hoc
        data["Thông tin khác"] = None

        # 4. Job Description, Requirements, Benefits
        def find_section_content(heading_text):
            try:
                # TopCV typically wraps sections in .job-description__item with an h3 header
                items = self.driver.find_elements(By.CSS_SELECTOR, ".job-description__item, .job-detail__section")
                for item in items:
                    try:
                        header = item.find_element(By.CSS_SELECTOR, "h3, h4, h2")
                        header_text = header.text.strip().lower()
                        if heading_text.lower() in header_text:
                            # Content is usually in .job-description__item--content
                            try:
                                content_el = item.find_element(By.CSS_SELECTOR, ".job-description__item--content, .content, .job-detail__section-content")
                                return content_el.text.strip()
                            except Exception:
                                pass
                            # Fallback: get entire item text and strip header text
                            full_text = item.text.strip()
                            if full_text.startswith(header.text):
                                return full_text[len(header.text):].strip()
                            return full_text
                    except Exception:
                        pass
            except Exception:
                pass
            return None

        data["Mô tả Công việc"] = find_section_content("Mô tả công việc") or find_section_content("Mô tả")
        data["Yêu Cầu Công Việc"] = find_section_content("Yêu cầu ứng viên") or find_section_content("Yêu cầu công việc") or find_section_content("Yêu cầu")
        
        # Quyền lợi (Benefits)
        benefits_text = find_section_content("Quyền lợi") or find_section_content("Phúc lợi")
        benefits_list = []
        if benefits_text:
            # Parse lines/bullets if possible to match CareerViet's list format
            benefits_list = [line.strip().lstrip("*-• ") for line in benefits_text.split("\n") if line.strip()]
        data["Phúc lợi"] = benefits_list

        return data

    def crawl_job_detail_by_url(self, job_link_info: dict) -> dict:
        """Navigates to job URL, scrapes details, and returns details dictionary."""
        href = job_link_info["href"]
        title = job_link_info["title"]
        
        logger.info(f"Navigating to job: {title} (URL: {href})")
        try:
            self.driver.get(href)
            time.sleep(3.0) # Wait for page load
            
            title_lower = self.driver.title.lower()
            if any(term in title_lower for term in ["429", "too many requests", "access denied", "cloudflare", "just a moment"]):
                raise Exception(f"Rate limit or Cloudflare block: {self.driver.title}")

            self.dismiss_popups()
            data = self.scrape_current_details()
            if not data.get("job_title"):
                data["job_title"] = title
            data["job_url"] = href
            return data
        except Exception as e:
            logger.error(f"Error crawling job details for {title}: {e}")
            raise e
