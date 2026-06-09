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

- **Phase**: Functional — đang vận hành thực tế với One Piece ch1-300+
- **Last updated**: 2026-06-01
- **Active work**: Vận hành ổn định, không có blocker
- **Blocked on**: none

## Key Design Decisions

- **Site adapter pattern**: Mỗi site có 1 adapter class kế thừa BaseAdapter. Core modules không biết gì về HTML structure của từng site. Lý do: dễ thêm site mới mà không sửa core code.
- **CDN probe thay vì HTML scraping**: onepiecetruyen.net là Next.js — HTML tĩnh chỉ có ~7 ảnh đầu. Probe HEAD request tuần tự lên CDN đến khi 404. URL pattern: `cdn.onepiecetruyen.net/one-piece/vi/chapter-{N}/{page:03d}.webp`.
- **`total_pages` tách riêng `downloaded_pages`**: `total_pages` = số pages từ CDN probe (source of truth). `downloaded_pages` = số ảnh thực tế save được. `is_images_complete()` chỉ so sánh actual files vs `total_pages`.
- **EPUB thay vì CBZ**: EPUB là primary format vì Kobo và Kindle đều hỗ trợ tốt hơn CBZ. CBZ là fallback.
- **10 chapters per EPUB**: Mặc định configurable qua `--batch-size N`. Lý do: file quá lớn load chậm trên e-reader.
- **Pack phase filter by range**: Pack phase chỉ xử lý chapters trong `--start-chapter` đến `--end-chapter`. Tránh chapters từ 2 range khác bị gộp khi có gap.
- **`_reset_missing_epubs` scan file thực tế**: Không dùng `batch_size` để tính tên EPUB — scan file `.epub` trên disk, match chapter key vào range. Batch_size-independent.
- **Retry 3 lần trong cả downloader và CDN probe**: Exponential backoff 2s/4s/8s. Lý do: 1 network error không được phép làm mất ảnh hoặc dừng probe sớm.
- **ebooklib cho EPUB**: Thư viện Python thuần, không cần binary dependency như Calibre.

## Known Issues / Gotchas

- **CDN probe có thể bị rate limit**: Nếu probe quá nhanh, CDN trả về 429. Đã có handler wait 5s và tiếp tục.
- **Chapters có `total_pages` rất nhỏ (< 10)**: Dấu hiệu probe bị ngắt sớm do network error trong lần download đầu. Kiểm tra bằng script trong daily-operations.md mục 3.
- **Chapter numbering thập phân**: Một số chapter có số (100.5) — manifest xử lý bằng format `100_5`. Chưa gặp thực tế với One Piece.
- **`--batch-size` nên nhất quán**: Tool không lưu batch_size vào manifest — nếu thay đổi giữa chừng, EPUB filename sẽ khác nhau nhưng không gây lỗi.

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
| `--target-device` | No | `both` | `kindle`, `kobo`, hoặc `both`. Khi `both`, tạo 2 file/batch với suffix `_kindle` và `_kobo`. |
| `--fit-mode` | No | `letterbox` | `letterbox`, `fill`, hoặc `stretch`. `stretch` khuyến nghị cho manga. |
| `--output-format` | No | `epub` | `epub`, `azw3`, hoặc `both`. `azw3` dùng Calibre convert + xóa EPUB trung gian. |
| `--force-repack` | No | false | Xóa EPUB+AZW3 cũ và pack lại từ ảnh đã download. |

## Environment Variables

| Biến | Bắt buộc | Mô tả |
|------|----------|-------|
| Không có | — | Tool chạy hoàn toàn qua CLI args |

## Changelog

### 2026-06-01 — Fix margin ~1cm khi đọc manga trên Kindle
**Files thay đổi:** `src/packager.py`, `main.py`
**Mô tả:** Kindle hiển thị ~1cm margin 4 phía dù ảnh đã đúng 1072×1448. Nguyên nhân kép: (1) Calibre thêm margin mặc định khi convert EPUB→AZW3, (2) EPUB thiếu Kindle-specific OPF metadata. Fix: thêm `--margin-* 0 --no-inline-toc` vào `ebook-convert`; thêm `zero-gutter/zero-margin/book-type/ke-border-*/original-resolution` metadata vào OPF khi device=kindle. `_pack_for_device` nhận thêm tham số `device` để biết đâu là Kindle.

### 2026-06-01 — Thêm --output-format azw3 (Calibre conversion)
**Files thay đổi:** `main.py`
**Mô tả:** Kindle PW5 không đọc EPUB trực tiếp qua USB — cần AZW3. Thêm `--output-format` với 3 giá trị: `epub` (default), `azw3` (convert qua Calibre ebook-convert, xóa EPUB trung gian), `both` (giữ cả hai). Calibre phải được cài và có trong PATH. `_reset_missing_epubs` và `_invalidate_epub_for_chapter` cũng được cập nhật để nhận dạng và xóa AZW3 files. Conversion dùng profile `--output-profile kindle_pw3`.
**Lưu ý deploy:** Phải cài Calibre trước khi dùng `--output-format azw3/both`. Verify: `ebook-convert --version`.

### 2026-06-01 — Thêm --fit-mode stretch (giữ chiều cao, kéo giãn chiều ngang)
**Files thay đổi:** `src/packager.py`, `main.py`
**Mô tả:** `fill` mode crop top/bottom gây mất chữ đầu/cuối trang. User muốn giữ nguyên chiều dọc, chỉ kéo giãn ngang để lấp đầy màn hình. Thêm `stretch` mode: scale theo chiều cao (device_height/img.height), sau đó stretch x từ new_w lên device_width. Không crop, không black bar, chỉ có slight horizontal distortion (~12% cho manga portrait trên Kobo). Portrait page: stretch x. Landscape page: crop sides. Lệnh: `--fit-mode stretch --force-repack`.

### 2026-06-01 — --fit-mode fill, --force-repack, CSS @page fix
**Files thay đổi:** `src/packager.py`, `main.py`
**Mô tả:** Trang manga portrait hẹp hơn màn hình Kobo (tỉ lệ ~0.67 vs 0.75) gây 2 vệt đen 2 bên.
- `--fit-mode fill`: scale ảnh theo đúng chiều rộng màn hình (new_w = device_width chính xác, không float error), crop top/bottom đối xứng nếu ảnh cao hơn màn hình. Default vẫn là `letterbox`.
- `--force-repack`: xóa toàn bộ EPUB cũ + reset chapter về downloaded → pack lại. Dùng khi muốn đổi fit-mode mà không thao tác thủ công.
- CSS: thêm `@page{margin:0;padding:0}` và `margin:0;padding:0` trên img để Kobo reader không tự thêm padding.
**Lưu ý deploy:** Phải dùng `--fit-mode fill` tường minh (KHÔNG phải default). Để repack: `python main.py ... --fit-mode fill --target-device kobo --force-repack`.

### 2026-06-01 — Device-optimized EPUB packing (Kindle PW5 + Kobo Libra 2)
**Files thay đổi:** `src/packager.py`, `main.py`
**Mô tả:** Fix hoàn toàn vấn đề hiển thị ảnh trên máy đọc sách.
- **Image resize + letterbox**: Mỗi ảnh được resize về đúng kích thước màn hình thiết bị (Kindle 1072×1448, Kobo 1264×1680) với black letterbox hai bên — đảm bảo 1 page = 1 màn hình, không cần scroll.
- **Fixed-layout EPUB**: Thêm `rendition:pre-paginated`, `rendition:spread=none`, `rendition:orientation=portrait` — reader hiển thị đúng 1 trang/màn hình.
- **Cover image**: Trang đầu chapter 1 được set làm cover trong metadata EPUB → hiện đúng thumbnail trên Kobo/Kindle khi tắt màn hình.
- **Viewport + CSS chính xác**: Mỗi HTML page có `<meta name="viewport" content="width=DW, height=DH"/>` và CSS `width/height` pixel-exact theo device.
- **`--target-device` CLI arg**: `kindle`, `kobo`, hoặc `both` (default). Khi `both`, tạo 2 EPUB/batch với suffix `_kindle.epub` và `_kobo.epub`.
- **`_parse_epub_range()` helper**: Refactor phân tích EPUB filename — xử lý cả tên cũ (không suffix) và tên mới (có `_kindle`/`_kobo`).
- **`_invalidate_epub_for_chapter` fix**: Xóa tất cả device variants khi chapter bị re-download (không `break` sau EPUB đầu tiên).
**Lưu ý deploy:** Các EPUB cũ (không suffix) vẫn được nhận dạng đúng. Để repack lại batch cũ theo format mới: xóa EPUB cũ + chạy lại tool.

### 2026-06-01 — [Project initialized]
**Files thay đổi:** `CLAUDE.md`, `docs/AI_CONTEXT.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `docs/error_ledger.md`, `docs/runbooks/daily-operations.md`
**Mô tả:** Khởi tạo project structure từ claude-template.init. Thiết lập architecture với site adapter pattern, viết skeleton code cho tất cả các modules.
**Lưu ý deploy:** Chạy `pip install -r requirements.txt` trước khi dùng.

### 2026-06-01 — [Full implementation + 7 bug fixes, tool vận hành thực tế]
**Files thay đổi:** `src/adapters/onepiecetruyen.py`, `src/downloader.py`, `src/manifest.py`, `src/packager.py`, `main.py`, `README.md`, `claude-template.init`, `docs/*`, `.planning/STATE.md`
**Mô tả:** Toàn bộ tool được implement và chạy thực tế với One Piece ch1-300+. 7 bugs được phát hiện và fix trong quá trình vận hành:
- ERR-001: Next.js lazy loading → chuyển từ HTML scraping sang CDN probe
- ERR-002: Extension hardcode `.jpg` → lấy từ URL
- ERR-003: Không retry khi download lỗi → exponential backoff 3 lần
- ERR-004: `image_count` lưu sai → thêm `total_pages` tách biệt
- ERR-005: CDN probe `break` khi network error → retry trong `_probe_page()`
- ERR-006: `_reset_missing_epubs` dùng `batch_size` → scan file thực tế
- ERR-007: Pack phase pool toàn manifest → filter by `range_keys`
- Tạo README.md, cập nhật claude-template.init với yêu cầu README
**Lưu ý deploy:** `--batch-size` nên nhất quán giữa các lần chạy. Dùng `--start-chapter` và `--end-chapter` rõ ràng mỗi lần.
