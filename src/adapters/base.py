from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """Abstract base class for site-specific manga crawlers."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    }

    @abstractmethod
    def get_chapter_urls(self, index_url: str) -> list[str]:
        """Return ordered list of chapter URLs from a manga index page."""
        ...

    @abstractmethod
    def get_page_image_urls(self, chapter_url: str) -> list[str]:
        """Return ordered list of image URLs for a single chapter."""
        ...

    @classmethod
    def matches(cls, url: str) -> bool:
        """Return True if this adapter can handle the given URL."""
        return False
