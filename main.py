"""
comic-ebook-creator — CLI tool to crawl manga chapters and package them into EPUB.

Usage:
    python main.py --url <manga-index-url> --title <manga-title> [options]
"""

import argparse
import logging
import re
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


def _invalidate_epub_for_chapter(chapter_key: str, manifest, output_dir: Path, title: str, log) -> None:
    """
    When a previously-packed chapter is re-downloaded, find the EPUB that
    contains it, delete it, and reset all chapters in that batch to 'downloaded'
    so the pack phase regenerates a correct EPUB.
    """
    for epub_path in output_dir.glob(f"{title}_ch*.epub"):
        stem = epub_path.stem  # e.g. "one-piece_ch001-010"
        range_part = stem.split("_ch")[-1]  # "001-010"
        parts = range_part.split("-")
        if len(parts) != 2:
            continue
        start_key, end_key = parts[0], parts[1]
        if start_key <= chapter_key <= end_key:
            log.info(f"Deleting stale EPUB: {epub_path.name} (chapter {chapter_key} was updated)")
            epub_path.unlink()
            # Reset all packed chapters in this batch so they get re-packed together
            packed_in_batch = [
                k for k in manifest.get_packed_chapters()
                if start_key <= k <= end_key
            ]
            if packed_in_batch:
                manifest.reset_to_downloaded(packed_in_batch)
            break


def _reset_missing_epubs(
    manifest, packager, output_dir: Path, title: str, batch_size: int, log
) -> None:
    """
    Scan chapters marked 'packed' in manifest. For each batch whose EPUB file
    no longer exists on disk, reset those chapters back to 'downloaded' so they
    get re-packed on the next run.
    """
    packed = manifest.get_packed_chapters()
    if not packed:
        return

    for batch_start in range(0, len(packed), batch_size):
        batch_keys = packed[batch_start : batch_start + batch_size]
        start, end = batch_keys[0], batch_keys[-1]
        epub_path = output_dir / f"{title}_ch{start}-{end}.epub"
        if not epub_path.exists():
            log.info(f"EPUB missing for chapters {start}-{end}, resetting to re-pack")
            manifest.reset_to_downloaded(batch_keys)


def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir) / args.title
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(output_dir)

    log = logging.getLogger(__name__)
    error_log = output_dir / "errors.log"

    adapter = pick_adapter(args.url)
    manifest = Manifest(output_dir, args.title)
    downloader = Downloader(output_dir, delay=args.delay, error_log=error_log)
    packager = Packager(output_dir, args.title)

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

    # --- Repair: reset chapters whose EPUB was deleted ---
    _reset_missing_epubs(manifest, packager, output_dir, args.title, args.batch_size, log)

    # --- Pack phase ---
    all_ready = manifest.get_downloaded_chapters()
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
        epub_path = packager.pack(batch_keys, [f for f in folders if f])
        manifest.set_packed(batch_keys)
        log.info(f"Created: {epub_path}")

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
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
