# AI_UI_GUIDE — Bản đồ UI để QC eyes-test nhanh

Tài liệu này giúp QC test giao diện mà không phải đọc source. Cập nhật sau mỗi
thay đổi UI.

## Cách chạy để eyes-test Editor

```bash
python scripts/launch_editor_demo.py
```

- Mở cửa sổ `EditorWindow` THẬT (không offscreen) với một ảnh mẫu 1280×800.
- Cửa sổ ở chế độ **windowed** 1100×720 (căn giữa màn hình, KHÔNG maximize/
  fullscreen) → kéo resize được; cố ý nhỏ hơn ảnh mẫu để thử scroll/zoom và ca
  thu nhỏ cửa sổ → menu ">>".
- Ảnh mẫu (do `make_sample_image`) có sẵn: nền gradient xanh chéo, 1 hình chữ
  nhật bo góc, 1 elip, 1 tam giác, 1 đường thẳng, tiêu đề "Editor Demo — Eyes
  Test" và đoạn chữ mô tả ở góc dưới phải → đủ nội dung để thử
  move/resize/style trên vùng có sẵn lẫn vẽ object mới.
- Đóng cửa sổ để thoát.
- Kiểm dựng-không-lỗi (không hiện cửa sổ, tự thoát ngay):
  `QT_QPA_PLATFORM=offscreen python scripts/launch_editor_demo.py` (EXIT=0 là OK).

## Màn hình Editor — các vùng chính

| Vùng | Mô tả | Cách tới |
|------|-------|---------|
| Toolbar (trái/trên) | Các tool: arrow, rect, ellipse, pen, text, highlight, step, stamp, spotlight, blur, crop, callout | Click icon hoặc phím tắt |
| Canvas (giữa) | Vùng ảnh để vẽ/chọn/move/resize object | Kéo chuột |
| Panel thuộc tính (phải) | Nhóm style theo object đang chọn: màu/độ dày/cỡ chữ/Opacity/Shadow/Tô nền + Express Styles (6 preset) | Tự hiện khi chọn tool/object |
| Dải "Ảnh gần đây" (dock dưới) | Filmstrip thumbnail 12 ảnh mới nhất (chỉ ảnh, bỏ video); click để chuyển ảnh edit; ảnh ĐANG mở có viền accent `#1E90FF` | Tự hiện khi có ảnh gần đây; ẩn khi rỗng |
| Status bar (dưới) | Hint thao tác + kích thước ảnh/khi resize | — |
| Empty state | CTA khi chưa có ảnh | Khi canvas trống |
| Toast | Thông báo khi Lưu/Copy/Export | Sau hành động tương ứng |

## Tiêu chí hiển thị đúng (rút gọn — chi tiết xem checklist ED2 ở board)

- Toolbar icon line-art (không emoji); hover/checked rõ; có tooltip + phím tắt.
- Mỗi tool vẽ ra đúng object; arrow preview là mũi tên thật.
- Direct-select: click trúng nét object → chọn + hiện 8 handle resize.
- Move handle bám realtime; cursor đổi đúng; Shift giữ tỉ lệ, Alt từ tâm; phím
  mũi tên nudge 1/10px.
- Panel phải áp style đúng + undo/redo; Express Styles áp combo.
- Callout: kéo vẽ to/nhỏ, double-click sửa chữ, kéo handle thì chữ co theo.
- Zoom in/out/fit/100% + Ctrl+wheel; thu nhỏ cửa sổ → menu ">>" có
  "Thu nhỏ"/"Phóng to".
- Phím 1-ký-tự (A/R/T…) KHÔNG nuốt khi đang gõ trong text/callout; Backspace khi
  gõ text không xoá object.

## Màn hình Thư viện (Library) — theme tối (LIB1)

Tiêu đề cửa sổ: `SnagTin - Thư viện`. Đã đồng bộ theme với Editor (nền tối
`#2B2D31`, accent `#1E90FF`).

| Vùng | Mô tả | Cách tới |
|------|-------|---------|
| Toolbar trên (`Chụp & Quay`) | 3 nút: **Chụp vùng / Chụp toàn màn hình / Quay video** — icon line-art (capture_region/capture_full/video) + chữ bên phải (ToolButtonTextBesideIcon), KHÔNG còn emoji | Click nút hoặc phím tắt Ctrl+Shift+A/F/R |
| Hàng tìm kiếm | Ô `QLineEdit` có icon kính lúp line-art bên trái (LeadingPosition) + placeholder "Tìm theo tên hoặc tag..." + nút "Làm mới" | Gõ để lọc realtime |
| Lưới thumbnail (`QListWidget` IconMode) | Card ảnh/video; item chọn nền xanh `#1E90FF`, hover nền `#3E4248` + viền `#55585E`. Nhãn KHÔNG emoji: video hiện duration (mm:ss) + play badge tam giác; tag prefix `#` | Double-click = mở editor / phát video |
| Thanh dưới | Nút "Mở trong Editor" / "Sửa tag" / "Xoá" + label đếm "{n} ảnh · {n} video" | — |
| Empty state (`#emptyState`) | Khi thư viện trống: card nền `#3A3D42` bo góc gồm title "Thư viện đang trống", sub (phím tắt, KHÔNG emoji) + 3 nút CTA có icon line-art (Chụp vùng/Chụp toàn màn hình primary `#1E90FF`, Quay video `#secondary`) | Khi không có capture; nút emit đúng signal chụp/quay |

Tiêu chí hiển thị đúng (LIB1):
- Toàn bộ nền tối `#2B2D31`, KHÔNG còn vùng trắng mặc định Qt.
- Toolbar `#33363B`; nút hover có nền `#3E4248` viền `#55585E`.
- Ô tìm kiếm nền `#3E4248`, viền focus chuyển xanh `#1E90FF`.
- Nút bấm (Làm mới/Mở/Sửa tag/Xoá) nền `#3E4248`, chữ sáng `#E8E8E8`.
- 3 nút toolbar là icon line-art đơn sắc (cùng bộ với Editor), không emoji.
- Chữ (count_label, empty_hint) sáng, đủ tương phản trên nền tối.

## Tray menu (menu helper) + Dialog cập nhật (UPD2)

Menu khay hệ thống (`app_controller._build_tray`) thêm — TRƯỚC mục "Thoát":
- Nhãn **"Về snapzhot (phiên bản 0.1.0)"** — disabled, chỉ để user thấy version hiện tại.
- Mục **"Kiểm tra cập nhật…"** → mở `_UpdateDialog` (theme tối).

Hộp thoại `_UpdateDialog` (tiêu đề "Cập nhật snapzhot", nền `#2B2D31`, nút primary
`#1E90FF`, label `#C8C8C8`). Việc kiểm tra chạy ở **luồng nền** (`QThread` +
`_UpdateCheckWorker`) → bấm nút KHÔNG làm đơ tray/dialog. **5 trạng thái** trong cùng
dialog (đổi nội dung tại chỗ):

| Trạng thái | Hiển thị | Nút chính |
|------------|----------|-----------|
| **Idle** (mở dialog) | "Phiên bản hiện tại: 0.1.0" | "Kiểm tra cập nhật" (enabled) |
| **Đang kiểm tra** | "Đang kiểm tra…" | disabled (đang chạy luồng nền) |
| **Có bản mới** | "Đã có phiên bản mới: {latest} (bạn đang dùng {current})" + ô notes (nếu manifest có) | **"Tải về"** → mở URL bằng trình duyệt (`QDesktopServices.openUrl`); nếu manifest thiếu `url` → nút disable + tooltip |
| **Đã mới nhất** | "Bạn đang dùng phiên bản mới nhất." | "Kiểm tra lại" |
| **Lỗi** | Thông điệp tiếng Việt từ `updater` (vd "Không kết nối được tới máy chủ cập nhật…") | "Thử lại" |

Nút phụ "Đóng"/"Để sau" đóng dialog. Nguồn manifest = config key `update_manifest_url`
(mặc định placeholder `updater.UPDATE_MANIFEST_URL`).

Brief eyes-test QC (offscreen-safe — **monkeypatch `updater.check_for_updates`** để giả
lập từng ca, KHÔNG cần mạng; xem `scripts/test_update_dialog.py`):
- 5 trạng thái render đúng + theme tối nhất quán Editor/Library.
- Bấm "Kiểm tra cập nhật" → chuyển "Đang kiểm tra…" NGAY (GUI không đơ), rồi ra kết quả.
- Ca "Có bản mới": nút "Tải về" mở đúng URL; ca url rỗng → nút disable.
- Tray có nhãn version + mục "Kiểm tra cập nhật…".

## Dải "Ảnh gần đây" (filmstrip — REC1)

`QDockWidget` objectName `recentDock` ở **BottomDockWidgetArea** (giữa canvas và
bottom toolbar), tiêu đề "Ảnh gần đây", NoDockWidgetFeatures (không đóng/kéo).
Bên trong là `QListWidget` objectName `recentStrip` chế độ IconMode ngang (icon
72px, dock cao 96px, không wrap, scroll ngang khi tràn).

- Mỗi item = 1 ảnh; tooltip = tên file. Click thumbnail KHÁC → editor load ảnh đó.
- Ảnh **đang mở** = item selected, viền accent `#1E90FF` (QSS `#recentStrip::item:selected`),
  hover viền `#55585E` nền `#3E4248`.
- Danh sách = **12 ảnh mới nhất** (mới → cũ), CHỈ ảnh (video bị bỏ).
- **Rỗng → ẩn dock** (không để khoảng trống).
- Cập nhật mỗi khi: chụp ảnh mới, lưu trong editor, mở ảnh từ thư viện/filmstrip.

Sau khi **chụp xong** (hoặc mở ảnh từ thư viện), editor được đưa lên foreground bền
vững: un-minimize (`setWindowState`) + `show/raise_/activateWindow` → user thấy ngay
để copy/chỉnh sửa.

Tiêu chí hiển thị đúng (REC1):
- Filmstrip nằm gọn dưới canvas, thumbnail rõ, theme tối nhất quán.
- Ảnh đang mở có viền xanh `#1E90FF`; click ảnh khác → canvas load đúng ảnh +
  viền nhảy theo (highlight đồng bộ với `_current_capture_id`).
- Không có ảnh nào → dock biến mất hẳn.
- Live-only (user phiên thật): sau chụp editor bật foreground thật, không kẹt dưới.

**Xoá ảnh từ filmstrip (REC2):**
- **Right-click** một thumbnail → menu tối "Xoá ảnh"; hoặc chọn item rồi nhấn **Delete**.
- Hỏi xác nhận `QMessageBox` (mặc định **No**) "Xoá ảnh này khỏi thư viện?": No →
  không xoá; Yes → ảnh biến mất khỏi strip + thư viện refresh.
- Xoá ảnh **đang mở** → editor tự nhảy sang ảnh **mới nhất còn lại** (highlight đúng);
  xoá tới hết → strip ẩn gọn.

## API liên quan (cho người dựng launcher/test)

- `EditorWindow()` — không tham số.
- `EditorWindow.load_image(image: QImage, capture_id: int | None = None)`.
- `EditorWindow.set_recent_captures(items: list[dict])` — item `{"id","thumb","label"}`.
- Signal `EditorWindow.open_capture_requested = Signal(int)` — phát capture_id khi
  click thumbnail (controller connect tới `_open_capture_in_editor`).
- Signal `EditorWindow.delete_capture_requested = Signal(int)` — phát capture_id khi
  user xác nhận xoá (right-click "Xoá ảnh" / phím Delete); controller connect tới
  `_on_delete_capture`.

## Thay đổi gần đây

- 2026-06-25 (ED1): Thêm `scripts/launch_editor_demo.py` — launcher mở Editor
  thật với ảnh mẫu để QC eyes-test. CHỈ thêm script, không sửa module `app/`.
- 2026-06-25 (LIB1): Màn Thư viện (`app/library/library_window.py`) đổi sang theme
  tối đồng bộ Editor: thêm `LIBRARY_QSS`, toolbar chụp dùng icon line-art thay
  emoji (Chụp vùng/Chụp toàn màn hình/Quay video), bỏ label 🔍 ở hàng tìm kiếm.
  Logic/signals/luồng mở editor giữ nguyên. (Empty state nâng cấp ở LIB2.)
- 2026-06-25 (LIB2): Toolbar đặt `objectName("captureBar")` + QSS `#captureBar`
  nền `#33363B` (fix bị nền thân đè). Thay `empty_hint` bằng empty-state card
  (`#emptyState`): title + sub không emoji + 3 nút CTA icon line-art emit signal
  chụp/quay (mirror #emptyState Editor). `_make_item` vẫn còn emoji 🏷/🎬 (để LIB3).
- 2026-06-25 (LIB3): Polish cuối — bỏ nốt emoji ở lưới (`_make_item`: video chỉ
  duration + play badge, tag prefix `#`); ô tìm kiếm có icon kính lúp line-art
  (drawer `search` mới trong tool_icons, ADDITIVE — Editor không đổi); item lưới
  có viền hover `#55585E`. Library nay đồng bộ theme với Editor, không còn tofu.
- 2026-06-25 (UPD2): Tray menu thêm nhãn version (disabled) + "Kiểm tra cập nhật…"
  → `_UpdateDialog` theme tối 5 trạng thái (idle/đang kiểm tra/có bản mới+Tải về/
  đã mới nhất/lỗi). Kiểm tra chạy luồng nền (`QThread`+`_UpdateCheckWorker`) nên
  không đơ. Chỉ thêm vào `app_controller.py` (additive), không đụng luồng chụp/quay.
  Harness `scripts/test_update_dialog.py` (monkeypatch `updater.check_for_updates`).
- 2026-06-26 (REC2): Editor cho xoá ảnh ngay từ filmstrip — right-click thumbnail →
  menu "Xoá ảnh" / phím Delete khi strip focus, confirm `QMessageBox` default No →
  signal `delete_capture_requested(int)` → controller `_on_delete_capture` (xoá qua
  `library.delete`, refresh, xoá ảnh đang mở→nhảy ảnh mới nhất còn lại). KHÔNG đụng
  library_manager/library_window. Harness `scripts/test_recent_delete.py`.
- 2026-06-26 (REC1): Editor thêm dải "Ảnh gần đây" (filmstrip) ở dock dưới —
  `QListWidget#recentStrip` IconMode ngang, 12 ảnh mới nhất (bỏ video), click chuyển
  ảnh, ảnh đang mở viền `#1E90FF`, rỗng→ẩn dock. `editor_window.py` thêm signal
  `open_capture_requested(int)` + `set_recent_captures()` + `_sync_recent_highlight()`
  (load_image giữ nguyên signature, chỉ thêm gọi sync). `app_controller.py` connect
  signal → `_open_capture_in_editor`, helper `_refresh_editor_recents()` (gọi sau
  chụp/lưu/mở), và `_raise_editor()` un-minimize+raise editor sau khi chụp. Harness
  `scripts/test_recent_strip.py`.
