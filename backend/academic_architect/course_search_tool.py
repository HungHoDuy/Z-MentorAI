import asyncio
import json
import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup

class CourseSearchTool:
    def __init__(self):
        # Using a standard browser User-Agent to prevent basic request rejection
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _decode_ddg_url(self, url: str) -> str:
        """Decodes the actual URL from DuckDuckGo's redirection wrapper if present."""
        if not url:
            return ""
        if "/l/?uddg=" in url:
            try:
                parsed_url = urllib.parse.urlparse(url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                if "uddg" in query_params:
                    return query_params["uddg"][0]
            except Exception:
                pass
        return url

    async def search_coursera(self, query: str) -> list[dict]:
        """Searches Coursera courses via DuckDuckGo HTML search restricted to site:coursera.org/learn/."""
        try:
            search_query = f"site:coursera.org/learn/ {query}"
            encoded_query = urllib.parse.quote(search_query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    results = []
                    
                    # Iterate through search results
                    for result_div in soup.find_all("div", class_="result"):
                        # Extract title and URL anchor
                        title_anchor = result_div.find("a", class_="result__title")
                        url_anchor = result_div.find("a", class_="result__url")
                        snippet_elem = result_div.find("a", class_="result__snippet")
                        
                        href = ""
                        if title_anchor:
                            href = title_anchor.get("href", "")
                        elif url_anchor:
                            href = url_anchor.get("href", "")
                        
                        actual_url = self._decode_ddg_url(href)
                        
                        if "coursera.org/learn/" in actual_url:
                            # Clean course title
                            title = ""
                            if title_anchor:
                                title = title_anchor.get_text(strip=True)
                            if not title:
                                # Fallback from URL slug
                                slug = actual_url.rstrip("/").split("/")[-1]
                                title = slug.replace("-", " ").title()
                            
                            # Clean description
                            description = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            
                            results.append({
                                "title": title,
                                "url": actual_url,
                                "platform": "Coursera",
                                "description": description[:200] + ("..." if len(description) > 200 else "")
                            })
                            if len(results) >= 5:
                                break
                    return results
                else:
                    print(f"Coursera DDG search returned status code {res.status_code}")
        except Exception as e:
            print(f"Error searching Coursera: {e}")
        return []

    async def search_udemy(self, query: str) -> list[dict]:
        """Searches Udemy courses via DuckDuckGo HTML search restricted to site:udemy.com/course/."""
        try:
            search_query = f"site:udemy.com/course/ {query}"
            encoded_query = urllib.parse.quote(search_query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    results = []
                    
                    # Iterate through search results
                    for result_div in soup.find_all("div", class_="result"):
                        # Extract title and URL anchor
                        title_anchor = result_div.find("a", class_="result__title")
                        url_anchor = result_div.find("a", class_="result__url")
                        snippet_elem = result_div.find("a", class_="result__snippet")
                        
                        href = ""
                        if title_anchor:
                            href = title_anchor.get("href", "")
                        elif url_anchor:
                            href = url_anchor.get("href", "")
                        
                        actual_url = self._decode_ddg_url(href)
                        
                        if "udemy.com/course/" in actual_url:
                            # Clean course title
                            title = ""
                            if title_anchor:
                                title = title_anchor.get_text(strip=True)
                            if not title:
                                # Fallback from URL slug
                                slug = actual_url.rstrip("/").split("/")[-1]
                                title = slug.replace("-", " ").title()
                            
                            # Clean description
                            description = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            
                            results.append({
                                "title": title,
                                "url": actual_url,
                                "platform": "Udemy",
                                "description": description[:200] + ("..." if len(description) > 200 else "")
                            })
                            if len(results) >= 5:
                                break
                    return results
        except Exception as e:
            print(f"Error searching Udemy: {e}")
        return []

    async def search_youtube(self, query: str) -> list[dict]:
        """Searches YouTube using unauthenticated desktop JSON extraction with DuckDuckGo fallback."""
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded_query}"
            
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    # Extract the ytInitialData JSON object which contains all page search results
                    match = re.search(r"var ytInitialData\s*=\s*({.+?});", res.text)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            results = []
                            # Drill down to find videoRenderer objects
                            contents = data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"]
                            for section in contents:
                                item_section = section.get("itemSectionRenderer", {})
                                for item in item_section.get("contents", []):
                                    if "videoRenderer" in item:
                                        video = item["videoRenderer"]
                                        video_id = video.get("videoId")
                                        
                                        # Get Title
                                        title_runs = video.get("title", {}).get("runs", [])
                                        title = title_runs[0].get("text", "") if title_runs else ""
                                        
                                        # Get Snippet/Description
                                        desc_runs = video.get("detailedMetadataSnippets", [{}])[0].get("snippetText", {}).get("runs", [])
                                        description = "".join(r.get("text", "") for r in desc_runs) if desc_runs else ""
                                        
                                        if video_id and title:
                                            results.append({
                                                "title": title,
                                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                                "platform": "YouTube",
                                                "description": description[:200] + ("..." if len(description) > 200 else "")
                                            })
                                        if len(results) >= 5:
                                            break
                                if len(results) >= 5:
                                    break
                            
                            if results:
                                return results
                        except Exception as parse_err:
                            print(f"Error parsing YouTube JSON data: {parse_err}")
        except Exception as e:
            print(f"Error searching YouTube directly: {e}")
            
        # Fall back to DuckDuckGo search for YouTube videos
        return await self._search_youtube_fallback(query)

    async def _search_youtube_fallback(self, query: str) -> list[dict]:
        """Fallback to search YouTube videos via DuckDuckGo HTML search."""
        try:
            search_query = f"site:youtube.com/watch {query}"
            encoded_query = urllib.parse.quote(search_query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    results = []
                    
                    for result_div in soup.find_all("div", class_="result"):
                        title_anchor = result_div.find("a", class_="result__title")
                        url_anchor = result_div.find("a", class_="result__url")
                        snippet_elem = result_div.find("a", class_="result__snippet")
                        
                        href = ""
                        if title_anchor:
                            href = title_anchor.get("href", "")
                        elif url_anchor:
                            href = url_anchor.get("href", "")
                            
                        actual_url = self._decode_ddg_url(href)
                        
                        if "youtube.com/watch" in actual_url:
                            title = title_anchor.get_text(strip=True) if title_anchor else "YouTube Video"
                            description = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            
                            results.append({
                                "title": title,
                                "url": actual_url,
                                "platform": "YouTube",
                                "description": description[:200] + ("..." if len(description) > 200 else "")
                            })
                            if len(results) >= 5:
                                break
                    return results
        except Exception as e:
            print(f"Error in YouTube fallback search: {e}")
        return []

    async def search_all(self, query: str) -> dict[str, list[dict]]:
        """Queries all three platforms (Coursera, Udemy, YouTube) with a brief delay to prevent DDG rate limits."""
        coursera_res = await self.search_coursera(query)
        await asyncio.sleep(0.5)
        udemy_res = await self.search_udemy(query)
        await asyncio.sleep(0.5)
        youtube_res = await self.search_youtube(query)
        return {
            "coursera": coursera_res,
            "udemy": udemy_res,
            "youtube": youtube_res
        }

# Simple standalone test script
if __name__ == "__main__":
    async def main():
        searcher = CourseSearchTool()
        print("Testing course search for 'Python Programming'...")
        results = await searcher.search_all("Python Programming")
        print(json.dumps(results, indent=2))
        
    asyncio.run(main())
