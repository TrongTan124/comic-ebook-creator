import logging
import uuid
from pathlib import Path

from ebooklib import epub
from PIL import Image

logger = logging.getLogger(__name__)


class Packager:
    """Packages downloaded chapter folders into EPUB files."""

    def __init__(self, output_dir: Path, title: str) -> None:
        self._output_dir = output_dir
        self._title = title

    def pack(self, chapter_keys: list[str], chapter_folders: list[Path]) -> Path:
        """
        Create one EPUB from the given chapters.
        chapter_keys: e.g. ["001", "002", ..., "010"]
        chapter_folders: matching list of chapter dirs containing images
        Returns path to the created EPUB file.
        """
        start = chapter_keys[0]
        end = chapter_keys[-1]
        epub_name = f"{self._title}_ch{start}-{end}.epub"
        epub_path = self._output_dir / epub_name

        book = epub.EpubBook()
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(f"{self._title} Ch.{start}-{end}")
        book.set_language("vi")

        spine: list = ["nav"]
        toc: list = []

        for ch_key, ch_folder in zip(chapter_keys, chapter_folders):
            chapter_pages = self._collect_pages(ch_folder)
            if not chapter_pages:
                logger.warning(f"No images found in {ch_folder}, skipping chapter {ch_key}")
                continue

            chapter_html_items = []
            for page_idx, img_path in enumerate(chapter_pages, start=1):
                img_item, html_item = self._add_page(book, ch_key, page_idx, img_path)
                chapter_html_items.append(html_item)
                spine.append(html_item)

            if chapter_html_items:
                toc.append(
                    epub.Link(
                        chapter_html_items[0].file_name,
                        f"Chapter {ch_key}",
                        f"ch{ch_key}",
                    )
                )

        book.toc = toc
        book.spine = spine
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        epub.write_epub(str(epub_path), book)
        logger.info(f"EPUB created: {epub_path}")
        return epub_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _collect_pages(self, folder: Path) -> list[Path]:
        images = sorted(
            p for p in folder.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )
        return images

    def _add_page(
        self,
        book: epub.EpubBook,
        ch_key: str,
        page_idx: int,
        img_path: Path,
    ) -> tuple[epub.EpubImage, epub.EpubHtml]:
        # Determine media type
        suffix = img_path.suffix.lower()
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")

        img_name = f"images/ch{ch_key}_{page_idx:03d}{suffix}"

        # Convert webp to jpeg for maximum compatibility
        img_data = self._read_image(img_path, convert_to_jpeg=(suffix == ".webp"))
        if suffix == ".webp":
            img_name = img_name.replace(".webp", ".jpg")
            media_type = "image/jpeg"

        img_item = epub.EpubImage()
        img_item.file_name = img_name
        img_item.media_type = media_type
        img_item.content = img_data
        book.add_item(img_item)

        # HTML wrapper — manga pages are usually full-width.
        # No XML declaration: lxml's HTML parser rejects it when ebooklib calls get_body_content().
        html_content = (
            f'<html xmlns="http://www.w3.org/1999/xhtml">'
            f'<head><title>Chapter {ch_key} Page {page_idx}</title>'
            f'<style>body{{margin:0;padding:0;text-align:center;background:#000}}'
            f'img{{max-width:100%;height:auto}}</style></head>'
            f'<body><img src="../{img_name}" alt="Ch{ch_key} P{page_idx}"/></body>'
            f'</html>'
        )
        html_item = epub.EpubHtml(
            title=f"Ch{ch_key} P{page_idx}",
            file_name=f"text/ch{ch_key}_p{page_idx:03d}.xhtml",
            lang="vi",
        )
        html_item.content = html_content
        book.add_item(html_item)

        return img_item, html_item

    @staticmethod
    def _read_image(path: Path, convert_to_jpeg: bool = False) -> bytes:
        if convert_to_jpeg:
            from io import BytesIO
            buf = BytesIO()
            with Image.open(path) as img:
                img.convert("RGB").save(buf, format="JPEG", quality=90)
            return buf.getvalue()
        return path.read_bytes()
