# AI Context — comic-ebook-creator

> File này được AI đọc ở ĐẦU MỖI session để nắm context nhanh.
> Cập nhật sau mỗi task hoàn thành (xem CLAUDE.md — Bước 2).

## Project Summary

CLI tool Python tự động crawl ảnh manga/comic từ trang đọc truyện online, tải về máy local với cấu trúc thư mục có tổ chức, và đóng gói mỗi 10 chapter thành 1 file EPUB đọc được trên Kobo và Kindle. Mục tiêu đầu tiên là crawl One Piece từ onepiecetruyen.net.

**Target users:** người đọc truyện muốn đọc offline trên e-reader.
**Core problem:** các site đọc truyện online không hỗ trợ export EPUB; tool này tự động hóa việc tải và đóng gói.

## Architecture Overview

```
main.py (CLI argparse)
    ↓
Orchestrator (điều phối workflow)
    ├── SiteAdapter (src/adapters/)
    │     ├── base.py       → BaseAdapter ABC
    │     └── onepiecetruyen.py → adapter cho onepiecetruyen.net
    │           → trả về list[ChapterURL]
    ├── Downloader (src/downloader.py)
    │     → tải ảnh với rate limiting 1-2s
    │     → output/<title>/ch-<NNN>/<page>.jpg
    │     → validate ảnh, bỏ qua corrupt/zero-byte
    ├── Manifest (src/manifest.py)
    │     → đọc/ghi output/<title>/chapters.json
    │     → track trạng thái từng chapter (pending/downloaded/packed)
    └── Packager (src/packager.py)
          → gom 10 chapters → 1 EPUB
          → output/<title>/<title>_ch001-010.epub
```

## Current Status

- **Phase**: Phase 1 — Project Setup & Architecture (in progress)
- **Last updated**: 2026-06-01
- **Active work**: Khởi tạo project, viết code skeleton
- **Blocked on**: Cần verify HTML structure của onepiecetruyen.net để viết adapter chính xác

## Key Design Decisions

- **Site adapter pattern**: Mỗi site có 1 adapter class kế thừa BaseAdapter. Core modules không biết gì về HTML structure của từng site. Lý do: dễ thêm site mới mà không sửa core code.
- **EPUB thay vì CBZ**: EPUB là primary format vì Kobo và Kindle đều hỗ trợ tốt hơn CBZ. CBZ là fallback.
- **10 chapters per EPUB**: Mặc định configurable qua `--batch-size N`. Lý do: file quá lớn load chậm trên e-reader.
- **chapters.json manifest**: Track state để resume khi bị ngắt giữa chừng. Không re-download chapter đã có.
- **Rate limiting 1-2s**: Tránh bị block bởi server. Dùng `time.sleep(random.uniform(1, 2))`.
- **User-Agent spoof**: Dùng browser UA thực để tránh bị detect là bot.
- **ebooklib cho EPUB**: Thư viện Python thuần, không cần binary dependency như Calibre.

## Known Issues / Gotchas

- **onepiecetruyen.net HTML structure chưa verify**: Adapter được viết dựa trên pattern thông thường của các manga site Việt Nam. Cần chạy thực tế để xác nhận CSS selectors đúng.
- **Image hotlinking protection**: Một số site kiểm tra Referer header. Adapter cần set `Referer` đúng.
- **Chapter numbering**: Một số site dùng số thập phân (ch-100.5 cho chapter đặc biệt). Manifest cần handle edge case này.

## API / Interface Map

| CLI Argument | Required | Default | Mô tả |
|--------------|----------|---------|-------|
| `--url` | Yes | — | URL trang index manga (hoặc chapter đầu tiên) |
| `--title` | Yes | — | Tên manga (dùng cho tên thư mục và EPUB) |
| `--chapters-file` | No | None | File text chứa danh sách URL chapters (1 dòng = 1 URL) |
| `--batch-size` | No | 10 | Số chapters per EPUB file |
| `--start-chapter` | No | 1 | Chapter bắt đầu (inclusive) |
| `--end-chapter` | No | None | Chapter kết thúc (inclusive), None = tất cả |
| `--output-dir` | No | ./output | Thư mục output |
| `--delay` | No | 1.5 | Delay giữa các request (giây) |

## Environment Variables

| Biến | Bắt buộc | Mô tả |
|------|----------|-------|
| Không có | — | Tool chạy hoàn toàn qua CLI args |

## Changelog

### 2026-06-01 — [Project initialized]
**Files thay đổi:** `CLAUDE.md`, `docs/AI_CONTEXT.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `docs/error_ledger.md`, `docs/runbooks/daily-operations.md`
**Mô tả:** Khởi tạo project structure từ claude-template.init. Thiết lập architecture với site adapter pattern, viết skeleton code cho tất cả các modules.
**Lưu ý deploy:** Chạy `pip install -r requirements.txt` trước khi dùng.
