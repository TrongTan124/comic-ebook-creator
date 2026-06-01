# Daily Operations Runbook — comic-ebook-creator

> Tài liệu vận hành thực tế. Cập nhật khi quy trình thay đổi.

## Mục lục

1. [Setup môi trường](#1-setup-môi-trường)
2. [Chạy tool](#2-chạy-tool)
3. [Xử lý sự cố thường gặp](#3-xử-lý-sự-cố-thường-gặp)

---

## 1. Setup môi trường

```bash
# Clone repo (nếu chưa có)
git clone <repo-url>
cd comic-ebook-creator

# Tạo virtualenv
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Cài dependencies
pip install -r requirements.txt

# Verify
python main.py --help
```

## 2. Chạy tool

### Crawl và tạo EPUB (thông thường)

```bash
python main.py \
  --url "https://onepiecetruyen.net/truyen-tranh/one-piece" \
  --title "one-piece"

# Verify
ls output/one-piece/
# Expected: ch-001/, ch-002/, ..., chapters.json, one-piece_ch001-010.epub
```

### Crawl với batch size tùy chỉnh

```bash
python main.py \
  --url "https://onepiecetruyen.net/truyen-tranh/one-piece" \
  --title "one-piece" \
  --batch-size 5
```

### Crawl range cụ thể

```bash
python main.py \
  --url "https://onepiecetruyen.net/truyen-tranh/one-piece" \
  --title "one-piece" \
  --start-chapter 1 \
  --end-chapter 10
```

### Fallback với chapters file

```bash
# Tạo file chapters.txt với 1 URL per dòng
cat chapters.txt
# https://onepiecetruyen.net/chapters/chapter-1
# https://onepiecetruyen.net/chapters/chapter-2

python main.py \
  --url "https://onepiecetruyen.net" \
  --title "one-piece" \
  --chapters-file chapters.txt
```

### Resume sau khi bị ngắt

```bash
# Chỉ cần chạy lại lệnh gốc — tool tự skip chapters đã download
python main.py \
  --url "https://onepiecetruyen.net/truyen-tranh/one-piece" \
  --title "one-piece"
```

## 3. Xử lý sự cố thường gặp

### Tool crash ngay khi bắt đầu

**Triệu chứng:** ImportError hoặc ModuleNotFoundError

```bash
# Fix
pip install -r requirements.txt

# Verify
python -c "import requests, bs4, PIL, ebooklib; print('OK')"
```

### Không tìm thấy chapter URLs

**Triệu chứng:** "No chapters found" hoặc empty list

```bash
# Kiểm tra URL có đúng không
curl -L "https://onepiecetruyen.net/truyen-tranh/one-piece" | grep -i "chapter"

# Fallback: dùng chapters file
python main.py --url <url> --title <title> --chapters-file chapters.txt
```

### Ảnh không tải được

**Triệu chứng:** Lỗi trong errors.log, thư mục chapter rỗng

```bash
# Xem errors.log
cat output/one-piece/errors.log

# Thử tải thủ công để debug
curl -H "Referer: https://onepiecetruyen.net" \
     -H "User-Agent: Mozilla/5.0 ..." \
     "<image-url>" -o test.jpg
```

### EPUB không mở được trên Kobo/Kindle

**Triệu chứng:** File EPUB bị báo lỗi khi mở

```bash
# Validate EPUB (cần epubcheck)
java -jar epubcheck.jar output/one-piece/one-piece_ch001-010.epub

# Xem file structure
unzip -l output/one-piece/one-piece_ch001-010.epub
```
