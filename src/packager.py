import logging
import uuid
from io import BytesIO
from pathlib import Path

from ebooklib import epub
from PIL import Image

logger = logging.getLogger(__name__)

# Screen dimensions (portrait) for supported e-reader devices
DEVICE_PROFILES: dict[str, dict[str, int]] = {
    "kindle": {"width": 1072, "height": 1448},  # Kindle Paperwhite 5
    "kobo":   {"width": 1264, "height": 1680},  # Kobo Libra 2
}


class Packager:
    """Packages downloaded chapter folders into EPUB files."""

    def __init__(
        self,
        output_dir: Path,
        title: str,
        devices: list[str] | None = None,
        fit_mode: str = "letterbox",
    ) -> None:
        self._output_dir = output_dir
        self._title = title
        self._fit_mode = fit_mode
        if fit_mode not in ("letterbox", "fill", "stretch"):
            raise ValueError(f"Unknown fit_mode '{fit_mode}'. Supported: letterbox, fill, stretch")
        # Default: all supported devices
        self._devices = devices if devices is not None else list(DEVICE_PROFILES.keys())
        for d in self._devices:
            if d not in DEVICE_PROFILES:
                raise ValueError(f"Unknown device '{d}'. Supported: {list(DEVICE_PROFILES)}")

    def pack(self, chapter_keys: list[str], chapter_folders: list[Path]) -> list[Path]:
        """
        Create one EPUB per target device from the given chapters.
        Returns list of paths to created EPUB files (one per device).
        """
        created: list[Path] = []
        # Use device suffix in filename only when producing multiple devices
        multi = len(self._devices) > 1
        for device in self._devices:
            profile = DEVICE_PROFILES[device]
            name_suffix = f"_{device}" if multi else ""
            epub_path = self._pack_for_device(chapter_keys, chapter_folders, profile, name_suffix)
            created.append(epub_path)
        return created

    # ------------------------------------------------------------------
    # Per-device EPUB builder
    # ------------------------------------------------------------------

    def _pack_for_device(
        self,
        chapter_keys: list[str],
        chapter_folders: list[Path],
        profile: dict[str, int],
        name_suffix: str,
    ) -> Path:
        start = chapter_keys[0]
        end = chapter_keys[-1]
        epub_name = f"{self._title}_ch{start}-{end}{name_suffix}.epub"
        epub_path = self._output_dir / epub_name

        dw, dh = profile["width"], profile["height"]

        book = epub.EpubBook()
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(f"{self._title} Ch.{start}-{end}")
        book.set_language("vi")

        # Fixed-layout metadata: one screen = one page, no scrolling
        book.add_metadata("OPF", "meta", "pre-paginated", {"property": "rendition:layout"})
        book.add_metadata("OPF", "meta", "none",          {"property": "rendition:spread"})
        book.add_metadata("OPF", "meta", "portrait",      {"property": "rendition:orientation"})

        cover_set = False
        spine: list = ["nav"]
        toc: list = []

        for ch_key, ch_folder in zip(chapter_keys, chapter_folders):
            chapter_pages = self._collect_pages(ch_folder)
            if not chapter_pages:
                logger.warning(f"No images found in {ch_folder}, skipping chapter {ch_key}")
                continue

            chapter_html_items: list[epub.EpubHtml] = []
            for page_idx, img_path in enumerate(chapter_pages, start=1):
                img_item, html_item = self._add_page(book, ch_key, page_idx, img_path, dw, dh, self._fit_mode)
                chapter_html_items.append(html_item)
                spine.append(html_item)

                # First page of first chapter becomes the library cover thumbnail
                if not cover_set:
                    cover_data = self._resize_for_device(img_path.read_bytes(), dw, dh, self._fit_mode)
                    book.set_cover("cover.jpg", cover_data, create_page=False)
                    cover_set = True

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
        return sorted(
            p for p in folder.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )

    def _add_page(
        self,
        book: epub.EpubBook,
        ch_key: str,
        page_idx: int,
        img_path: Path,
        device_width: int,
        device_height: int,
        fit_mode: str = "letterbox",
    ) -> tuple[epub.EpubImage, epub.EpubHtml]:
        img_name = f"images/ch{ch_key}_{page_idx:03d}.jpg"
        img_data = self._resize_for_device(img_path.read_bytes(), device_width, device_height, fit_mode)

        img_item = epub.EpubImage()
        img_item.file_name = img_name
        img_item.media_type = "image/jpeg"
        img_item.content = img_data
        book.add_item(img_item)

        # Fixed-layout page: dimensions match device exactly so there is no scrolling.
        # The image is already pixel-perfect after resize (black letterbox added in Python).
        html_content = (
            f'<html xmlns="http://www.w3.org/1999/xhtml"'
            f' xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><title>Chapter {ch_key} Page {page_idx}</title>'
            f'<meta name="viewport" content="width={device_width}, height={device_height}"/>'
            f'<style>'
            f'@page{{margin:0;padding:0}}'
            f'html,body{{margin:0;padding:0;width:{device_width}px;height:{device_height}px;overflow:hidden;background:#000}}'
            f'img{{width:{device_width}px;height:{device_height}px;display:block;margin:0;padding:0}}'
            f'</style></head>'
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
    def _resize_for_device(
        img_data: bytes,
        device_width: int,
        device_height: int,
        fit_mode: str = "letterbox",
    ) -> bytes:
        """
        Resize image for device screen.

        letterbox: scale to fit entirely within screen — preserves all content,
                   adds black bars on sides or top/bottom as needed.
        fill:      scale to fill full screen width — no side bars; crops top/bottom
                   symmetrically if image is taller than screen after scaling.
        stretch:   scale to fit full screen height, then stretch width to fill screen
                   — no black bars, no content loss; slight horizontal distortion.
                   Best for portrait manga pages narrower than the device screen.
        Always returns JPEG bytes at device_width x device_height.
        """
        with Image.open(BytesIO(img_data)) as img:
            img = img.convert("RGB")

            if fit_mode == "stretch":
                # Step 1: scale to fit height exactly
                new_h = device_height
                new_w = round(img.width * (device_height / img.height))
                height_fitted = img.resize((new_w, new_h), Image.LANCZOS)
                # Step 2: stretch (or crop) width to fill device width
                if new_w <= device_width:
                    # Portrait page narrower than device — stretch x to fill, no content loss
                    result = height_fitted.resize((device_width, device_height), Image.LANCZOS)
                else:
                    # Landscape page wider than device — crop sides symmetrically
                    x_start = (new_w - device_width) // 2
                    result = height_fitted.crop((x_start, 0, x_start + device_width, device_height))
            elif fit_mode == "fill":
                # Force exact device width — no floating-point rounding error
                new_w = device_width
                new_h = round(img.height * (device_width / img.width))
                resized = img.resize((new_w, new_h), Image.LANCZOS)
                if new_h > device_height:
                    # Crop symmetrically — keep center of the page
                    y_start = (new_h - device_height) // 2
                    result = resized.crop((0, y_start, device_width, y_start + device_height))
                else:
                    canvas = Image.new("RGB", (device_width, device_height), (0, 0, 0))
                    canvas.paste(resized, ((device_width - new_w) // 2, (device_height - new_h) // 2))
                    result = canvas
            else:  # letterbox
                scale = min(device_width / img.width, device_height / img.height)
                new_w = round(img.width * scale)
                new_h = round(img.height * scale)
                resized = img.resize((new_w, new_h), Image.LANCZOS)
                canvas = Image.new("RGB", (device_width, device_height), (0, 0, 0))
                canvas.paste(resized, ((device_width - new_w) // 2, (device_height - new_h) // 2))
                result = canvas

        buf = BytesIO()
        result.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
