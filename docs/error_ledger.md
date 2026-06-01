# Error Ledger — comic-ebook-creator

> Mỗi bug được verify xong mới được ghi vào đây.
> Format ID: ERR-NNN (tăng dần, không tái sử dụng).

## Tổng hợp nhanh

| ID | Component | Tóm tắt | Ngày | Status |
|----|-----------|---------|------|--------|
| ERR-001 | Adapter / CDN probe | Lazy loading: HTML chỉ có ~7 ảnh đầu | 2026-06-01 | Fixed |
| ERR-002 | Downloader | Extension hardcode `.jpg` cho ảnh `.webp` | 2026-06-01 | Fixed |
| ERR-003 | Downloader | Không có retry → 1 timeout = mất ảnh vĩnh viễn | 2026-06-01 | Fixed |
| ERR-004 | Manifest / Completeness | `image_count` lưu số ảnh download được, không phải tổng CDN | 2026-06-01 | Fixed |
| ERR-005 | CDN probe | `break` khi network error → probe dừng sớm, `total_pages` sai | 2026-06-01 | Fixed |
| ERR-006 | `_reset_missing_epubs` | Dùng `batch_size` để tính EPUB path → sai khi batch_size thay đổi | 2026-06-01 | Fixed |
| ERR-007 | Pack phase | Pool toàn bộ manifest → chapters 2 range khác bị gộp 1 EPUB khi có gap | 2026-06-01 | Fixed |

---

## Chi tiết

### ERR-001 — Adapter: Lazy loading khiến HTML chỉ có ~7 ảnh

**Thời gian:** 2026-06-01
**Component:** `src/adapters/onepiecetruyen.py`

**Triệu chứng:**
```
[001] Downloaded 7/7 images
```
Chapter 1 thực tế có 54 pages nhưng chỉ download được 7.

**Phát hiện:**
```bash
python -c "
import requests; from bs4 import BeautifulSoup
r = requests.get('https://onepiecetruyen.net/chapters/chapter-1', headers={...})
soup = BeautifulSoup(r.text, 'lxml')
print(len(soup.select('section img')))  # → 7
"
```

**Nguyên nhân:**
Site dùng Next.js SSR + lazy loading. Static HTML chỉ render ~7 ảnh đầu, phần còn lại (đến page 54) load bằng JavaScript khi user scroll.

**Xử lý:**
Bỏ scrape HTML, thay bằng CDN probe — HEAD request tuần tự đến CDN cho đến khi gặp 404:
```python
url = f"https://cdn.onepiecetruyen.net/one-piece/vi/chapter-{N}/{page:03d}.webp"
resp = session.head(url); stop when 404
```

**Verify:**
```
[001] Chapter 1: 54 pages found
[001] Downloaded 54/54 images
```

**Phòng ngừa:**
Mọi site adapter mới cần kiểm tra xem site có lazy loading không trước khi dùng HTML scraping. CDN probe là fallback đáng tin cậy hơn khi URL pattern cố định.

---

### ERR-002 — Downloader: Extension hardcode `.jpg` cho ảnh `.webp`

**Thời gian:** 2026-06-01
**Component:** `src/downloader.py`

**Triệu chứng:**
Ảnh webp được save thành `001.jpg`, khi packager đọc lại treat là JPEG (sai format bytes), EPUB có thể bị lỗi trên một số reader.

**Nguyên nhân:**
```python
filename = chapter_dir / f"{idx:03d}.jpg"  # hardcode extension
```

**Xử lý:**
```python
ext = _ext_from_url(url)  # lấy từ URL: .webp, .jpg, .png
filename = chapter_dir / f"{idx:03d}{ext}"
```

**Verify:** Files được save đúng extension `.webp`, packager convert sang JPEG khi embed vào EPUB.

---

### ERR-003 — Downloader: Không retry → 1 timeout = mất ảnh vĩnh viễn

**Thời gian:** 2026-06-01
**Component:** `src/downloader.py`

**Triệu chứng:**
```
[WARNING] Skipping .../chapter-1/031.webp: Network error: Read timed out.
[001] Downloaded 53/54 images
```
Page 31 bị skip, EPUB thiếu trang.

**Nguyên nhân:**
`_download_image` không có retry — 1 lần timeout là log error và bỏ qua luôn.

**Xử lý:**
Thêm exponential backoff retry (max 3 lần, wait 2s / 4s / 8s):
```python
def _download_image(self, url, dest, referer, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            ...
        except requests.RequestException as e:
            wait = 2 ** attempt
            if attempt < max_retries:
                time.sleep(wait)
            else:
                self._log_error(url, f"Failed after {max_retries} attempts: {e}")
```

**Verify:** Chapter 1 re-download page 031 thành công sau khi thêm retry.

---

### ERR-004 — Manifest: `image_count` không phân biệt "đã download" vs "tổng CDN"

**Thời gian:** 2026-06-01
**Component:** `src/manifest.py`, `main.py`

**Triệu chứng:**
```
[001] Already downloaded (53 pages), skipping
```
Chapter 1 thực tế có 54 pages nhưng manifest lưu `image_count=53` (số ảnh download được), completeness check thấy 53/53 → pass.

**Nguyên nhân:**
Schema cũ chỉ lưu `image_count = saved` (số ảnh thực tế download được). Không có trường nào lưu tổng pages từ CDN probe.

**Xử lý:**
Thêm trường `total_pages` (từ CDN probe) và `downloaded_pages` (thực tế):
```python
manifest.set_downloaded(key, url, folder, saved, total=len(image_urls))
```
`is_images_complete()` chỉ tin `total_pages`, bỏ qua `image_count` cũ. Nếu `total_pages=None` → re-probe.

**Verify:** Chapters cũ (không có `total_pages`) tự động re-probe CDN 1 lần, sau đó skip đúng.

---

### ERR-005 — CDN probe: `break` khi network error → `total_pages` bị lưu sai

**Thời gian:** 2026-06-01
**Component:** `src/adapters/onepiecetruyen.py`

**Triệu chứng:**
```
ch-046: manifest=2 pages stored, 2 files on disk
ch-067: manifest=2 pages stored, 2 files on disk
ch-163: manifest=6 pages stored, 6 files on disk
```
Các chapters này thực tế có 19-21 pages.

**Phát hiện:**
```python
# Code cũ
except requests.RequestException as e:
    break  # 1 lỗi mạng = dừng toàn bộ probe
```

**Nguyên nhân:**
Network error xảy ra ở page 3 hoặc 7 → probe dừng → `total_pages` lưu giá trị sai → `is_images_complete()` thấy 2/2 hoặc 6/6 → skip mãi mãi.

**Xử lý:**
Thêm `_probe_page()` với retry (3 lần, backoff 2s/4s/8s). Khi tất cả retry đều fail → skip page đó, KHÔNG dừng probe:
```python
elif status is None:
    # network error sau retry → bỏ qua page này, tiếp tục probe
    logger.warning(f"Skipping page {page:03d} in probe, continuing")
```

**Verify:** ch-046 probe đúng 21 pages, ch-067 đúng 21 pages, ch-163 đúng 19 pages.

**Phòng ngừa:**
Chapters có `total_pages` rất nhỏ (< 10) nên bị coi là suspicious. Cân nhắc thêm warning log nếu `total_pages < 10`.

---

### ERR-006 — `_reset_missing_epubs`: Dùng `batch_size` để tính EPUB filename

**Thời gian:** 2026-06-01
**Component:** `main.py` — hàm `_reset_missing_epubs`

**Triệu chứng:**
Chạy `--batch-size 1` (để test chapter 219):
```
EPUB missing for chapters 001-001, resetting to re-pack
EPUB missing for chapters 002-002, resetting to re-pack
... (240 dòng)
Packing chapters 001-001 -> EPUB
Packing chapters 002-002 -> EPUB
... (240 EPUB riêng lẻ được tạo)
```

**Nguyên nhân:**
```python
# Code cũ — tính tên EPUB từ batch_size hiện tại
epub_path = output_dir / f"{title}_ch{start}-{end}.epub"
```
Chapters được pack với `batch_size=10` → `ch001-010.epub`. Nhưng repair chạy với `batch_size=1` → tìm `ch001-001.epub` (không tồn tại) → reset tất cả → re-pack 240 file riêng lẻ.

Thêm vào đó: repair chạy trên TẤT CẢ packed chapters trong manifest, không lọc theo range hiện tại.

**Xử lý:**
Redesign hoàn toàn:
1. Bỏ `batch_size` khỏi hàm
2. Scan file EPUB thực tế trên disk để xác định coverage
3. Chỉ xử lý chapters trong range hiện tại (`range_keys`)

```python
def _reset_missing_epubs(manifest, output_dir, title, range_keys, log):
    packed_in_range = [k for k in range_keys if manifest.is_packed(k)]
    covered = set()
    for epub in output_dir.glob(f"{title}_ch*.epub"):
        start_key, end_key = epub.stem.split("_ch")[-1].split("-")
        for key in packed_in_range:
            if start_key <= key <= end_key:
                covered.add(key)
    uncovered = [k for k in packed_in_range if k not in covered]
    manifest.reset_to_downloaded(uncovered)
```

**Verify:** Chạy lại với `--batch-size 1` sau fix → chỉ reset chapters trong range, không đụng chapters ngoài range.

---

### ERR-007 — Pack phase: Pool toàn bộ manifest → EPUBs sai khi có gap

**Thời gian:** 2026-06-01
**Component:** `main.py` — pack phase

**Triệu chứng:**
Sau khi download ch-046 (range 41-50), pack phase tạo ra:
```
one-piece_ch041-050.epub  ✅
one-piece_ch061-161.epub  ❌ (gộp chapters 061-066, 068-070, 161!)
one-piece_ch162-170.epub  ❌ (thiếu 163)
```

**Nguyên nhân:**
```python
all_ready = manifest.get_downloaded_chapters()  # ALL chapters toàn bộ manifest
```
Chapters 061-070 (reset để fix ch-067) và 161-170 (reset để fix ch-163) đều là "downloaded". Pack phase gộp chúng vào cùng sorted list với chapters 041-050 → batch by count → lệch range.

**Xử lý:**
Lọc `all_ready` chỉ giữ chapters trong `range_keys` của lần chạy hiện tại:
```python
range_key_set = set(range_keys)
all_ready = [k for k in manifest.get_downloaded_chapters() if k in range_key_set]
```

**Verify:**
- `--start-chapter 61 --end-chapter 70` → chỉ tạo `ch061-070.epub` ✅
- `--start-chapter 161 --end-chapter 170` → chỉ tạo `ch161-170.epub` ✅
