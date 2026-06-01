import re
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from .base import BaseAdapter

logger = logging.getLogger(__name__)

SITE_DOMAIN = "onepiecetruyen.net"
BASE_URL = "https://onepiecetruyen.net"
CHAPTERS_INDEX = f"{BASE_URL}/chapters"
CDN_BASE = "https://cdn.onepiecetruyen.net/one-piece/vi"


class OnePieceTruyenAdapter(BaseAdapter):
    """
    Adapter for onepiecetruyen.net (Next.js site).

    Chapter discovery:
      The /chapters page shows only recent entries — no full pagination.
      URL structure is sequential: /chapters/chapter-{N}
      We detect max chapter from the index page, then generate URLs 1..N.

    Image discovery:
      The chapter page lazy-loads images via JavaScript as the user scrolls.
      Static HTML only contains the first ~7 images, missing the rest.
      Solution: probe the CDN directly with sequential HEAD requests.
      CDN pattern: cdn.onepiecetruyen.net/one-piece/vi/chapter-{N}/{page:03d}.webp
      Stop when 404 is returned.
    """

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)
        self._session.headers["Referer"] = f"{BASE_URL}/"

    @classmethod
    def matches(cls, url: str) -> bool:
        return SITE_DOMAIN in urlparse(url).netloc

    def get_chapter_urls(self, index_url: str) -> list[str]:
        logger.info(f"Detecting latest chapter from: {CHAPTERS_INDEX}")
        max_chapter = self._detect_max_chapter()
        if max_chapter == 0:
            logger.error("Could not determine chapter count. Use --chapters-file as fallback.")
            return []
        logger.info(f"Generating {max_chapter} chapter URLs (chapter-1 to chapter-{max_chapter})")
        return [f"{BASE_URL}/chapters/chapter-{n}" for n in range(1, max_chapter + 1)]

    def get_page_image_urls(self, chapter_url: str) -> list[str]:
        """
        Discover all page images by probing the CDN sequentially.
        The chapter page lazy-loads via JS so scraping HTML is unreliable.
        Instead we HEAD-request CDN URLs until 404.
        """
        chapter_num = self._extract_chapter_num(chapter_url)
        if not chapter_num:
            logger.error(f"Cannot extract chapter number from: {chapter_url}")
            return []

        cdn_chapter_base = f"{CDN_BASE}/chapter-{chapter_num}"
        logger.info(f"Probing CDN for chapter {chapter_num}: {cdn_chapter_base}/NNN.webp")

        urls = []
        consecutive_misses = 0

        for page in range(1, 600):
            url = f"{cdn_chapter_base}/{page:03d}.webp"
            try:
                resp = self._session.head(
                    url,
                    timeout=8,
                    headers={"Referer": chapter_url},
                    allow_redirects=True,
                )
                if resp.status_code == 200:
                    urls.append(url)
                    consecutive_misses = 0
                elif resp.status_code == 404:
                    consecutive_misses += 1
                    # Allow 1 gap (some chapters skip a page number) but stop after 2
                    if consecutive_misses >= 2:
                        break
                elif resp.status_code == 429:
                    logger.warning("CDN rate-limited, waiting 5s")
                    time.sleep(5)
                # Any other status: keep trying
            except requests.RequestException as e:
                logger.warning(f"CDN probe error at page {page}: {e}")
                break

        if urls:
            logger.info(f"Chapter {chapter_num}: {len(urls)} pages found")
        else:
            logger.warning(f"Chapter {chapter_num}: no pages found via CDN probe")
        return urls

    # ------------------------------------------------------------------

    def _detect_max_chapter(self) -> int:
        try:
            resp = self._session.get(CHAPTERS_INDEX, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch chapter list: {e}")
            return 0

        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.find_all("a", href=re.compile(r"/chapters/chapter-\d+"))
        nums = []
        for a in links:
            m = re.search(r"chapter-(\d+)", a.get("href", ""))
            if m:
                nums.append(int(m.group(1)))

        if not nums:
            logger.error("No chapter numbers found on /chapters page")
            return 0
        return max(nums)

    @staticmethod
    def _extract_chapter_num(chapter_url: str) -> str | None:
        m = re.search(r"chapter-(\d+)", chapter_url, re.I)
        return m.group(1) if m else None
