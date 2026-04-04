import httpx
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET
from urllib.parse import parse_qs, urlparse, unquote
from tools.base import BaseTool
from logger.logger import get_logger

logger = get_logger(__name__)


class CrawlerTool(BaseTool):
    name = "crawler"
    description = "Crawl a URL and extract text"
    description_ko = "웹 주소를 수집하고 텍스트 추출"
    description_en = "Crawl a URL and extract text"

    async def run(self, params: dict) -> dict:
        url: str = params.get("url", "")
        selector: str = params.get("selector", "")  # CSS selector (선택)

        if not url:
            return {"success": False, "data": None, "error": "url is required"}

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()

            rss_results = self._extract_rss_results(response.text, response.headers.get("content-type", ""))
            if rss_results:
                data = {"url": url, "text": self._format_rss_preview(rss_results), "links": rss_results}
                return {"success": True, "data": data, "error": None}

            soup = BeautifulSoup(response.text, "html.parser")
            search_results = self._extract_search_results(url, soup)

            if selector:
                elements = soup.select(selector)
                text = "\n".join(el.get_text(strip=True) for el in elements)
            else:
                # 불필요한 태그 제거 후 본문 텍스트 추출
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)

            data = {"url": url, "text": text[:5000]}
            if search_results:
                data["links"] = search_results

            return {"success": True, "data": data, "error": None}

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "data": None,
                "error": f"웹 페이지를 불러오지 못했습니다. 사이트가 HTTP {e.response.status_code} 를 반환했습니다.",
            }
        except httpx.RequestError:
            return {
                "success": False,
                "data": None,
                "error": "외부 웹사이트에 연결하지 못했습니다. 네트워크 상태나 사이트 접근 가능 여부를 확인해주세요.",
            }
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    def _extract_search_results(self, url: str, soup: BeautifulSoup) -> list[dict]:
        parsed = urlparse(url)
        hostname = parsed.netloc.lower()
        if "google." not in hostname and "search.naver.com" not in hostname:
            return []

        results: list[dict] = []
        seen: set[str] = set()

        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "").strip()
            title = anchor.get_text(" ", strip=True)
            if not href or not title:
                continue

            link = self._normalize_search_link(href, hostname)
            if not link:
                continue
            if link in seen:
                continue
            if len(title) < 3:
                continue

            seen.add(link)
            results.append(
                {
                    "title": title[:140],
                    "url": link,
                }
            )
            if len(results) >= 8:
                break

        return results

    def _extract_rss_results(self, body: str, content_type: str) -> list[dict]:
        if "xml" not in content_type.lower() and "<rss" not in body[:200].lower():
            return []

        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []

        results: list[dict] = []
        seen: set[str] = set()
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link or link in seen:
                continue
            seen.add(link)
            results.append({"title": title[:140], "url": link})
            if len(results) >= 8:
                break
        return results

    def _format_rss_preview(self, results: list[dict]) -> str:
        lines = []
        for index, item in enumerate(results, start=1):
            lines.append(f"{index}. {item['title']}")
        return "\n".join(lines[:8])

    def _normalize_search_link(self, href: str, hostname: str) -> str | None:
        if href.startswith("/url?") and "google." in hostname:
            query = parse_qs(urlparse(href).query)
            target = query.get("q", [None])[0]
            if target:
                return unquote(target)
            return None

        if href.startswith("http://") or href.startswith("https://"):
            blocked_hosts = ("google.", "accounts.google.", "support.google.", "maps.google.")
            parsed = urlparse(href)
            host = parsed.netloc.lower()
            if any(part in host for part in blocked_hosts):
                return None
            return href

        return None
