"""
comic-ebook-creator — CLI tool to crawl manga chapters and package them into EPUB.

Usage:
    python main.py --url <manga-index-url> --title <manga-title> [options]
"""

import argparse
import logging
import re
import subprocess
import sys
from pathlib import Path

from src.adapters.base import BaseAdapter
from src.adapters.onepiecetruyen import OnePieceTruyenAdapter
from src.downloader import Downloader
from src.manifest import Manifest
from src.packager import Packager

# All registered adapters — checked in order, first match wins
ADAPTERS: list[type[BaseAdapter]] = [
    OnePieceTruyenAdapter,
]


def setup_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def pick_adapter(url: str) -> BaseAdapter:
    for adapter_cls in ADAPTERS:
        if adapter_cls.matches(url):
            logging.info(f"Using adapter: {adapter_cls.__name__}")
            return adapter_cls()
    logging.warning("No matching adapter found — falling back to OnePieceTruyenAdapter")
    return OnePieceTruyenAdapter()


def load_chapters_from_file(path: Path) -> list[str]:
    urls = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def chapter_key(chapter_url: str, index: int) -> str:
    """Derive a zero-padded chapter key from URL or fallback to index."""
    match = re.search(r"chapter[-_]?([\d]+(?:[._][\d]+)?)", chapter_url, re.I)
    if match:
        raw = match.group(1).replace(".", "_")
        num = float(raw.replace("_", "."))
        if num == int(num):
            return f"{int(num):03d}"
        return f"{int(num):03d}_{str(num).split('.')[1]}"
    return f"{index:03d}"


def _count_folder_images(folder) -> int:
    if folder is None or not folder.exists():
        return 0
    from src.manifest import IMAGE_EXTS
    return sum(1 for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS and f.stat().st_size > 0)


def _pack_cbz(chapter_folders: list[Path], cbz_path: Path) -> int:
    """Pack downloaded images into CBZ for KCC. Returns image count.

    KCC does not support WebP — convert to JPEG in-memory before writing.
    """
    import zipfile as _zf
    from PIL import Image
    from io import BytesIO

    count = 0
    with _zf.ZipFile(cbz_path, "w", _zf.ZIP_STORED) as zf:
        for ch_folder in chapter_folders:
            for img_path in sorted(ch_folder.iterdir()):
                ext = img_path.suffix.lower()
                if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                    continue
                if ext == ".webp":
                    with Image.open(img_path) as img:
                        buf = BytesIO()
                        img.convert("RGB").save(buf, "JPEG", quality=92)
                        zf.writestr(f"{count:05d}.jpg", buf.getvalue())
                else:
                    zf.write(img_path, f"{count:05d}{ext}")
                count += 1
    return count


def _find_kindle_previewer() -> str | None:
    """Find Kindle Previewer 3 executable on Windows."""
    import os
    base_dirs = [
        os.path.expandvars(r"%LOCALAPPDATA%\Amazon\Kindle Previewer 3"),
        r"C:\Program Files\Amazon\Kindle Previewer 3",
        r"C:\Program Files (x86)\Amazon\Kindle Previewer 3",
    ]
    # Amazon ships it as "Kindle Previewer 3.exe" (with spaces)
    exe_names = ["Kindle Previewer 3.exe", "KindlePreviewer.exe", "kindlepreviewer.exe"]
    for base in base_dirs:
        for exe in exe_names:
            p = Path(base) / exe
            if p.exists():
                return str(p)
    return None


def convert_to_azw3(
    epub_path: Path,
    chapter_folders: list[Path],
    log,
) -> Path | None:
    """
    Convert to Kindle AZW3/MOBI. Returns output path on success, None on failure.

    Kindle reads AZW3/MOBI/KFX via USB — EPUB is NOT supported via USB copy.

    Strategy (in order):
    1. Kindle Previewer 3 CLI: converts our fixed-layout EPUB → AZW3 directly.
       Best option: KP3 preserves fixed-layout properties → full-bleed on Kindle.
       Install KP3 (free, official): https://www.amazon.com/gp/feature.html?ie=UTF8&docId=1000765261
    2. Calibre CBZ→MOBI fallback: creates "Text Type" MOBI (margins ~1cm).
    """
    import zipfile as _zf

    abs_epub = epub_path.resolve()
    out_dir  = abs_epub.parent
    azw3_path = abs_epub.with_suffix(".azw3")
    mobi_path = abs_epub.with_suffix(".mobi")

    # ------------------------------------------------------------------ #
    # Path 1 — Kindle Previewer 3 CLI: fixed-layout EPUB → AZW3          #
    # ------------------------------------------------------------------ #
    kp3_exe = _find_kindle_previewer()
    if kp3_exe:
        before = {f.resolve() for f in out_dir.glob("*.azw3")}
        try:
            result = subprocess.run(
                [kp3_exe, "-convert", str(abs_epub), "-output", str(out_dir)],
                capture_output=True, text=True, timeout=300,
            )
            after = {f.resolve() for f in out_dir.glob("*.azw3")}
            new_azw3 = after - before
            if result.returncode == 0 and new_azw3:
                kp3_out = new_azw3.pop()
                kp3_out.rename(azw3_path)
                log.info(f"AZW3 created via Kindle Previewer 3 (full-bleed): {azw3_path.name}")
                return azw3_path
            log.warning(
                f"Kindle Previewer conversion failed (rc={result.returncode})\n"
                f"stdout: {result.stdout[:300]}"
            )
        except subprocess.TimeoutExpired:
            log.warning("Kindle Previewer timed out")
        except Exception as exc:
            log.warning(f"Kindle Previewer error: {exc}")
        log.info("Falling back to Calibre (MOBI with ~1cm margins)")
    else:
        log.info(
            "Kindle Previewer 3 not found — install for full-bleed AZW3 output:\n"
            "  https://www.amazon.com/gp/feature.html?ie=UTF8&docId=1000765261\n"
            "Falling back to Calibre (MOBI with ~1cm margins)"
        )

    # ------------------------------------------------------------------ #
    # Path 2 — Calibre CBZ→MOBI fallback (margins ~1cm on Kindle)        #
    # ------------------------------------------------------------------ #
    cbz_path = out_dir / (abs_epub.stem + "_cal_in.cbz")
    try:
        with _zf.ZipFile(abs_epub, "r") as epub_zip:
            image_names = sorted(
                n for n in epub_zip.namelist()
                if "/images/" in n and n.lower().endswith((".jpg", ".jpeg", ".png"))
            )
            if not image_names:
                log.error(f"No images found inside {abs_epub.name}")
                return None
            with _zf.ZipFile(cbz_path, "w", _zf.ZIP_STORED) as cbz:
                for i, name in enumerate(image_names):
                    cbz.writestr(f"{i:05d}.jpg", epub_zip.read(name))
    except Exception as exc:
        log.error(f"CBZ creation failed: {exc}")
        cbz_path.unlink(missing_ok=True)
        return None

    try:
        result = subprocess.run(
            [
                "ebook-convert", str(cbz_path), str(mobi_path),
                "--output-profile", "kindle_pw3",
                "--no-inline-toc",
            ],
            capture_output=True, text=True, timeout=300,
        )
    except FileNotFoundError:
        cbz_path.unlink(missing_ok=True)
        log.error("ebook-convert not found. Install Calibre: https://calibre-ebook.com/download")
        return None
    except subprocess.TimeoutExpired:
        cbz_path.unlink(missing_ok=True)
        log.error("ebook-convert timed out")
        return None
    finally:
        cbz_path.unlink(missing_ok=True)

    if result.returncode == 0:
        log.info(f"MOBI created via Calibre (margins ~1cm): {mobi_path.name}")
        return mobi_path
    log.error(f"ebook-convert failed:\n{result.stderr[-500:]}")
    return None


def _key_num(key: str) -> float:
    """Convert chapter key ('001', '1000', '100_5') to float for numeric comparison."""
    return float(key.replace("_", "."))


def _parse_epub_range(stem: str) -> tuple[str, str] | None:
    """
    Parse (start_key, end_key) from an EPUB stem.
    Handles both plain ('title_ch001-010') and device-suffixed ('title_ch001-010_kindle').
    """
    if "_ch" not in stem:
        return None
    range_part = stem.split("_ch")[-1]   # "001-010" or "001-010_kindle"
    range_part = range_part.split("_")[0]  # strip optional device suffix → "001-010"
    parts = range_part.split("-")
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _invalidate_epub_for_chapter(chapter_key: str, manifest, output_dir: Path, title: str, log) -> None:
    """
    When a previously-packed chapter is re-downloaded, find all EPUBs (and AZW3s)
    that contain it (including device-suffixed variants), delete them, and reset all
    chapters in that batch to 'downloaded' so the pack phase regenerates correct files.
    """
    for epub_path in output_dir.glob(f"{title}_ch*.epub"):
        parsed = _parse_epub_range(epub_path.stem)
        if parsed is None:
            continue
        start_key, end_key = parsed
        if _key_num(start_key) <= _key_num(chapter_key) <= _key_num(end_key):
            log.info(f"Deleting stale EPUB: {epub_path.name} (chapter {chapter_key} was updated)")
            epub_path.unlink()
            for stale_ext in (".azw3", ".mobi"):
                stale = epub_path.with_suffix(stale_ext)
                if stale.exists():
                    log.info(f"Deleting stale {stale_ext[1:].upper()}: {stale.name}")
                    stale.unlink()
            packed_in_batch = [
                k for k in manifest.get_packed_chapters()
                if _key_num(start_key) <= _key_num(k) <= _key_num(end_key)
            ]
            if packed_in_batch:
                manifest.reset_to_downloaded(packed_in_batch)
            # Keep scanning — there may be multiple device variants of the same batch


def _reset_missing_epubs(
    manifest, output_dir: Path, title: str, range_keys: list[str], log
) -> None:
    """
    For packed chapters in the current run's range, check whether an EPUB or AZW3
    file actually covers each one. Reset uncovered chapters back to 'downloaded'.

    Intentionally batch_size-independent: scans existing filenames instead
    of recomputing expected paths. This prevents runaway resets when a user
    passes --batch-size that differs from the original packing run.
    """
    packed_in_range = [k for k in range_keys if manifest.is_packed(k)]
    if not packed_in_range:
        return

    # Build coverage from actual EPUB and AZW3 files on disk (any device variant counts)
    covered: set[str] = set()
    for pattern in (f"{title}_ch*.epub", f"{title}_ch*.azw3", f"{title}_ch*.mobi"):
        for output_file in output_dir.glob(pattern):
            parsed = _parse_epub_range(output_file.stem)
            if parsed is None:
                continue
            start_key, end_key = parsed
            for key in packed_in_range:
                if _key_num(start_key) <= _key_num(key) <= _key_num(end_key):
                    covered.add(key)

    uncovered = [k for k in packed_in_range if k not in covered]
    if uncovered:
        log.info(f"EPUB missing for {len(uncovered)} chapter(s) in range, resetting to re-pack")
        manifest.reset_to_downloaded(uncovered)


def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir) / args.title
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(output_dir)

    log = logging.getLogger(__name__)
    error_log = output_dir / "errors.log"

    from src.packager import DEVICE_PROFILES
    devices = list(DEVICE_PROFILES.keys()) if args.target_device == "both" else [args.target_device]

    adapter = pick_adapter(args.url)
    manifest = Manifest(output_dir, args.title)
    downloader = Downloader(output_dir, delay=args.delay, error_log=error_log)
    packager = Packager(output_dir, args.title, devices=devices, fit_mode=args.fit_mode)

    if args.force_repack:
        deleted = []
        for pattern in (f"{args.title}_ch*.epub", f"{args.title}_ch*.azw3", f"{args.title}_ch*.mobi"):
            for f in output_dir.glob(pattern):
                f.unlink()
                deleted.append(f.name)
        if deleted:
            log.info(f"--force-repack: deleted {len(deleted)} file(s): {', '.join(deleted)}")
            manifest.reset_to_downloaded(manifest.get_packed_chapters())
        else:
            log.info("--force-repack: no existing output files found")

    # --- Gather chapter URLs ---
    if args.chapters_file:
        log.info(f"Loading chapters from file: {args.chapters_file}")
        all_chapter_urls = load_chapters_from_file(Path(args.chapters_file))
    else:
        all_chapter_urls = adapter.get_chapter_urls(args.url)

    if not all_chapter_urls:
        log.error("No chapter URLs found. Exiting.")
        sys.exit(1)

    # --- Apply chapter range filter ---
    start = args.start_chapter - 1  # 0-based
    end = args.end_chapter if args.end_chapter else len(all_chapter_urls)
    chapter_urls = all_chapter_urls[start:end]
    log.info(f"Processing {len(chapter_urls)} chapters (total found: {len(all_chapter_urls)})")

    # --- Download phase ---
    newly_downloaded: list[str] = []
    for idx, ch_url in enumerate(chapter_urls, start=start + 1):
        key = chapter_key(ch_url, idx)

        if manifest.is_downloaded(key):
            if manifest.is_images_complete(key):
                status = "packed" if manifest.is_packed(key) else "downloaded"
                total = manifest.get_total_pages(key)
                log.info(f"[{key}] Already {status} ({total} pages), skipping")
                continue
            else:
                actual = _count_folder_images(manifest.get_folder(key))
                total = manifest.get_total_pages(key)
                if total is None:
                    log.info(f"[{key}] total_pages not recorded — re-probing CDN to verify ({actual} images on disk)")
                else:
                    log.warning(f"[{key}] Incomplete ({actual}/{total} pages) — downloading missing")

        log.info(f"[{key}] Fetching image list: {ch_url}")
        image_urls = adapter.get_page_image_urls(ch_url)

        if not image_urls:
            log.warning(f"[{key}] No images found, skipping")
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"[SKIP-CHAPTER] {ch_url} - no images found\n")
            continue

        was_packed = manifest.is_packed(key)
        ch_folder, saved = downloader.download_chapter(key, ch_url, image_urls)
        if saved > 0:
            manifest.set_downloaded(key, ch_url, ch_folder, saved, total=len(image_urls))
            newly_downloaded.append(key)
            log.info(f"[{key}] Images ready: {saved}/{len(image_urls)}")
            if was_packed:
                _invalidate_epub_for_chapter(key, manifest, output_dir, args.title, log)
        else:
            log.warning(f"[{key}] No images saved")

    # --- Repair: reset chapters in range whose EPUB is missing ---
    range_keys = [chapter_key(u, i) for i, u in enumerate(chapter_urls, start=start + 1)]
    _reset_missing_epubs(manifest, output_dir, args.title, range_keys, log)

    # --- Pack phase: only consider chapters within the current run's range ---
    # Pooling ALL downloaded chapters across the entire manga causes chapters
    # from different ranges to bleed into the same batch when there are gaps.
    range_key_set = set(range_keys)
    all_ready = [k for k in manifest.get_downloaded_chapters() if k in range_key_set]
    if not all_ready:
        existing_epubs = sorted(output_dir.glob("*.epub"))
        if existing_epubs:
            log.info("All chapters already packed. Existing EPUBs:")
            for ep in existing_epubs:
                log.info(f"  {ep.name} ({ep.stat().st_size // 1024} KB)")
        else:
            log.info("No chapters ready to pack. Download some chapters first.")
        return

    batch_size = args.batch_size
    for batch_start in range(0, len(all_ready), batch_size):
        batch_keys = all_ready[batch_start : batch_start + batch_size]
        if len(batch_keys) < batch_size:
            log.info(
                f"Batch {batch_keys[0]}-{batch_keys[-1]} has only {len(batch_keys)} chapters "
                f"(need {batch_size} for a full batch) — will pack when more chapters are downloaded"
            )
            # Pack partial batch only if these are the last chapters available
            if batch_start + batch_size >= len(all_ready) and args.end_chapter:
                log.info("Packing final (partial) batch...")
            else:
                continue

        folders = [manifest.get_folder(k) for k in batch_keys]
        missing = [k for k, f in zip(batch_keys, folders) if f is None or not f.exists()]
        if missing:
            log.warning(f"Missing folders for chapters: {missing}, skipping batch")
            continue

        log.info(f"Packing chapters {batch_keys[0]}-{batch_keys[-1]} -> EPUB")
        epub_paths = packager.pack(batch_keys, [f for f in folders if f])
        manifest.set_packed(batch_keys)
        for ep in epub_paths:
            log.info(f"Created: {ep}")

        if args.output_format in ("azw3", "both"):
            folders_list = [f for f in folders if f]
            for ep in epub_paths:
                mobi = convert_to_azw3(ep, folders_list, log)
                if mobi and args.output_format == "azw3":
                    ep.unlink(missing_ok=True)
                    log.info(f"Removed intermediate EPUB: {ep.name}")

    log.info("Done.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl manga chapters and package them into EPUB files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", required=True, help="Manga index page URL")
    parser.add_argument("--title", required=True, help="Manga title (used for folder and file names)")
    parser.add_argument("--chapters-file", help="Plain-text file with one chapter URL per line")
    parser.add_argument("--batch-size", type=int, default=10, help="Chapters per EPUB (default: 10)")
    parser.add_argument("--start-chapter", type=int, default=1, help="First chapter to process (1-based)")
    parser.add_argument("--end-chapter", type=int, default=None, help="Last chapter to process (inclusive)")
    parser.add_argument("--output-dir", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests in seconds (default: 1.5)")
    parser.add_argument(
        "--target-device",
        choices=["kindle", "kobo", "both"],
        default="both",
        help="Target e-reader device for image sizing (default: both — creates one EPUB per device)",
    )
    parser.add_argument(
        "--fit-mode",
        choices=["letterbox", "fill", "stretch"],
        default="letterbox",
        help=(
            "How to fit images to screen (default: letterbox). "
            "letterbox: preserve aspect ratio, add black bars if needed. "
            "fill: scale to fill screen width, crop top/bottom if needed. "
            "stretch: scale to fit full screen height, stretch width to fill — no bars, no crop, slight horizontal distortion."
        ),
    )
    parser.add_argument(
        "--force-repack",
        action="store_true",
        default=False,
        help="Delete all existing EPUBs/AZW3s for this title and re-pack from downloaded images.",
    )
    parser.add_argument(
        "--output-format",
        choices=["epub", "azw3", "both"],
        default="epub",
        help=(
            "Output format (default: epub). "
            "azw3: convert to AZW3 via Calibre ebook-convert, delete intermediate EPUB. "
            "both: keep EPUB and also produce AZW3. "
            "Requires Calibre installed: https://calibre-ebook.com/download"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
