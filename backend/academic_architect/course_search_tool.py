import os
import time
import asyncio
import urllib.parse
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

class CourseSearchTool:
    def __init__(self, headless: bool = None):
        if headless is None:
            # Default to running headless inside Docker, but visible (non-headless) locally for visual debugging
            is_in_docker = os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')
            self.headless = True if is_in_docker else False
        else:
            self.headless = headless

    def _get_driver(self):
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,800")
        
        # User-Agent representing Edge on Windows
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")
        
        # If running inside Linux/Docker with Edge installed
        if os.path.exists("/usr/bin/microsoft-edge"):
            options.binary_location = "/usr/bin/microsoft-edge"
            
        driver = webdriver.Edge(options=options)
        driver.set_page_load_timeout(25)
        return driver

    async def search_coursera(self, query: str) -> list[dict]:
        """Scrapes Coursera search results with metadata using Edge."""
        return await asyncio.to_thread(self._fetch_coursera, query)

    def _fetch_coursera(self, query: str) -> list[dict]:
        driver = self._get_driver()
        results = []
        try:
            url = f"https://www.coursera.org/search?query={urllib.parse.quote(query)}"
            driver.get(url)
            # Wait for content to load
            time.sleep(5)
            
            # Find product cards
            cards = driver.find_elements(By.CSS_SELECTOR, "div.cds-ProductCard-gridCard, div.cds-ProductCard-multipleCard, [data-testid='product-card']")
            if not cards:
                # Fallback to general links
                cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='/learn/'], a[href*='/specializations/']")
            
            for card in cards[:5]:
                try:
                    title = ""
                    url = ""
                    partner = ""
                    rating = ""
                    duration = ""
                    
                    if card.tag_name == "a":
                        url = card.get_attribute("href")
                        title = card.text.split("\n")[0] if card.text else "Coursera Course"
                    else:
                        anchor = card.find_element(By.CSS_SELECTOR, "a")
                        url = anchor.get_attribute("href")
                        
                        title_elems = card.find_elements(By.CSS_SELECTOR, "h3, h4, .cds-CommonCard-title")
                        if title_elems:
                            title = title_elems[0].text
                            
                        partner_elems = card.find_elements(By.CSS_SELECTOR, ".cds-ProductCard-partnerNames, .partner-name")
                        if partner_elems:
                            partner = partner_elems[0].text
                            
                        rating_elems = card.find_elements(By.CSS_SELECTOR, ".cds-CommonCard-ratings, [data-testid='rating-number']")
                        if rating_elems:
                            rating = rating_elems[0].text.split("\n")[0]
                            
                        metadata_elems = card.find_elements(By.CSS_SELECTOR, ".cds-ProductCard-metadata, .metadata-item")
                        if metadata_elems:
                            duration = ", ".join(m.text for m in metadata_elems if m.text)
                    
                    if url and title:
                        results.append({
                            "title": title.strip(),
                            "url": url,
                            "platform": "Coursera",
                            "partner_creator": partner.strip() if partner else "Coursera Partner",
                            "rating": rating.strip() if rating else "N/A",
                            "duration_details": duration.strip() if duration else "N/A"
                        })
                except Exception as card_err:
                    print(f"Error parsing Coursera card: {card_err}")
        except Exception as e:
            print(f"Error scraping Coursera: {e}")
        finally:
            driver.quit()
        return results

    async def search_udemy(self, query: str) -> list[dict]:
        """Scrapes Udemy search results with metadata using Edge."""
        return await asyncio.to_thread(self._fetch_udemy, query)

    def _fetch_udemy(self, query: str) -> list[dict]:
        driver = self._get_driver()
        results = []
        try:
            url = f"https://www.udemy.com/courses/search/?q={urllib.parse.quote(query)}"
            driver.get(url)
            # Sleep slightly longer as Udemy has heavy script loading
            time.sleep(6)
            
            cards = driver.find_elements(By.CSS_SELECTOR, ".course-card-module--container--, div.course-card--container--")
            if not cards:
                cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='/course/']")
                
            for card in cards[:5]:
                try:
                    title = ""
                    url = ""
                    instructor = ""
                    rating = ""
                    duration = ""
                    
                    if card.tag_name == "a":
                        url = card.get_attribute("href")
                        title = card.text.split("\n")[0] if card.text else "Udemy Course"
                    else:
                        anchor = card.find_element(By.CSS_SELECTOR, "a[href*='/course/']")
                        url = anchor.get_attribute("href")
                        
                        title_elems = card.find_elements(By.CSS_SELECTOR, "h3[data-purpose='course-title-link'], h3")
                        if title_elems:
                            title = title_elems[0].text
                            
                        instructor_elems = card.find_elements(By.CSS_SELECTOR, "[data-purpose='safely-set-inner-html:course-card:visible-instructors'], .course-card-module--instructor-list--")
                        if instructor_elems:
                            instructor = instructor_elems[0].text
                            
                        rating_elems = card.find_elements(By.CSS_SELECTOR, "[data-purpose='rating-number'], .star-rating-module--rating-number--")
                        if rating_elems:
                            rating = rating_elems[0].text
                            
                        meta_elems = card.find_elements(By.CSS_SELECTOR, "[data-purpose='course-meta-info'], .course-card-module--row--")
                        if meta_elems:
                            duration = meta_elems[0].text.replace("\n", " • ")
                            
                    if url and title:
                        results.append({
                            "title": title.strip(),
                            "url": url,
                            "platform": "Udemy",
                            "partner_creator": instructor.strip() if instructor else "Udemy Instructor",
                            "rating": rating.strip() if rating else "N/A",
                            "duration_details": duration.strip() if duration else "N/A"
                        })
                except Exception as card_err:
                    print(f"Error parsing Udemy card: {card_err}")
        except Exception as e:
            print(f"Error scraping Udemy: {e}")
        finally:
            driver.quit()
        return results

    async def search_youtube(self, query: str) -> list[dict]:
        """Scrapes YouTube search results with metadata using Edge."""
        return await asyncio.to_thread(self._fetch_youtube, query)

    def _fetch_youtube(self, query: str) -> list[dict]:
        driver = self._get_driver()
        results = []
        try:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            driver.get(url)
            time.sleep(5)
            
            videos = driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer")
            for video in videos[:5]:
                try:
                    title_elem = video.find_element(By.CSS_SELECTOR, "a#video-title")
                    title = title_elem.get_attribute("title") or title_elem.text
                    url = title_elem.get_attribute("href")
                    
                    channel_elem = video.find_elements(By.CSS_SELECTOR, "ytd-channel-name a, #channel-info a")
                    channel = channel_elem[0].text if channel_elem else ""
                    
                    meta_elem = video.find_elements(By.CSS_SELECTOR, "#metadata-line span")
                    meta_text = " • ".join(m.text for m in meta_elem if m.text) if meta_elem else ""
                    
                    if url and title:
                        results.append({
                            "title": title.strip(),
                            "url": url,
                            "platform": "YouTube",
                            "partner_creator": channel.strip() if channel else "YouTube Creator",
                            "rating": "N/A",
                            "duration_details": meta_text.strip() if meta_text else "N/A"
                        })
                except Exception as video_err:
                    pass
        except Exception as e:
            print(f"Error scraping YouTube: {e}")
        finally:
            driver.quit()
        return results

    async def search_all(self, query: str) -> dict[str, list[dict]]:
        """Queries all three platforms (Coursera, Udemy, YouTube) sequentially using Edge."""
        coursera_res = await self.search_coursera(query)
        udemy_res = await self.search_udemy(query)
        youtube_res = await self.search_youtube(query)
        return {
            "coursera": coursera_res,
            "udemy": udemy_res,
            "youtube": youtube_res
        }
