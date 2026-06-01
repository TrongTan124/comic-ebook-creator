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

### Download và pack 10 chapters

```bash
python main.py \
  --url "https://onepiecetruyen.net/chapters" \
  --title "one-piece" \
  --start-chapter 1 \
  --end-chapter 10

# Verify
ls output/one-piece/*.epub
# Expected (default --target-device both):
#   one-piece_ch001-010_kindle.epub   (1072x1448, ~73 MB)
#   one-piece_ch001-010_kobo.epub     (1264x1680, ~90 MB)

# Chỉ tạo cho 1 device:
python main.py --url "..." --title "one-piece" --target-device kindle ...
python main.py --url "..." --title "one-piece" --target-device kobo  ...
```

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
