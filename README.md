# snapzhot — Phần mềm chụp màn hình, thư viện & vẽ chú thích

> **Tên hiển thị trong app**: `snapzhot` (v0.1.2) — file EXE đóng gói: `SnagTin.exe`.

Bản clone tối giản của Snagit, viết bằng **Python + PySide6 (Qt)**, đóng gói được thành `.exe` chạy trên Windows. Gồm 3 phần như Snagit:

1. **Capture** — chụp **vùng chọn**, **toàn màn hình** (đa màn hình), **chụp cửa sổ** (highlight cửa sổ dưới con trỏ), và **chụp hẹn giờ** (đếm ngược 3s/5s).
2. **Library** — thư viện ảnh **và video** đã chụp, lưu trong SQLite, tìm kiếm & gắn tag; **trình phát video nhúng** ngay trong app.
3. **Editor** — canvas vẽ chú thích: mũi tên, chữ nhật, elip, bút vẽ, chữ, đánh dấu (highlight), làm mờ (blur), **đánh số bước (step)**, **cắt ảnh (crop)**, **stamp (chèn biểu tượng — 6 glyph)**, **tiêu điểm (spotlight — làm tối ngoài vùng chọn)**; panel phải có **Express Styles (6 preset)**, **Độ trong (Opacity)**, **Đổ bóng (Shadow)**, **Tô nền (Fill)** cho chữ nhật/elip; có **Zoom** (in/out/fit/100% + Ctrl+lăn chuột) và **Hoàn tác/Làm lại (Undo/Redo)** nhiều bước.
4. **Recording** — **quay video toàn màn hình** xuất MP4 (H.264), tùy chọn **quay kèm âm thanh micro**.

## Cài đặt & chạy (chế độ phát triển)

```powershell
pip install -r requirements.txt
python main.py
```

`requirements.txt` gồm: `PySide6` (Qt, kèm QtMultimedia cho trình phát video), `mss` (chụp/quay), `keyboard` (phím tắt toàn cục), `imageio` + `imageio-ffmpeg` (ghi/ghép video), `numpy`, **`pywin32`** (chụp cửa sổ — chỉ Windows), **`sounddevice`** + **`soundfile`** (thu âm micro). Hai nhóm cuối là *tùy chọn*: thiếu chúng app vẫn chạy, chỉ tắt tính năng tương ứng.

App chạy ở **khay hệ thống** (system tray, icon chấm đỏ). Lần đầu sẽ mở cửa sổ Thư viện.

### Phím tắt toàn cục (mặc định)
| Phím | Chức năng |
|------|-----------|
| `Print Screen` | Chụp vùng chọn *(mặc định; có thể tuỳ chỉnh — xem bên dưới)* |
| `Ctrl+Shift+F` | Chụp toàn màn hình |
| `Ctrl+Shift+R` | Bật/tắt quay video toàn màn hình |
| `Ctrl+Z` / `Ctrl+Y` | Hoàn tác / Làm lại (trong Editor) |
| `Esc` | Hủy đếm ngược / Dừng quay (khi đang đếm ngược hoặc quay video) |

> Phím tắt toàn cục dùng thư viện `keyboard`; một số máy cần chạy với **quyền Administrator**. Nếu không, vẫn dùng được mọi chức năng qua **menu chuột phải ở khay hệ thống**.

**Tuỳ chỉnh phím chụp vùng**: Trong menu khay → **"Cài đặt phím tắt chụp vùng…"** → nhấn tổ hợp phím mới → OK. Phím mới được lưu vào file cấu hình và có hiệu lực ngay.

### Thao tác chính
- **Chụp** (qua phím tắt hoặc menu khay) → ảnh tự lưu vào thư viện và mở trong Editor.
- **Chụp cửa sổ** (menu khay → "Chụp cửa sổ"): di chuột tới cửa sổ cần chụp, khung được highlight, bấm chọn. *(Cần `pywin32` trên Windows; thiếu thì báo và bỏ qua, không ảnh hưởng tính năng khác.)*
- **Chụp hẹn giờ** (menu khay → "Chụp hẹn giờ" → 3s/5s): đếm ngược hiển thị to giữa màn hình rồi tự chụp toàn màn hình.
- **Vẽ**: chọn công cụ ở thanh trên, chỉnh **màu / độ dày / cỡ chữ / số bước** ở panel phải.
- **Phím tắt 1 phím trong Editor**: `V` Chọn · `A` Mũi tên · `R` Chữ nhật · `E` Elip · `P` Bút · `T` Chữ · `H` Đánh dấu · `B` Mờ · `S` Bước · `C` Cắt · `M` Stamp · `F` Tiêu điểm · `O` Callout.
- **Express Styles**: dải 6 preset ở đầu panel phải — click một preset để áp ngay bộ màu/độ dày/đổ bóng/tô nền cho đối tượng đang chọn (một bước Undo).
- **Độ trong / Đổ bóng**: chỉnh **Opacity** và bật/tắt **Shadow** cho mọi đối tượng chú thích.
- **Tô nền (Fill)**: bật và chọn màu nền cho **chữ nhật / elip**.
- **Stamp** (công cụ `M`): click để chèn biểu tượng vector (check/cross/star/heart/exclaim/pin); chọn, di chuyển, đổi kích thước & đổi màu như mọi đối tượng.
- **Tiêu điểm/Spotlight** (công cụ `F`): kéo một vùng — mọi thứ ngoài vùng bị làm tối để làm nổi vùng bên trong; là lớp phủ vector, hoàn tác được.
- **Callout/Bong bóng thoại** (công cụ `O`): click để đặt bong bóng chú thích có đuôi nhọn rồi gõ nội dung; đổi **màu viền/chữ, độ dày viền, cỡ chữ** và **màu nền bong bóng** (khi chọn) như mọi đối tượng — di chuyển, đổi kích thước, hoàn tác đầy đủ.
- **Cắt ảnh (Crop ⛶)**: chọn công cụ Cắt, kéo vùng cần giữ → ảnh được cắt, **chú thích vẫn giữ nguyên** (không bị làm phẳng) và cắt được hoàn tác bằng Undo.
- **Zoom**: nút `＋` `－` `Vừa khung` `100%` trên toolbar, hoặc `Ctrl+=` / `Ctrl+-` / `Ctrl+0` / `Ctrl+1`, hoặc **Ctrl + lăn chuột** để zoom tại con trỏ. Zoom không ảnh hưởng ảnh xuất ra.
- **Đánh số bước** (①): mỗi lần click đặt một badge số tăng dần; chỉnh "Số kế tiếp" hoặc "Reset = 1" ở panel.
- **Hoàn tác/Làm lại**: nút ↶ ↷ trên toolbar hoặc `Ctrl+Z` / `Ctrl+Y` — áp dụng cho mọi thao tác kể cả blur, crop, di chuyển, xoá.
- **Chọn/di chuyển/xoá**: công cụ "Chọn" (↖), nhấn `Delete` để xoá đối tượng đang chọn.
- **Lưu vào thư viện / Xuất ra file / Copy** ở thanh dưới Editor.
- **Quay video**: `Ctrl+Shift+R` (hoặc menu khay → "Quay video toàn màn hình") → thanh điều khiển nổi hiện ra với **Tạm dừng / Dừng** và đồng hồ. Dừng xong (hoặc nhấn `Esc`) video tự lưu vào thư viện. *(Luôn quay toàn màn hình — không chọn vùng.)*
- **Quay kèm âm thanh micro**: bật mục **"Quay kèm âm thanh micro"** ở menu khay (checkable). Khi quay, mic được thu song song rồi ghép (mux) vào MP4. Thiếu thiết bị/thư viện thu âm thì tự động quay không tiếng (video vẫn hợp lệ).
- **Thư viện**: ảnh → double-click mở trong Editor; video (có badge ▶) → double-click mở bằng **trình phát nhúng** (Play/Pause, thanh tua, thời gian, âm lượng). Sửa tag, xoá như nhau.
- **Khởi động cùng Windows**: menu khay → bật/tắt **"Khởi động cùng Windows"** — ghi vào registry HKCU\…\Run, không cần quyền admin.
- **Kiểm tra cập nhật**: menu khay → **"Kiểm tra cập nhật…"** — tải manifest JSON từ GitHub Release, so version, hiện hộp thoại với nút "Tải về" nếu có bản mới.

## Đóng gói thành EXE

```powershell
build_exe.bat
```

File kết quả: thư mục **`dist\SnagTin\`** chứa `SnagTin.exe` và các thư viện đi kèm (onedir — khởi động nhanh hơn onefile). Cấu hình build nằm trong `SnagTin.spec`.

Để tạo **installer** (`dist\SnagTin-Setup-<ver>.exe`):

```powershell
build_setup.bat   # cần Inno Setup 6 cài sẵn
```

## Cấu trúc dự án

```
snagit_tin/
├─ main.py                     # điểm khởi động
├─ build_exe.bat               # đóng gói PyInstaller (onedir → dist\SnagTin\)
├─ build_setup.bat             # tạo installer Inno Setup (cần ISCC.exe)
├─ SnagTin.spec                # cấu hình PyInstaller (icon, hidden imports, excludes)
├─ requirements.txt
└─ app/
   ├─ __init__.py              # APP_NAME = "snapzhot", __version__ = "0.1.2"
   ├─ app_controller.py        # điều phối: tray, hotkey, nối 3 module
   ├─ updater.py               # kiểm tra cập nhật qua manifest JSON trên GitHub
   ├─ common/
   │  ├─ paths.py              # đường dẫn lưu dữ liệu (%LOCALAPPDATA%\SnagTin)
   │  ├─ config.py             # cấu hình JSON (hotkey, fps, autostart…)
   │  ├─ assets.py             # tải icon đa độ phân giải (nội bộ)
   │  ├─ autostart.py          # bật/tắt khởi động cùng Windows (registry HKCU Run)
   │  └─ settings_dialog.py    # hộp thoại tuỳ chỉnh phím tắt chụp vùng
   ├─ capture/
   │  ├─ capture_manager.py    # chụp bằng mss -> QImage
   │  ├─ region_selector.py    # overlay kéo chọn vùng
   │  ├─ window_selector.py    # overlay chụp cửa sổ (win32gui, có fallback)
   │  └─ countdown_overlay.py  # overlay đếm ngược cho chụp hẹn giờ
   ├─ library/
   │  ├─ library_manager.py    # SQLite + thumbnail + tag + video (migration)
   │  ├─ library_window.py     # lưới thumbnail (ảnh + video)
   │  ├─ video_player.py       # trình phát video nhúng (QtMultimedia)
   │  └─ video_editor.py       # cắt/mute video qua ffmpeg (nội bộ, chưa có UI)
   ├─ editor/
   │  ├─ canvas.py             # QGraphicsView + vẽ + blur + step + crop + zoom + undo
   │  ├─ commands.py           # các QUndoCommand (add/delete/move/blur/crop)
   │  ├─ editor_window.py      # toolbar + Undo/Redo + Zoom + panel Tool Properties
   │  └─ tool_icons.py         # icon công cụ vẽ runtime bằng QPainter (nội bộ)
   └─ recording/
      ├─ recorder.py           # quay video QThread (mss + imageio/ffmpeg)
      ├─ audio_recorder.py     # thu mic ra WAV + mux audio/video (có fallback)
      └─ record_bar.py         # thanh điều khiển quay nổi
```

Dữ liệu người dùng (ảnh, video, DB, cấu hình) nằm ở: `%LOCALAPPDATA%\SnagTin`

## Hướng phát triển tiếp (so với Snagit)
- **Chỉnh sửa video** (Trim/Mute) có sẵn module `video_editor.py` (dùng ffmpeg), cần tích hợp UI vào thư viện.
- Thu **âm thanh hệ thống** (loopback) song song với mic.
- Chụp **cuộn trang** (scrolling capture).
- Chia sẻ trực tiếp (clipboard đã có; thêm upload).
