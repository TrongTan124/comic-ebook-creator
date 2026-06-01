# comic-ebook-creator

CLI tool Python tự động crawl ảnh manga/comic từ trang đọc truyện online, tải về máy, và đóng gói thành file EPUB đọc được trên Kobo và Kindle.

## Tính năng

- Tự động phát hiện toàn bộ danh sách chapter từ trang index
- Tải ảnh về với cấu trúc thư mục có tổ chức: `output/<tên-truyện>/ch-<NNN>/<page>.webp`
- Đóng gói mỗi N chapter thành 1 file EPUB (mặc định 10 chapter/file)
- Resume: chạy lại tự bỏ qua chapter đã tải, chỉ tải phần còn thiếu
- Tự phát hiện và tải bù ảnh bị miss (timeout/lỗi mạng)
- Retry tự động với exponential backoff khi gặp lỗi mạng
- Log lỗi vào `errors.log` thay vì crash
- Tương thích EPUB chuẩn Kobo và Kindle

## Yêu cầu

- Python 3.10+
- pip

## Cài đặt

```bash
git clone <repo-url>
cd comic-ebook-creator

# Tạo virtual environment (khuyến nghị)
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

## Cách sử dụng

### Cơ bản — tải toàn bộ truyện

```bash
python main.py --url "<url-trang-index>" --title "<tên-truyện>"
```

### Tải một range chapter cụ thể

```bash
python main.py --url "<url>" --title "one-piece" --start-chapter 1 --end-chapter 10
```

### Tùy chỉnh số chapter mỗi EPUB

```bash
# 5 chapter per EPUB thay vì mặc định 10
python main.py --url "<url>" --title "one-piece" --batch-size 5
```

### Fallback khi auto-detection không hoạt động

```bash
# Tạo file chapters.txt — mỗi dòng một URL chapter
python main.py --url "<url>" --title "one-piece" --chapters-file chapters.txt
```

### Tất cả tham số

| Tham số | Mặc định | Mô tả |
|---------|---------|-------|
| `--url` | _(bắt buộc)_ | URL trang index manga |
| `--title` | _(bắt buộc)_ | Tên manga (dùng cho tên thư mục và file EPUB) |
| `--batch-size` | `10` | Số chapter mỗi file EPUB |
| `--start-chapter` | `1` | Chapter bắt đầu (1-based) |
| `--end-chapter` | _(tất cả)_ | Chapter kết thúc (inclusive) |
| `--chapters-file` | — | File text chứa danh sách URL (1 dòng = 1 URL) |
| `--output-dir` | `./output` | Thư mục lưu kết quả |
| `--delay` | `1.5` | Delay giữa các request (giây) |

## Output

```
output/
└── one-piece/
    ├── ch-001/
    │   ├── 001.webp
    │   ├── 002.webp
    │   └── ...
    ├── ch-002/
    │   └── ...
    ├── chapters.json          ← manifest theo dõi trạng thái
    ├── errors.log             ← log ảnh bị skip
    └── one-piece_ch001-010.epub
```

## Trang web được hỗ trợ

| Trang | URL | Ghi chú |
|-------|-----|---------|
| **One Piece Truyen** | `onepiecetruyen.net` | Đang hoạt động — One Piece tiếng Việt, chapter 1–1181+ |

> **Cách thêm site mới:** Tạo file `src/adapters/<sitename>.py` kế thừa `BaseAdapter` và đăng ký trong `ADAPTERS` list ở `main.py`. Không cần sửa core code.

## Ví dụ thực tế

```bash
# Tải 10 chapter đầu One Piece
python main.py \
  --url "https://onepiecetruyen.net/chapters" \
  --title "one-piece" \
  --start-chapter 1 \
  --end-chapter 10

# Kết quả: output/one-piece/one-piece_ch001-010.epub
```

## Ghi chú kỹ thuật

- Ảnh được lưu định dạng gốc (`.webp`) và convert sang JPEG khi đóng gói vào EPUB
- Rate limiting: delay 1–2 giây ngẫu nhiên giữa mỗi request để tránh bị block
- Retry: tối đa 3 lần với backoff 2s, 4s, 8s khi gặp timeout
- Manifest `chapters.json` lưu `total_pages` (từ CDN probe) để detect ảnh bị miss chính xác


# BONUS
Tôi sử dụng skill prompt-master để tạo lệnh chuẩn gửi claude làm ứng dụng này. Cụ thể tôi viết:

```sh
/prompt-master Tôi muốn viết một hệ thống có thể truy cập vào các trang đọc truyện online, sau đó tải các ảnh về theo từng chapter. Sau đó tôi dùng các ảnh này để làm thành file ebook đọc trên kobo hoặc kindle. 
Trang đọc truyện và truyện tôi sẽ chỉ định. Các chapter nếu có thể lấy tự động được theo truyện thì tốt. Còn nếu không thể tự động thì tôi có thể đưa danh sách link từng chapter (cái này không khuyến khích)
Ứng dụng này có thể tự tải ảnh, tự tạo thành một file book sau khi gom gộp khoảng 10 chapter lại với nhau.
```

Kêt quả trả về y hệt như dưới (đúng cấu trúc markdown). Tôi sử dụng prompt này để gửi cho claude viết ứng dụng. Sau đó tôi có cải tiến thêm một số yêu cầu (điều chỉnh) để phù hợp với nhu cầu của tôi. Cơ bản prompt này chuẩn để yêu cầu claude viết rồi:

## Objective
Build a CLI tool in Python that crawls manga/comic chapter images from a specified online reading site, downloads them locally, and packages every 10 chapters into a single EPUB or CBZ ebook file readable on Kobo and Kindle.

## Context
- No existing codebase. Build from scratch.
- Target: manga/webtoon reading sites (URL and manga title will be provided at runtime)
- Chapters should be auto-detected from the manga's table of contents page when possible
- Fallback: accept a plain-text file of chapter URLs (one per line) — deprioritize UX for this path
- Output ebooks must be compatible with Kobo and Kindle (EPUB preferred; CBZ as fallback)
- Tool runs locally on Linux/macOS via CLI. No GUI needed.

## Target State
A working CLI tool with this interface:

```bash
python main.py --url "https://site.com/manga/ten-truyen" --title "Tên Truyện" [--chapters-file chapters.txt]
```

When done:
- Auto-discovers all chapter URLs from the manga index page
- Downloads images per chapter into `output/<manga-title>/ch-<NNN>/`
- Every 10 chapters → generates one EPUB file: `output/<manga-title>/<manga-title>_ch001-010.epub`
- Images are embedded in the EPUB with correct reading order
- Existing downloaded chapters are skipped (resume support)
- A `chapters.json` manifest is written to track state

## Scope
- Work only in: `./src/`, `./output/`, `main.py`, `requirements.txt`
- Do NOT touch: system Python packages, system directories, any file outside the project folder

## Constraints
- Python 3.10+
- Dependencies: `requests`, `beautifulsoup4`, `Pillow`, `ebooklib` — no others without asking
- Use `requests` + `BeautifulSoup` for scraping. Do NOT use Selenium or Playwright unless the site requires JS rendering — ask before adding browser automation
- Respect rate limiting: add a 1–2 second delay between image requests
- User-agent spoof: use a realistic browser User-Agent header
- Chapter auto-detection MUST be configurable via a site adapter pattern — different sites have different HTML structures. Start with one adapter (e.g. NetTruyen or site the user specifies), make it easy to add more
- Image validation: skip and log corrupt/zero-byte images instead of crashing
- EPUB chapter grouping: 10 chapters per file, configurable via `--batch-size N`

## Acceptance Criteria
- [ ] `python main.py --url <url> --title <name>` runs end-to-end without error on the target site
- [ ] Images download to correct folder structure: `output/<title>/ch-<NNN>/<page>.jpg`
- [ ] Every 10 chapters produces one valid EPUB file openable in Kobo/Kindle desktop app
- [ ] Re-running skips already-downloaded chapters
- [ ] `--chapters-file` fallback path works when auto-detection fails
- [ ] Errors (network, parse, corrupt image) are logged to `output/<title>/errors.log`, not crash

## Stop Conditions
Stop and ask before:
- Adding any dependency not in the Constraints list
- Implementing Selenium or any browser automation
- Changing the output folder structure or EPUB naming convention
- Writing any file outside `./src/`, `./output/`, `main.py`, `requirements.txt`
- Choosing a site adapter implementation that hard-codes site logic into core modules

## Progress
After each completed step: ✅ [what was done] — [file(s) affected]

## Session Strategy
New session — build from scratch. Think carefully before starting architecture.