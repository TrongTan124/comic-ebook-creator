# STATE.md — comic-ebook-creator

## Current Position

**Milestone:** v0.1 — MVP One Piece Crawler
**Phase:** Phase 1 — Project Setup & Architecture
**Status:** IN PROGRESS

---

## Phases Overview

| Phase | Name | Status |
|-------|------|--------|
| 1 | Project Setup & Architecture | 🔄 In Progress |
| 2 | Site Adapter + Downloader | ⏳ Pending |
| 3 | EPUB Packager + Manifest | ⏳ Pending |
| 4 | Integration + E2E Test | ⏳ Pending |

---

## Phase 1 — Project Setup & Architecture

**Goal:** Skeleton code hoàn chỉnh, tất cả modules có interface rõ ràng, project chạy được mà không crash.

### TODOs
- [x] Tạo project structure (dirs, CLAUDE.md, docs/, .planning/)
- [x] Viết CLAUDE.md với workflow và architecture
- [x] Viết docs/AI_CONTEXT.md
- [x] Viết .planning/ROADMAP.md
- [x] Tạo requirements.txt
- [x] Viết main.py (CLI skeleton)
- [x] Viết src/adapters/base.py (BaseAdapter ABC)
- [x] Viết src/adapters/onepiecetruyen.py (adapter skeleton)
- [x] Viết src/downloader.py
- [x] Viết src/packager.py
- [x] Viết src/manifest.py
- [ ] Verify HTML structure của onepiecetruyen.net — chạy thực tế để kiểm tra selectors
- [ ] Fix adapter selectors nếu cần sau khi test

### Success Criteria
- `python main.py --help` chạy không crash
- Import tất cả modules không lỗi
- Architecture rõ ràng, dễ thêm adapter mới

---

## Phase 2 — Site Adapter + Downloader

**Goal:** Crawl được chapter URLs từ onepiecetruyen.net và tải ảnh xuống đúng cấu trúc.

### TODOs
- [ ] Test OnePieceTruyenAdapter với URL thực
- [ ] Verify CSS selectors cho chapter list và image extraction
- [ ] Test Downloader với 1 chapter
- [ ] Verify folder structure: `output/one-piece/ch-001/001.jpg`
- [ ] Verify rate limiting hoạt động
- [ ] Test resume: re-run không re-download chapter đã có

### Success Criteria
- `python main.py --url <url> --title one-piece --end-chapter 1` tải được chapter 1
- Folder structure đúng
- errors.log được tạo nếu có lỗi

---

## Phase 3 — EPUB Packager + Manifest

**Goal:** Đóng gói chapters thành EPUB đọc được trên Kobo/Kindle.

### TODOs
- [ ] Test Packager với chapters đã download
- [ ] Verify EPUB mở được trên Kobo desktop app
- [ ] Verify EPUB mở được trên Kindle desktop app
- [ ] Test batch grouping: 10 chapters → 1 EPUB
- [ ] Test naming convention: `one-piece_ch001-010.epub`
- [ ] Test `--batch-size 5`

### Success Criteria
- EPUB file hợp lệ, mở được
- Reading order đúng (page 1, 2, 3...)
- Metadata đúng (title, chapter range)

---

## Phase 4 — Integration + E2E Test

**Goal:** Tool chạy end-to-end không crash, tất cả acceptance criteria đều pass.

### TODOs
- [ ] E2E test: `python main.py --url <url> --title one-piece`
- [ ] Test `--chapters-file` fallback
- [ ] Test resume (chạy lại giữa chừng)
- [ ] Test corrupt image handling (errors.log)
- [ ] Review errors.log format
- [ ] Cleanup và polish CLI output

### Success Criteria
- Tất cả 6 acceptance criteria trong project brief đều pass

---

## Decisions Made

| Quyết định | Lý do | Ngày |
|-----------|-------|------|
| Site adapter pattern | Isolate site-specific logic, dễ thêm site mới | 2026-06-01 |
| EPUB primary, CBZ fallback | Kobo/Kindle support tốt hơn | 2026-06-01 |
| chapters.json manifest | Resume support khi interrupt | 2026-06-01 |
| ebooklib cho EPUB generation | Pure Python, không cần Calibre | 2026-06-01 |
| Rate limit 1-2s random | Tránh bị block server | 2026-06-01 |

## Critical Pitfalls

- **Hotlinking protection**: Set `Referer` header đúng với URL của site khi download ảnh
- **Chapter number parsing**: Một số chapter có số thập phân (100.5) — cần handle khi format tên file
- **EPUB image paths**: ebooklib yêu cầu image items phải được add vào spine đúng thứ tự
- **Large EPUBs**: Nếu chapter có quá nhiều ảnh, EPUB có thể quá lớn → consider image resize
