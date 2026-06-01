import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "chapters.json"
IMAGE_EXTS = {".webp", ".jpg", ".jpeg", ".png"}


class Manifest:
    """
    Tracks download state for each chapter.

    Schema:
    {
        "title": "one-piece",
        "chapters": {
            "001": {
                "url": "https://...",
                "status": "downloaded" | "packed",
                "total_pages": 54,      <- from CDN probe (source of truth)
                "downloaded_pages": 54, <- actually saved to disk
                "folder": "output/one-piece/ch-001"
            }
        }
    }
    """

    def __init__(self, output_dir: Path, title: str) -> None:
        self._path = output_dir / MANIFEST_FILENAME
        self._title = title
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not read manifest, starting fresh: {e}")
        return {"title": self._title, "chapters": {}}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def is_in_manifest(self, chapter_key: str) -> bool:
        return chapter_key in self._data["chapters"]

    def is_downloaded(self, chapter_key: str) -> bool:
        entry = self._data["chapters"].get(chapter_key, {})
        return entry.get("status") in ("downloaded", "packed")

    def is_packed(self, chapter_key: str) -> bool:
        return self._data["chapters"].get(chapter_key, {}).get("status") == "packed"

    def is_images_complete(self, chapter_key: str) -> bool:
        """
        Return True only if total_pages (from CDN probe) is known AND
        all those pages are present on disk.
        Falls back to False for old manifest entries that only have image_count
        (which stored actual downloaded count, not true total — unreliable).
        """
        entry = self._data["chapters"].get(chapter_key, {})
        total = entry.get("total_pages")  # only trust CDN-sourced total
        if total is None:
            return False  # unknown total → assume incomplete, re-probe to verify

        folder = Path(entry.get("folder", ""))
        if not folder.exists():
            return False

        actual = _count_images(folder)
        return actual >= total

    def get_total_pages(self, chapter_key: str) -> int | None:
        entry = self._data["chapters"].get(chapter_key, {})
        return entry.get("total_pages") or entry.get("image_count")

    def get_folder(self, chapter_key: str) -> Path | None:
        entry = self._data["chapters"].get(chapter_key)
        if entry and entry.get("folder"):
            return Path(entry["folder"])
        return None

    def get_downloaded_chapters(self) -> list[str]:
        return sorted(
            k for k, v in self._data["chapters"].items()
            if v.get("status") == "downloaded"
        )

    def get_packed_chapters(self) -> list[str]:
        return sorted(
            k for k, v in self._data["chapters"].items()
            if v.get("status") == "packed"
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def set_downloaded(
        self,
        chapter_key: str,
        url: str,
        folder: Path,
        downloaded: int,
        total: int | None = None,
    ) -> None:
        self._data["chapters"][chapter_key] = {
            "url": url,
            "status": "downloaded",
            "total_pages": total,
            "downloaded_pages": downloaded,
            "folder": str(folder),
        }
        self.save()

    def set_packed(self, chapter_keys: list[str]) -> None:
        for key in chapter_keys:
            if key in self._data["chapters"]:
                self._data["chapters"][key]["status"] = "packed"
        self.save()

    def reset_to_downloaded(self, chapter_keys: list[str]) -> None:
        for key in chapter_keys:
            if self._data["chapters"].get(key, {}).get("status") == "packed":
                self._data["chapters"][key]["status"] = "downloaded"
        self.save()

    def reset_chapter(self, chapter_key: str) -> None:
        """Remove a chapter from manifest so it gets re-downloaded from scratch."""
        self._data["chapters"].pop(chapter_key, None)
        self.save()


def _count_images(folder: Path) -> int:
    return sum(
        1 for f in folder.iterdir()
        if f.suffix.lower() in IMAGE_EXTS and f.stat().st_size > 0
    )
