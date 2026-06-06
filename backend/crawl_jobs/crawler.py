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

class CareerVietCrawler:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.driver = None

    def init_driver(self, headless: bool = True):
        """Initializes the Edge WebDriver."""
        logger.info("Initializing Microsoft Edge WebDriver...")
        options = Options()
        # Edge configurations
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        if headless:
            options.add_argument("--headless=new")
        
        # Prevent automation detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Disable geolocation permissions entirely to prevent location-based page redirects
        prefs = {
            "profile.default_content_setting_values.geolocation": 2
        }
        options.add_experimental_option("prefs", prefs)

        try:
            # Try to install Edge driver using webdriver-manager
            service = Service(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=options)
        except Exception as e:
            logger.warning(f"webdriver-manager failed: {e}. Falling back to default system path driver.")
            # Fall back to default selenium behavior
            self.driver = webdriver.Edge(options=options)
            
        # Bypass webdriver detection
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

    def close(self):
        if self.driver:
            logger.info("Closing WebDriver...")
            self.driver.quit()
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
            ".btn-close"
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
        """Parses the unique job alphanumeric ID from the Careerviet URL."""
        if not url:
            return None
        # Pattern: .<job_id>.html
        match = re.search(r'\.([a-zA-Z0-9]+)\.html$', url.split('?')[0])
        if match:
            return match.group(1)
        return None

    def get_job_links_from_page(self, page_index: int):
        """Navigates to the search page and extracts job links."""
        url = f"https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-{page_index}-vi.html"
        logger.info(f"Navigating to page: {url}")
        self.driver.get(url)
        
        # Wait for the job list content to load
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, "jobs-side-list-content"))
            )
        except TimeoutException:
            logger.warning("Timeout waiting for #jobs-side-list-content to load.")
            
        self.dismiss_popups()
        time.sleep(2)
        
        # Try to find all job title elements (avoiding the wrapper cards)
        job_links = []
        try:
            # We target the title link directly to avoid double matching and location redirects
            elements = self.driver.find_elements(By.CSS_SELECTOR, "#jobs-side-list-content .figcaption .title a.job_link")
            for el in elements:
                try:
                    href = el.get_attribute("href")
                    title = el.text.strip()
                    # Ensure the link has an href and is not empty
                    if href and title:
                        job_links.append({
                            "href": href,
                            "title": title
                        })
                except Exception as inner_e:
                    # Skip stale elements and continue
                    logger.debug(f"Skipping a stale or unreadable job link: {inner_e}")
                    pass
            logger.info(f"Found {len(job_links)} jobs on page {page_index}.")
        except Exception as e:
            logger.error(f"Error finding job links container: {e}")
            raise e # Raise to notify outer loop of failure/rate limit
            
        return job_links

    def scrape_current_details(self) -> dict:
        """Parses the detailed job information from the current page/pane."""
        data = {}
        
        # Standard labels to extract
        labels = [
            "Ngày cập nhật",
            "Ngành nghề",
            "Hình thức",
            "Lương",
            "Kinh nghiệm",
            "Cấp bậc",
            "Hết hạn nộp",
            "Địa điểm làm việc",
            "Địa điểm"
        ]

        # Helper to search for list items/divs containing labels, while ignoring giant container elements
        def find_info_by_label(label_text):
            xpath_queries = [
                f"//li[contains(., '{label_text}')]",
                f"//div[contains(., '{label_text}')]",
                f"//p[contains(., '{label_text}')]",
                f"//span[contains(., '{label_text}')]"
            ]
            for query in xpath_queries:
                try:
                    elements = self.driver.find_elements(By.XPATH, query)
                    for el in elements:
                        text = el.text.strip()
                        if text and label_text in text:
                            # Heuristic: Avoid containers that contain other field labels
                            other_labels = [l for l in labels if l.lower() != label_text.lower() and l.lower() != "địa điểm"]
                            if label_text.lower() == "địa điểm":
                                other_labels.append("địa điểm làm việc")
                            if any(ol.lower() in text.lower() for ol in other_labels):
                                continue  # Reject parent container false positive
                                
                            val = text
                            idx = val.find(label_text)
                            if idx != -1:
                                val = val[idx + len(label_text):].strip()
                            # Clean up leading colons/hyphens
                            val = val.lstrip(":- \t\n")
                            if val and len(val) < 250:
                                return val
                except Exception:
                    pass
            return None

        # Extract standard text fields
        data["Ngày cập nhật"] = find_info_by_label("Ngày cập nhật")
        data["Ngành nghề"] = find_info_by_label("Ngành nghề")
        data["Hình thức"] = find_info_by_label("Hình thức")
        data["Lương"] = find_info_by_label("Lương")
        data["Kinh nghiệm"] = find_info_by_label("Kinh nghiệm")
        data["Cấp bậc"] = find_info_by_label("Cấp bậc")
        data["Hết hạn nộp"] = find_info_by_label("Hết hạn nộp")

        # Extract Company
        company = None
        for sel in [".employer.job-company-name", ".job-company-name", ".employer", "a.employer"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                txt = el.text.strip()
                if txt:
                    company = txt
                    break
            except Exception:
                pass
        data["company"] = company

        # Extract Phúc lợi (Benefits)
        benefits = []
        # Welfare list selectors
        for sel in [".welfare-list li", ".benefits-list li", ".welfare-list-info li", ".job-detail-benefits li", ".welfare-content li"]:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    for el in els:
                        txt = el.text.strip()
                        if txt and txt not in benefits:
                            benefits.append(txt)
            except Exception:
                pass
        
        # Fallback for Phúc lợi: look for heading and scrape below it
        if not benefits:
            try:
                headers = self.driver.find_elements(By.XPATH, "//*[self::h2 or self::h3 or self::h4 or self::h5 or self::p or self::span][contains(text(), 'Phúc lợi') or contains(text(), 'phúc lợi') or contains(text(), 'PHÚC LỢI')]")
                for h in headers:
                    parent = h.find_element(By.XPATH, "..")
                    lis = parent.find_elements(By.TAG_NAME, "li")
                    if lis:
                        for li in lis:
                            txt = li.text.strip()
                            if txt and txt not in benefits:
                                benefits.append(txt)
            except Exception:
                pass
        data["Phúc lợi"] = benefits

        # Helper to extract sections like Job Description / Requirements by heading name
        def find_section_by_heading(heading_text):
            try:
                # Find all possible heading elements
                candidates = self.driver.find_elements(By.CSS_SELECTOR, "h2, h3, h4, h5, h6, .detail-title, .title, strong, p")
                matching_header = None
                for el in candidates:
                    try:
                        txt = el.text.strip().lower()
                        # Match heading exactly or startswith
                        if txt == heading_text.lower() or txt.startswith(heading_text.lower()):
                            if len(txt) < 100:  # Ensure it is a heading, not a large body paragraph
                                matching_header = el
                                break
                    except Exception:
                        pass
                
                if not matching_header:
                    return None
                    
                # Walk up to find a container that contains this section without spilling into others
                current = matching_header
                for _ in range(4):  # Check up to 4 levels of parent nesting
                    parent = current.find_element(By.XPATH, "..")
                    parent_text = parent.text.strip().lower()
                    
                    # Check if parent text contains other section headers
                    other_sections = ["mô tả công việc", "yêu cầu công việc", "phúc lợi", "thông tin khác", "ngày cập nhật"]
                    other_sections_filtered = [s for s in other_sections if s != heading_text.lower()]
                    
                    has_others = False
                    for os_name in other_sections_filtered:
                        if os_name in parent_text:
                            has_others = True
                            break
                            
                    if not has_others:
                        content = parent.text.strip()
                        header_text = matching_header.text
                        if content.startswith(header_text):
                            content = content[len(header_text):].strip()
                        elif content.endswith(header_text):
                            content = content[:-len(header_text)].strip()
                        else:
                            content = content.replace(header_text, "").strip()
                        
                        content = content.lstrip(":- \t\n")
                        if content:
                            return content
                    current = parent
                    
                # Sibling fallback: if no clean parent container is found, collect subsequent siblings
                siblings = matching_header.find_elements(By.XPATH, "following-sibling::*")
                content_parts = []
                for sib in siblings:
                    sib_text = sib.text.strip()
                    if not sib_text:
                        continue
                    sib_text_lower = sib_text.lower()
                    other_sections = ["mô tả công việc", "yêu cầu công việc", "phúc lợi", "thông tin khác"]
                    if any(os_name in sib_text_lower and len(sib_text) < 100 for os_name in other_sections):
                        break
                    content_parts.append(sib_text)
                    
                if content_parts:
                    return "\n".join(content_parts)
            except Exception as e:
                logger.error(f"Error extracting section {heading_text}: {e}")
            return None

        # Extract Mô tả Công việc
        data["Mô tả Công việc"] = find_section_by_heading("Mô tả Công việc") or find_section_by_heading("MÔ TẢ CÔNG VIỆC") or find_section_by_heading("Mô tả")
        
        # Extract Yêu Cầu Công Việc
        data["Yêu Cầu Công Việc"] = find_section_by_heading("Yêu Cầu Công Việc") or find_section_by_heading("Yêu cầu công việc") or find_section_by_heading("Yêu cầu")

        # Extract Địa điểm làm việc
        work_loc = find_info_by_label("Địa điểm làm việc") or find_info_by_label("Địa điểm")
        if not work_loc:
            # Try to get from heading
            work_loc = find_section_by_heading("Địa điểm làm việc") or find_section_by_heading("Địa điểm")
        if not work_loc:
            # Try CSS selectors
            for sel in [".work-location", ".map-wrapper", ".location"]:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        txt = el.text.strip()
                        if txt:
                            work_loc = txt
                            break
                    if work_loc:
                        break
                except Exception:
                    pass
        data["Địa điểm làm việc"] = work_loc

        # Extract Thông tin khác
        data["Thông tin khác"] = find_section_by_heading("Thông tin khác") or find_section_by_heading("THÔNG TIN KHÁC")

        return data

    def crawl_job_detail_by_url(self, job_link_info: dict) -> dict:
        """Navigates directly to the job URL, scrapes details, and returns details dictionary."""
        href = job_link_info["href"]
        title = job_link_info["title"]
        
        logger.info(f"Navigating directly to job: {title} (URL: {href})")
        
        try:
            self.driver.get(href)
            time.sleep(3.0) # Wait for page load
            
            # Check if we landed on a rate limit or Cloudflare challenge page by title
            title_lower = self.driver.title.lower()
            if any(term in title_lower for term in ["429", "too many requests", "access denied", "cloudflare", "just a moment"]):
                raise Exception(f"Rate limit or Cloudflare block detected in Page Title: {self.driver.title}")

            # Fallback: check text of H1 tags
            try:
                h1_elements = self.driver.find_elements(By.TAG_NAME, "h1")
                for h1 in h1_elements:
                    h1_text = h1.text.lower()
                    if any(term in h1_text for term in ["429", "too many requests", "access denied", "cloudflare"]):
                        raise Exception(f"Rate limit or Cloudflare block detected in H1 text: {h1.text}")
            except Exception as h1_err:
                # If finding H1 throws, it might be a stale frame/error
                pass
                
            self.dismiss_popups()
            
            data = self.scrape_current_details()
            data["job_title"] = title
            data["job_url"] = href
            return data
        except Exception as e:
            logger.error(f"Error crawling job details for {title}: {e}")
            raise e
