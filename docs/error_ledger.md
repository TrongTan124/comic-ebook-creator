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
| ERR-008 | main.py | Git merge conflict markers còn sót → SyntaxError khi chạy Python | 2026-06-09 | Fixed |
| ERR-009 | main.py / KCC | Flag `-S` (hoa) không tồn tại trong KCC → rc=2 | 2026-06-10 | Fixed |
| ERR-010 | main.py / KCC | KCC không nhận `.webp` trong CBZ → "No matching files found" | 2026-06-10 | Fixed |
| ERR-011 | main.py / KCC | KCC cần absolute path — relative path → "No matching files found" | 2026-06-10 | Fixed |
| ERR-012 | main.py / KCC | KCC v10 cần KindleGen (deprecated) → chuyển sang Kindle Previewer 3 | 2026-06-10 | Fixed |
| ERR-013 | main.py / KP3 | Tên exe KP3 là `Kindle Previewer 3.exe`, không phải `KindlePreviewer.exe` | 2026-06-10 | Fixed |
| ERR-014 | main.py / KP3 | Argument order KP3 CLI sai (`-convert input` thay vì `input -convert`) | 2026-06-10 | Fixed |
| ERR-015 | main.py / KP3 | KP3 output vào subdirectory `Mobi\` → `glob` không tìm thấy, cần `rglob` | 2026-06-10 | Fixed |

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

---

### ERR-008 — main.py: Git merge conflict markers gây SyntaxError

**Thời gian:** 2026-06-09
**Component:** `main.py`

**Triệu chứng:**
```
File "main.py", line 117
    >>>>>>> 2b4b8ea2bd7e0177ede21a02f3bf9a2478733024
            ^
SyntaxError: invalid decimal literal
```

**Nguyên nhân:**
Commit `2b4b8ea` (fix chapter sort 1000+) thêm hàm `_key_num` và cập nhật `_reset_missing_epubs` để dùng numeric comparison. Khi tôi edit `main.py` cùng lúc (thêm `convert_to_azw3` và mở rộng `_reset_missing_epubs` để check cả `.azw3`), git tạo conflict markers nhưng không được resolve trước khi chạy.

**Xử lý:**
Resolve 2 conflict blocks:
1. Giữ `convert_to_azw3` (HEAD) + thêm `_key_num` (branch) ngay sau
2. Merge `_reset_missing_epubs`: check cả `.epub` và `.azw3` patterns (HEAD) + dùng `_key_num` cho numeric comparison (branch)

**Verify:** `python -m py_compile main.py` → OK

**Phòng ngừa:**
Sau mỗi lần merge/pull, chạy `python -m py_compile main.py` để phát hiện conflict markers sót trước khi chạy tool.

---

### ERR-009 — KCC flag `-S` không tồn tại

**Thời gian:** 2026-06-10
**Component:** `main.py` — `convert_to_azw3`

**Triệu chứng:** `KCC failed (rc=2), falling back to Calibre`

**Nguyên nhân:** Dùng `-S` (hoa) thay vì `-s` (thường) cho flag stretch. KCC help: `-s, --stretch`.

**Xử lý:** Đổi `-S` → `-s`.

**Verify:** KCC chạy qua bước này, tiếp tục xử lý.

---

### ERR-010 — KCC không nhận `.webp` trong CBZ

**Thời gian:** 2026-06-10
**Component:** `main.py` — `_pack_cbz`

**Triệu chứng:** `No matching files found.` (KCC rc=1)

**Nguyên nhân:** Chapter folders chứa `.webp` từ CDN. KCC không xử lý WebP — chỉ nhận JPEG/PNG.

**Xử lý:** Trong `_pack_cbz`, convert `.webp` → JPEG in-memory (Pillow, quality=92) trước khi write vào CBZ.

**Verify:** KCC nhận file, tiến tới bước tiếp theo.

---

### ERR-011 — KCC cần absolute path

**Thời gian:** 2026-06-10
**Component:** `main.py` — `convert_to_azw3`

**Nguyên nhân:** `str(cbz_path)` với relative path → KCC báo "No matching files found." (dù file tồn tại).

**Xử lý:** Dùng `.resolve()` cho `cbz_path`, `mobi_path`, và `epub_path.parent` khi truyền vào subprocess.

**Verify:** KCC bắt đầu xử lý `Working on E:\...`.

---

### ERR-012 — KCC v10 cần KindleGen (đã bị deprecated)

**Thời gian:** 2026-06-10
**Component:** `main.py` — `convert_to_azw3`

**Triệu chứng:** `ERROR: KindleGen is missing!`

**Nguyên nhân:** KCC v10 dùng KindleGen để tạo MOBI. Amazon ngừng cung cấp KindleGen từ 2021.

**Xử lý:** Chuyển primary pipeline sang Kindle Previewer 3 CLI (tool chính thức từ Amazon, miễn phí). KP3 convert fixed-layout EPUB → MOBI đúng chuẩn. Calibre CBZ→MOBI giữ làm fallback.

**Verify:** KP3 tạo được `one-piece_ch001-010.mobi`.

---

### ERR-013 — Tên exe KP3 sai

**Thời gian:** 2026-06-10
**Component:** `main.py` — `_find_kindle_previewer`

**Triệu chứng:** `Kindle Previewer 3 not found` dù đã cài.

**Nguyên nhân:** Code tìm `KindlePreviewer.exe`. Amazon đặt tên file thực tế là `Kindle Previewer 3.exe` (có khoảng trắng).

**Xử lý:** Cập nhật `_find_kindle_previewer` tìm cả `Kindle Previewer 3.exe`.

**Verify:** `_find_kindle_previewer()` trả về đúng path.

---

### ERR-014 — Argument order KP3 CLI sai

**Thời gian:** 2026-06-10
**Component:** `main.py` — `convert_to_azw3`

**Triệu chứng:** `Unknown file given as input.` + rc=0 (KP3 exit 0 kể cả khi lỗi usage)

**Nguyên nhân:** Code gọi `[kp3_exe, "-convert", str(abs_epub), "-output", ...]`. KP3 syntax yêu cầu: `kindlepreviewer <input> -convert -output <dir>` — input phải đứng trước command.

**Xử lý:** Đổi thành `[kp3_exe, str(abs_epub), "-convert", "-output", str(out_dir)]`.

**Verify:** KP3 hiện `Pre-processing in progress.` và xử lý file.

---

### ERR-015 — KP3 output vào subdirectory `Mobi\`

**Thời gian:** 2026-06-10
**Component:** `main.py` — `convert_to_azw3`

**Triệu chứng:** `Kindle Previewer produced no output (rc=0)` dù KP3 báo "Book converted successfully!"

**Nguyên nhân:** KP3 tạo output trong `Mobi\` subdirectory bên trong output folder, không phải top-level. `out_dir.glob("*.mobi")` không tìm thấy.

**Xử lý:** Đổi sang `out_dir.rglob("*.mobi")` (và `.azw3`, `.kpf`). Sau khi tìm thấy file, rename về top-level, xóa subdirectory `Mobi\` nếu rỗng.

**Verify:** `Kindle file created via KP3 (full-bleed): one-piece_ch001-010.mobi`
