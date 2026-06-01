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
