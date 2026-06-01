# ROADMAP — comic-ebook-creator v0.1

## Milestone Goal

MVP: CLI tool crawl One Piece từ onepiecetruyen.net, tải ảnh, đóng gói EPUB đọc được trên Kobo/Kindle.

## Acceptance Criteria (Project Level)

- [ ] `python main.py --url <url> --title <name>` chạy end-to-end không lỗi trên target site
- [ ] Ảnh download vào đúng cấu trúc: `output/<title>/ch-<NNN>/<page>.jpg`
- [ ] Mỗi 10 chapters tạo 1 EPUB hợp lệ mở được trên Kobo/Kindle desktop
- [ ] Re-run bỏ qua chapters đã download
- [ ] `--chapters-file` fallback hoạt động khi auto-detection fail
- [ ] Errors (network, parse, corrupt image) được log vào `output/<title>/errors.log`, không crash

## Phase Breakdown

### Phase 1 — Project Setup & Architecture (1-2 giờ)

**Deliverables:**
- Skeleton code đủ để import không lỗi
- Tất cả modules có interface rõ ràng (type hints)
- `python main.py --help` chạy được
- requirements.txt đầy đủ

**Requirements covered:** Project structure, architecture decisions

### Phase 2 — Site Adapter + Downloader (2-3 giờ)

**Deliverables:**
- `OnePieceTruyenAdapter` lấy được chapter URLs từ index page
- `Downloader` tải được ảnh với rate limiting và resume support
- `chapters.json` manifest được ghi và đọc đúng
- errors.log được tạo khi có lỗi

**Requirements covered:** REQ-1 (auto-discover chapters), REQ-2 (download images), REQ-5 (resume), REQ-6 (error logging)

### Phase 3 — EPUB Packager (1-2 giờ)

**Deliverables:**
- `Packager` tạo EPUB hợp lệ từ folder ảnh
- Batch grouping: 10 chapters per file (configurable)
- Naming convention: `<title>_ch001-010.epub`
- EPUB mở được trên Kobo + Kindle desktop

**Requirements covered:** REQ-3 (EPUB generation), REQ-4 (Kobo/Kindle compatible)

### Phase 4 — Integration + Polish (1 giờ)

**Deliverables:**
- E2E test thành công
- `--chapters-file` fallback hoạt động
- CLI output rõ ràng (progress bar hoặc print statements)
- Tất cả acceptance criteria pass

**Requirements covered:** REQ-1 đến REQ-6 (verify all)

## Out of Scope (v0.1)

- GUI
- CBZ format (EPUB đủ dùng)
- Parallel downloads (tránh bị block)
- Multiple sites (chỉ onepiecetruyen.net)
- Image resize/compression
- Cloud storage upload
