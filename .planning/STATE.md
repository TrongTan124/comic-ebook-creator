# STATE.md — comic-ebook-creator

## Current Position

**Milestone:** v0.1 — MVP One Piece Crawler
**Phase:** Phase 4 — Integration hoàn thành, đang vận hành thực tế
**Status:** FUNCTIONAL — tool chạy được, đang crawl One Piece ch1-300+

---

## Phases Overview

| Phase | Name | Status |
|-------|------|--------|
| 1 | Project Setup & Architecture | ✅ Done |
| 2 | Site Adapter + Downloader | ✅ Done |
| 3 | EPUB Packager + Manifest | ✅ Done |
| 4 | Integration + E2E Test | ✅ Done (verified với 300+ chapters) |

---

## Phase 1 — Project Setup & Architecture ✅

### TODOs
- [x] Tạo project structure (dirs, CLAUDE.md, docs/, .planning/)
- [x] Viết CLAUDE.md với workflow và architecture
- [x] Viết docs/AI_CONTEXT.md
- [x] Viết .planning/ROADMAP.md
- [x] Tạo requirements.txt
- [x] Viết main.py (CLI skeleton)
- [x] Viết src/adapters/base.py (BaseAdapter ABC)
- [x] Viết src/adapters/onepiecetruyen.py
- [x] Viết src/downloader.py
- [x] Viết src/packager.py
- [x] Viết src/manifest.py
- [x] Verify HTML structure onepiecetruyen.net → phát hiện Next.js lazy loading
- [x] Fix adapter: CDN probe thay vì HTML scraping
- [x] Tạo README.md
- [x] Cập nhật claude-template.init với yêu cầu README

---

## Phase 2 — Site Adapter + Downloader ✅

### TODOs
- [x] CDN probe strategy (HEAD request tuần tự đến 404)
- [x] Retry logic trong CDN probe (3 lần, backoff 2s/4s/8s) — fix ERR-005
- [x] Retry logic trong image downloader (3 lần) — fix ERR-003
- [x] Extension từ URL thay vì hardcode `.jpg` — fix ERR-002
- [x] Resume: `_page_already_exists()` check nhiều extension
- [x] Rate limiting 1-2s random delay
- [x] Referer header set đúng
- [x] errors.log cho ảnh skip/lỗi

---

## Phase 3 — EPUB Packager + Manifest ✅

### TODOs
- [x] Manifest schema: `total_pages` (CDN source of truth) + `downloaded_pages` — fix ERR-004
- [x] `is_images_complete()` chỉ tin `total_pages`, không dùng `image_count` cũ
- [x] EPUB pack với ebooklib, webp→JPEG convert
- [x] Batch grouping: N chapters per EPUB (default 10)
- [x] Naming convention: `<title>_ch001-010.epub`
- [x] Repair: `_reset_missing_epubs` redesign — fix ERR-006
- [x] EPUB invalidation khi chapter re-download
- [x] Pack phase filter by range — fix ERR-007
- [x] Message rõ ràng khi all packed + EPUBs exist

---

## Phase 4 — Integration + E2E ✅

### TODOs
- [x] E2E test chapter 1 (54 pages → EPUB 16MB)
- [x] E2E test chapters 1-10 → `ch001-010.epub` (66MB)
- [x] Verify resume: re-run skip chapters đã packed
- [x] Verify re-pack khi EPUB bị xóa
- [x] Crawl thực tế chapters 1-300+
- [x] Fix và verify chapters bị thiếu ảnh: 46, 67, 163, 219
- [x] Dọn 300 individual EPUB (artifact từ batch-size=1 test)

---

## Decisions Made

| Quyết định | Lý do | Ngày |
|-----------|-------|------|
| Site adapter pattern | Isolate site-specific logic, dễ thêm site mới | 2026-06-01 |
| EPUB primary, CBZ fallback | Kobo/Kindle support tốt hơn | 2026-06-01 |
| chapters.json manifest | Resume support khi interrupt | 2026-06-01 |
| ebooklib cho EPUB generation | Pure Python, không cần Calibre | 2026-06-01 |
| Rate limit 1-2s random | Tránh bị block server | 2026-06-01 |
| CDN probe thay vì HTML scraping | Site dùng Next.js lazy loading — HTML chỉ có ~7 ảnh | 2026-06-01 |
| `total_pages` tách riêng `downloaded_pages` | `image_count` cũ = số ảnh download được, không phải tổng CDN | 2026-06-01 |
| Pack phase filter by `range_keys` | Tránh chapters từ 2 range khác nhau bị gộp chung khi có gap | 2026-06-01 |
| `_reset_missing_epubs` scan file thực tế | batch_size-independent, không bị lệch khi user thay đổi --batch-size | 2026-06-01 |
| Device-optimized EPUB (resize + fixed-layout) | Ảnh 756x1200 hẹp hơn màn hình → bị tràn khi dùng max-width:100% → cần resize về đúng device resolution + pre-paginated | 2026-06-01 |
| `--target-device both` tạo 2 EPUB/batch | User dùng đồng thời Kindle PW5 + Kobo Libra 2 — 2 kích thước màn hình khác nhau | 2026-06-01 |

## Decisions Made (tiếp theo)

| Quyết định | Lý do | Ngày |
|-----------|-------|------|
| `--fit-mode fill` không phải default | Tránh phá EPUB cũ đã packed; user phải ghi tường minh | 2026-06-01 |
| `stretch` mode thay vì `fill` cho manga Kobo | `fill` crop top/bottom gây mất chữ đầu/cuối trang; `stretch` giữ nguyên chiều dọc, chỉ kéo ngang ~12% | 2026-06-01 |
| `--force-repack` xóa EPUB + reset manifest | Khi đổi fit-mode cần repack toàn bộ — xóa thủ công từng file rất bất tiện | 2026-06-01 |
| `@page{margin:0}` trong CSS mỗi page | Kobo reader có thể tự thêm page margin — cần khai báo tường minh để override | 2026-06-01 |
| `new_w = device_width` thay vì `int(img.width * scale)` | Float precision: với một số img.width, `int(...)` cho kết quả device_width-1 → 1px black column bên phải | 2026-06-01 |
| `--output-format azw3` dùng Calibre | Kindle PW5 không đọc EPUB trực tiếp qua USB — cần AZW3; Calibre là converter duy nhất không cần Amazon toolchain | 2026-06-09 |
| Kindle zero-margin metadata trong OPF | `zero-gutter/zero-margin/ke-border-width=0` báo Kindle không thêm margin; thiếu metadata này → ~1cm trắng 4 phía | 2026-06-09 |
| Calibre `--margin-* 0 --no-inline-toc` | Calibre mặc định thêm margin khi convert; phải tắt tường minh | 2026-06-09 |
| KCC thay Calibre cho Kindle MOBI | Calibre tạo "Text Type" MOBI → Kindle áp reading margin bất kể metadata; chỉ KCC tạo "Image Type" MOBI với EXTH records đúng chuẩn → full-bleed thực sự | 2026-06-09 |

## Critical Pitfalls

- **Hotlinking protection**: Set `Referer` header đúng với URL của site khi download ảnh
- **Next.js lazy loading**: HTML tĩnh chỉ có ~7 ảnh đầu — KHÔNG scrape HTML, dùng CDN probe
- **CDN probe phải retry**: 1 network error = probe dừng = `total_pages` sai → chapter thiếu ảnh mãi mãi
- **`total_pages` vs `image_count`**: Chỉ tin `total_pages` (từ CDN probe), bỏ qua `image_count` cũ (là số ảnh download được)
- **`--batch-size` phải nhất quán**: Dùng `--batch-size` khác lần pack gốc không còn gây crash, nhưng để tránh nhầm lẫn nên dùng nhất quán
- **Pack phase chỉ xử lý range hiện tại**: Chạy range nhỏ (vd ch41-50) sẽ KHÔNG pack chapters ngoài range dù chúng đang "downloaded"
- **Chapter number parsing**: Một số chapter có số thập phân (100.5) — cần handle khi format tên file
- **EPUB image paths**: ebooklib yêu cầu image items phải được add vào spine đúng thứ tự
- **EPUB không dùng fixed-layout sẽ bị scroll**: Ảnh manga (~0.63 ratio) hẹp hơn màn hình e-reader (~0.74-0.75 ratio) → fill 100% width khiến height vượt màn hình → phải resize + `rendition:pre-paginated`
- **EPUBs cũ (không có device suffix) vẫn được nhận dạng**: `_parse_epub_range()` xử lý cả 2 format. Muốn repack format mới: xóa EPUB cũ + chạy lại tool
- **`--fit-mode fill` KHÔNG tự động áp dụng**: Default là `letterbox`. Nếu chạy lại mà không thêm flag này, EPUB sẽ giữ nguyên letterbox dù code đã có fill mode. Phải ghi tường minh `--fit-mode fill` mỗi lần.
- **EPUB cũ không bị repack tự động khi đổi fit-mode**: `_reset_missing_epubs` chỉ reset khi EPUB file bị *xóa khỏi disk*. Nếu file còn đó, chapter vẫn là "packed" và tool bỏ qua. Dùng `--force-repack` để force delete + repack.
- **`fill` mode crop nội dung — KHÔNG dùng cho manga**: `fill` scale theo chiều rộng → ảnh cao hơn màn hình → crop top/bottom đối xứng → mất chữ đầu/cuối trang. Dùng `stretch` thay thế: giữ nguyên chiều dọc, chỉ kéo ngang.
- **`stretch` cho portrait, crop sides cho landscape**: `stretch` tự detect — nếu `new_w <= device_width` (portrait) thì stretch x; nếu `new_w > device_width` (landscape) thì crop sides. Logic trong `_resize_for_device`.
- **Kindle PW5 không đọc EPUB qua USB**: Chỉ đọc được MOBI/AZW3/KFX qua USB. Phải dùng `--output-format azw3`. EPUB chỉ dùng cho Kobo hoặc Send to Kindle (cloud).
- **Kindle Previewer 3 pipeline**: KP3 CLI tạo full-bleed MOBI từ fixed-layout EPUB. Exe tên `Kindle Previewer 3.exe` (có khoảng trắng). Output vào subdirectory `Mobi\` — cần rglob. Argument order: `input -convert -output dir`.
- **KindleGen deprecated**: Không còn download được từ Amazon. Dùng Kindle Previewer 3 thay thế.
- **Git conflict markers → SyntaxError**: Sau merge/pull, luôn chạy `python -m py_compile main.py` trước khi dùng tool.
- **PowerShell dùng `` ` `` không phải `\`**: Lệnh multi-line trong PowerShell dùng backtick (`` ` ``) để ngắt dòng, không phải backslash. Hoặc viết 1 dòng.
