import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


class Downloader:
    def __init__(
        self,
        output_dir: Path,
        delay: float = 1.5,
        error_log: Path | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._delay = delay
        self._error_log = error_log or (output_dir / "errors.log")
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    def download_chapter(
        self,
        chapter_key: str,
        chapter_url: str,
        image_urls: list[str],
    ) -> tuple[Path, int]:
        """
        Download all images for a chapter into output_dir/ch-<key>/.
        File extension is taken from the source URL (e.g. .webp, .jpg).
        Returns (chapter_folder, number_of_images_saved).
        Skips corrupt/zero-byte images and logs them.
        """
        chapter_dir = self._output_dir / f"ch-{chapter_key}"
        chapter_dir.mkdir(parents=True, exist_ok=True)

        saved = 0
        for idx, url in enumerate(image_urls, start=1):
            ext = _ext_from_url(url)
            filename = chapter_dir / f"{idx:03d}{ext}"

            if _page_already_exists(chapter_dir, idx):
                logger.debug(f"Skip existing: page {idx:03d}")
                saved += 1
                continue

            success = self._download_image(url, filename, chapter_url)
            if success:
                saved += 1

            time.sleep(random.uniform(self._delay * 0.8, self._delay * 1.2))

        return chapter_dir, saved

    def _download_image(self, url: str, dest: Path, referer: str, max_retries: int = 3) -> bool:
        for attempt in range(1, max_retries + 1):
            try:
                resp = self._session.get(
                    url,
                    timeout=20,
                    headers={"Referer": referer},
                    stream=True,
                )
                resp.raise_for_status()

                raw = resp.content
                if len(raw) == 0:
                    raise requests.RequestException("Zero-byte response")

                dest.write_bytes(raw)
                self._validate_image(dest, url)
                return True

            except _CorruptImageError:
                return False
            except requests.RequestException as e:
                wait = 2 ** attempt
                if attempt < max_retries:
                    logger.warning(f"Attempt {attempt}/{max_retries} failed for {url}: {e} — retrying in {wait}s")
                    time.sleep(wait)
                else:
                    self._log_error(url, f"Failed after {max_retries} attempts: {e}")
        return False

    def _validate_image(self, path: Path, url: str) -> None:
        try:
            with Image.open(path) as img:
                img.verify()
        except (UnidentifiedImageError, Exception) as e:
            path.unlink(missing_ok=True)
            self._log_error(url, f"Corrupt image: {e}")
            raise _CorruptImageError()

    def _log_error(self, url: str, reason: str) -> None:
        logger.warning(f"Skipping {url}: {reason}")
        self._error_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self._error_log, "a", encoding="utf-8") as f:
            f.write(f"[SKIP] {url} - {reason}\n")


class _CorruptImageError(Exception):
    pass


def _ext_from_url(url: str) -> str:
    """Extract file extension from URL path. Defaults to .jpg."""
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"


def _page_already_exists(chapter_dir: Path, idx: int) -> bool:
    """Check if page N already downloaded under any supported extension."""
    for ext in (".webp", ".jpg", ".jpeg", ".png"):
        if (chapter_dir / f"{idx:03d}{ext}").exists():
            f = chapter_dir / f"{idx:03d}{ext}"
            if f.stat().st_size > 0:
                return True
    return False
