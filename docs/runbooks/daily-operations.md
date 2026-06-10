# Daily Operations Runbook — comic-ebook-creator

> Tài liệu vận hành thực tế. Cập nhật khi quy trình thay đổi.

## Mục lục

1. [Setup môi trường](#1-setup-môi-trường)
2. [Chạy tool](#2-chạy-tool)
3. [Kiểm tra chapter bị thiếu ảnh](#3-kiểm-tra-chapter-bị-thiếu-ảnh)
4. [Dọn dẹp EPUB sai](#4-dọn-dẹp-epub-sai)
5. [Xử lý sự cố thường gặp](#5-xử-lý-sự-cố-thường-gặp)

---

## 1. Setup môi trường

```bash
git clone <repo-url>
cd comic-ebook-creator

python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

pip install -r requirements.txt

# Verify
python main.py --help
```

## 2. Chạy tool

### Lệnh chuẩn theo device

**Kobo Libra 2** (EPUB, stretch mode):
```bash
python main.py --url "https://onepiecetruyen.net/chapters" --title "one-piece" \
  --target-device kobo --fit-mode stretch --start-chapter 1 --end-chapter 10
# Output: one-piece_ch001-010_kobo.epub
```

**Kindle Paperwhite 5** (MOBI via Kindle Previewer 3 — full-bleed, không margin):
```bash
# Yêu cầu: cài Kindle Previewer 3 (miễn phí, chính thức từ Amazon)
# Tải tại: https://www.amazon.com/gp/feature.html?ie=UTF8&docId=1000765261
# Cài xong: tool tự tìm exe ở %LOCALAPPDATA%\Amazon\Kindle Previewer 3\

python main.py --url "https://onepiecetruyen.net/chapters" --title "one-piece" `
  --target-device kindle --fit-mode stretch --output-format azw3 `
  --start-chapter 1 --end-chapter 10
# Output: one-piece_ch001-010.mobi  (KP3: full-bleed thực sự)
# Nếu KP3 chưa cài: tool tự fallback Calibre CBZ->MOBI (vẫn có margin ~1cm)

# QUAN TRỌNG: Copy file .mobi (KHÔNG phải .epub) vào documents\ trên Kindle qua USB
# EPUB KHÔNG được nhận dạng khi copy USB — chỉ MOBI/AZW3/KFX qua USB
```

**Cả 2 device cùng lúc:**
```bash
python main.py --url "https://onepiecetruyen.net/chapters" --title "one-piece" \
  --target-device both --fit-mode stretch --output-format both --start-chapter 1 --end-chapter 10
# Output: _kobo.epub + _kindle.epub + _kindle.azw3
```

> **PowerShell**: dùng `` ` `` (backtick) để ngắt dòng, không phải `\`. Hoặc viết 1 dòng.

### Định dạng theo device

| Device | Format | Ghi chú |
|--------|--------|---------|
| Kobo Libra 2 | EPUB | Copy vào `/kobo/` qua USB |
| Kindle PW5 | AZW3 | Copy vào `documents/` qua USB — EPUB không được nhận dạng |
| Kindle (Send to Kindle) | EPUB | Upload lên amazon.com/sendtokindle |

### QUAN TRỌNG: Luôn chỉ định range rõ ràng

Pack phase chỉ xử lý chapters trong range `--start-chapter` đến `--end-chapter`.
Nếu muốn pack chapters 1-300 thành 30 file EPUB, chạy từng batch:

```bash
python main.py --url "..." --title "one-piece" --start-chapter 1   --end-chapter 10
python main.py --url "..." --title "one-piece" --start-chapter 11  --end-chapter 20
# ...hoặc dùng --end-chapter lớn để tool tự chia batch:
python main.py --url "..." --title "one-piece" --start-chapter 1 --end-chapter 100
# → tạo ra: ch001-010.epub, ch011-020.epub, ..., ch091-100.epub
```

### Resume sau khi bị ngắt

```bash
# Chạy lại đúng lệnh cũ — tool tự skip chapters đã packed/downloaded
python main.py --url "..." --title "one-piece" --start-chapter 1 --end-chapter 100
```

### Re-pack EPUB bị xóa (không re-download ảnh)

```bash
# Xóa EPUB đi
del output\one-piece\one-piece_ch001-010.epub

# Chạy lại — tool detect EPUB missing, re-pack từ ảnh đã có
python main.py --url "..." --title "one-piece" --start-chapter 1 --end-chapter 10
```

### Repack batch cũ (format cũ không có device suffix) sang format mới

```bash
# Xóa EPUB cũ (không có _kindle/_kobo suffix)
del output\one-piece\one-piece_ch001-010.epub

# Chạy lại — tự detect missing, tạo _kindle.epub + _kobo.epub
python main.py --url "..." --title "one-piece" --start-chapter 1 --end-chapter 10
```

### Repack xóa vệt đen 2 bên — khuyến nghị dùng `stretch`

Trang manga portrait (~tỉ lệ 0.67) hẹp hơn màn hình Kobo (~0.75) → letterbox để 2 vệt đen hai bên.

**So sánh 3 fit-mode:**

| Mode | Vệt đen | Mất nội dung | Distortion | Khuyến nghị |
|------|---------|-------------|-----------|-------------|
| `letterbox` | Có (2 bên) | Không | Không | Khi cần giữ tỉ lệ tuyệt đối |
| `fill` | Không | Có (crop top/bottom) | Không | KHÔNG dùng cho manga |
| `stretch` | Không | Không | Nhẹ (~12% ngang) | **Dùng cho Kobo** |

**QUAN TRỌNG:** Cả 3 mode đều KHÔNG phải default — phải ghi tường minh mỗi lần chạy. Default là `letterbox`.

```bash
# Repack với stretch mode — xóa vệt đen, giữ toàn bộ nội dung
python main.py \
  --url "https://onepiecetruyen.net/chapters" \
  --title "one-piece" \
  --target-device kobo \
  --fit-mode stretch \
  --force-repack \
  --start-chapter 1 \
  --end-chapter 10
```

`--force-repack` tự động:
1. Xóa tất cả EPUB của title này trên disk
2. Reset chapters về trạng thái "downloaded"
3. Pack lại với settings mới

Kiểm tra ảnh trong EPUB đúng kích thước và không có black bar:
```bash
python -c "
import zipfile
from PIL import Image
from io import BytesIO

epub_path = 'output/one-piece/one-piece_ch001-010_kobo.epub'
with zipfile.ZipFile(epub_path) as z:
    imgs = [n for n in z.namelist() if 'images/' in n]
    data = z.read(imgs[0])
    with Image.open(BytesIO(data)) as img:
        print(f'Size: {img.size}')  # Expected: (1264, 1680)
        px_left  = img.getpixel((0, img.height // 2))
        px_right = img.getpixel((img.width - 1, img.height // 2))
        print(f'Left-edge pixel:  {px_left}')   # không đen = không black bar
        print(f'Right-edge pixel: {px_right}')  # không đen = không black bar
"
```

## 3. Kiểm tra chapter bị thiếu ảnh

Chapters có thể bị thiếu ảnh nếu CDN probe gặp network error trong lần download đầu.
Dấu hiệu: `total_pages` trong manifest rất nhỏ (< 10) so với chapters bình thường (~20 pages).

### Kiểm tra nhanh

```bash
python -c "
import json
from pathlib import Path

d = json.load(open('output/one-piece/chapters.json'))
suspicious = [
    (k, v['total_pages'], sum(1 for f in Path(v['folder']).iterdir() if f.suffix in ('.webp','.jpg')))
    for k, v in d['chapters'].items()
    if v.get('total_pages') and v['total_pages'] < 10
]
for key, total, actual in sorted(suspicious):
    print(f'ch-{key}: total_pages={total}, actual={actual}')
"
```

### Fix chapter thiếu ảnh

```bash
# Bước 1: Xóa entry khỏi manifest và xóa folder ảnh cũ
python -c "
import json, shutil
from pathlib import Path

CH = '046'  # chapter cần fix
output = Path('output/one-piece')
d = json.load(open(output / 'chapters.json'))

# Xoa manifest entry
d['chapters'].pop(CH, None)

# Xoa folder anh cu
folder = output / f'ch-{CH}'
if folder.exists():
    for f in folder.iterdir(): f.unlink()
    try: folder.rmdir()
    except: pass

# Xoa EPUB chua chapter nay (neu biet ten)
# Bat ky EPUB nao cover ch-NNN se bi invalidate tu dong khi re-download

with open(output / 'chapters.json', 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('Done')
"

# Bước 2: Re-download đúng batch chứa chapter đó
# Nếu chapter 046 nằm trong batch 041-050:
python main.py --url "..." --title "one-piece" --start-chapter 41 --end-chapter 50
```

## 4. Dọn dẹp EPUB sai

### Phát hiện EPUB lẻ (ch-N-N thay vì ch-N-M)

```bash
python -c "
import re
from pathlib import Path
epubs = list(Path('output/one-piece').glob('*.epub'))
individual = [e.name for e in epubs if re.search(r'ch(\d+)-\1\.epub', e.name)]
print(f'Individual EPUBs: {len(individual)}')
for name in sorted(individual)[:10]:
    print(f'  {name}')
"
```

### Xóa toàn bộ EPUB lẻ

```bash
python -c "
import re
from pathlib import Path
deleted = 0
for epub in Path('output/one-piece').glob('*.epub'):
    if re.search(r'ch(\d+)-\1\.epub', epub.name):
        epub.unlink()
        deleted += 1
print(f'Deleted {deleted} individual EPUBs')
"
```

> Sau khi xóa EPUB lẻ, chapters tương ứng sẽ được tự động re-pack theo đúng batch-size khi chạy lại tool.

## 5. Xử lý sự cố thường gặp

### Tool báo "Already packed (N pages)" nhưng N nhỏ bất thường

Nguyên nhân: CDN probe bị ngắt bởi network error → `total_pages` lưu sai.
Fix: xem mục 3 — kiểm tra và fix chapter thiếu ảnh.

### Tool crash: ImportError

```bash
pip install -r requirements.txt
python -c "import requests, bs4, PIL, ebooklib; print('OK')"
```

### EPUB không mở được trên Kobo/Kindle

```bash
# Unzip để kiểm tra nội dung
python -c "
import zipfile
with zipfile.ZipFile('output/one-piece/one-piece_ch001-010_kindle.epub') as z:
    imgs = [n for n in z.namelist() if 'images/' in n]
    print(f'Images: {len(imgs)}')
    print('First:', imgs[0])
    print('Last:', imgs[-1])
"
```

### Kiểm tra kích thước ảnh trong EPUB đúng device chưa

```bash
python -c "
import zipfile
from PIL import Image
from io import BytesIO

epub_path = 'output/one-piece/one-piece_ch001-010_kindle.epub'
with zipfile.ZipFile(epub_path) as z:
    imgs = [n for n in z.namelist() if 'images/' in n]
    data = z.read(imgs[0])
    with Image.open(BytesIO(data)) as img:
        print(f'Size: {img.size}')  # Expected: (1072, 1448) for kindle
"
```

### "No chapters ready to pack" sau khi xóa EPUB

Tool sẽ tự detect và re-pack khi chạy lại đúng range. Xem thêm mục "Re-pack EPUB bị xóa".
