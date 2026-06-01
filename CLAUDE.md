# comic-ebook-creator — Claude Instructions

## Communication Language

**Luôn trả lời bằng tiếng Việt** khi trao đổi với người dùng trong project này.
Giải thích kỹ thuật, hướng dẫn, phân tích lỗi — tất cả đều dùng tiếng Việt.

## Project Context

**Core Value:** CLI tool tự động crawl ảnh từ trang đọc truyện online, tải về máy, và đóng gói mỗi 10 chapter thành 1 file EPUB/CBZ đọc được trên Kobo và Kindle.

**Milestone:** v0.1 — MVP One Piece Crawler (4 phases, 6 requirements)

**State:** `.planning/STATE.md` — đọc file này đầu tiên để biết phase hiện tại

---

## Mandatory Workflow — KHÔNG ĐƯỢC BỎ QUA

> Áp dụng cho MỌI task: sửa bug, thêm tính năng, refactor, cập nhật config.

### Bước 1 — Trước khi bắt đầu
Đọc `docs/AI_CONTEXT.md` để nắm context và lịch sử thay đổi gần nhất.
Nếu task liên quan đến tính năng mới → đọc thêm `.planning/ROADMAP.md`.

### Bước 2 — Sau khi hoàn thành task
**BẮT BUỘC** cập nhật `docs/AI_CONTEXT.md` mục `## Changelog` với entry mới:

```markdown
### YYYY-MM-DD — [Tên task ngắn gọn]
**Files thay đổi:** `path/to/file1`, `path/to/file2`
**Mô tả:** Giải thích chi tiết những gì đã thay đổi và tại sao.
**Lưu ý deploy:** (nếu cần thiết)
```

### Bước 3 — Commit
Sau khi đã cập nhật changelog, commit toàn bộ thay đổi:

```bash
git add -A
git commit -m "type: mô tả ngắn gọn task"
```

> Hỏi xác nhận user trước khi `git push` nếu không được yêu cầu rõ ràng.

---

## Critical Rules (Do Not Violate)

1. **Never commit secrets** — `.env` files phải gitignored; chỉ commit `.env.example`
2. **No new dependencies without asking** — Chỉ dùng: `requests`, `beautifulsoup4`, `Pillow`, `ebooklib`. Hỏi trước khi thêm bất kỳ package nào khác
3. **No browser automation without asking** — Không dùng Selenium/Playwright trừ khi site bắt buộc JS rendering — hỏi user trước
4. **No files outside project scope** — Chỉ ghi vào `./src/`, `./output/`, `main.py`, `requirements.txt`. Không động đến system directories
5. **Stop conditions** — Dừng và hỏi trước khi: thay đổi output folder structure, thay đổi EPUB naming convention, hard-code site logic vào core modules

## Architecture

```
main.py (CLI)
    ↓
Orchestrator
    ├── SiteAdapter (src/adapters/)
    │     ├── BaseAdapter (abstract)
    │     └── OnePieceTruyenAdapter
    │           → chapter URLs list
    ├── Downloader (src/downloader.py)
    │     → output/<title>/ch-<NNN>/<page>.jpg
    ├── Manifest (src/manifest.py)
    │     → output/<title>/chapters.json
    └── Packager (src/packager.py)
          → output/<title>/<title>_ch001-010.epub
```

ADRs in `docs/decisions/` are LOCKED decisions — do not change without explicit discussion.

## Key File Locations

| File | Purpose |
|------|---------|
| `.planning/STATE.md` | Current phase, progress, open questions |
| `.planning/ROADMAP.md` | Phase structure with success criteria |
| `docs/AI_CONTEXT.md` | AI context, design decisions, changelog |
| `docs/decisions/` | ADRs — all architectural decisions |
| `docs/error_ledger.md` | Bug log với triệu chứng + fix đã verify |
| `docs/runbooks/daily-operations.md` | Hướng dẫn vận hành thủ công |
| `src/adapters/base.py` | BaseAdapter abstract class |
| `src/adapters/onepiecetruyen.py` | Adapter cho onepiecetruyen.net |
| `src/downloader.py` | Image downloader với rate limiting |
| `src/packager.py` | EPUB/CBZ packager |
| `src/manifest.py` | chapters.json manifest manager |

## Technology Stack

- **CLI** — Python 3.10+ (entry point `main.py`)
- **HTTP/Scraping** — `requests` + `beautifulsoup4` (crawl chapter URLs và images)
- **Image processing** — `Pillow` (validate và convert images)
- **EPUB generation** — `ebooklib` (tạo EPUB chuẩn Kobo/Kindle)

## Deployment Target

Linux/macOS, Python 3.10+ venv. Chạy `pip install -r requirements.txt` rồi `python main.py --url <url> --title <title>`.

## Common Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run
python main.py --url "https://onepiecetruyen.net/truyen-tranh/one-piece" --title "one-piece"
python main.py --url "https://onepiecetruyen.net/truyen-tranh/one-piece" --title "one-piece" --batch-size 5

# Fallback với chapters file
python main.py --url "https://onepiecetruyen.net" --title "one-piece" --chapters-file chapters.txt

# Test một chapter cụ thể
python main.py --url "https://onepiecetruyen.net/truyen-tranh/one-piece" --title "one-piece" --start-chapter 1 --end-chapter 1
```

---

## Lệnh "Tổng hợp cuộc trò chuyện"

Khi người dùng nói **"hãy tổng hợp lại cuộc trò chuyện này"** (hoặc tương tự: "cập nhật tài liệu", "ghi lại những gì đã làm"), thực hiện đúng quy trình sau — không hỏi lại, không bỏ sót bước nào.

### Bước 1 — Đọc để hiểu trạng thái hiện tại

```
docs/error_ledger.md              → xem ERR cuối cùng đã có, tránh trùng số
docs/runbooks/daily-operations.md → xem phần nào đã có, cần bổ sung chỗ nào
.planning/STATE.md                → cập nhật progress nếu có phase/plan hoàn thành
docs/backlog.md                   → ghi nhận feature/improvement phát sinh
```

### Bước 2 — Phân loại nội dung cuộc trò chuyện

| Loại | Ghi vào đâu | Tiêu chí nhận biết |
|------|-------------|-------------------|
| **Bug mới phát hiện** | `docs/error_ledger.md` — thêm ERR-NNN mới | Lỗi có triệu chứng + nguyên nhân + fix đã verify |
| **Hướng dẫn vận hành / thiết lập** | `docs/runbooks/daily-operations.md` | Quy trình thao tác thủ công, cấu hình, setup... |
| **Quyết định kiến trúc mới** | `docs/decisions/ADR-NNN-*.md` (mới) | Chọn công nghệ, thay đổi thiết kế hệ thống |
| **Phase/plan hoàn thành** | `.planning/STATE.md` — cập nhật progress | Người dùng xác nhận tính năng hoạt động |
| **Tính năng backlog** | `docs/backlog.md` | Ý tưởng cải tiến, feature chưa implement |
| **Pitfall / cạm bẫy mới** | `.planning/STATE.md` mục "Critical Pitfalls" | Lỗi tiềm ẩn có thể tái phát ở phase khác |
| **Thay đổi context / thiết kế** | `docs/AI_CONTEXT.md` mục Changelog | Quyết định thiết kế, interface, API thay đổi |

### Bước 3 — Sau khi cập nhật xong

Báo cáo ngắn gọn những file đã cập nhật. Không cần giải thích lại nội dung.
