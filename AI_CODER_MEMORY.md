# AI_CODER_MEMORY — Bộ nhớ riêng của Coder

## Đã làm
- REC2 (2026-06-26): Xoá ảnh từ filmstrip Editor. CHỈ 2 file source (additive),
  KHÔNG đụng library_manager/library_window, KHÔNG đổi `load_image`. editor_window.py:
  signal `delete_capture_requested(int)`; `_build_recent_dock` thêm
  `setContextMenuPolicy(CustomContextMenu)` + `customContextMenuRequested` +
  `installEventFilter(self)`; `_on_recent_context_menu` (QMenu "Xoá ảnh" exec tại
  `viewport().mapToGlobal(pos)`); `_request_delete_capture` (QMessageBox.question
  Yes|No **default No** → emit); `eventFilter` thêm nhánh `obj is recent_strip +
  Key_Delete` → `_request_delete_capture(currentItem)`, return True nuốt phím (guard
  `getattr` vì eventFilter có thể chạy sớm). KHÔNG sửa `set_recent_captures` (impact
  CRITICAL theo caller → tránh). app_controller.py: connect→`_on_delete_capture`
  (was_current; `library.delete`; refresh + `_refresh_editor_recents`; nếu xoá ảnh
  đang mở+còn ảnh→`_open_capture_in_editor(list_captures()[0].id)` mới nhất; hết→
  để nguyên không crash). Verify `scripts/test_recent_delete.py` (FakeLibrary +
  monkeypatch QMessageBox.question). Launcher demo connect signal→handler local cho
  QC. BÀI HỌC: FakeCap phải có `thumbnail_path`+`filename` vì `_refresh_editor_recents`
  đọc cả 2 khi build items.
- REC1 (2026-06-26): Filmstrip "Ảnh gần đây" trong Editor + active-show sau chụp.
  CHỈ 2 file source (additive). editor_window.py: signal `open_capture_requested(int)`,
  `_build_recent_dock()` (QDockWidget#recentDock Bottom + QListWidget#recentStrip
  IconMode ngang, icon 72/h96, hide khi khởi tạo), `set_recent_captures(items)`
  (items {id,thumb,label}; rỗng→ẩn dock), `_sync_recent_highlight()` (chọn item
  khớp `_current_capture_id`, blockSignals tránh re-emit), `_on_recent_item_clicked`
  (no-op nếu là ảnh đang mở). `load_image` GIỮ NGUYÊN signature — chỉ thêm 1 dòng
  gọi `_sync_recent_highlight()` ở cuối (impact CRITICAL theo 3 caller → additive là
  bắt buộc). app_controller.py: connect signal→`_open_capture_in_editor`,
  `_refresh_editor_recents()` (lọc `not is_video`, `[:12]`, `str(thumbnail_path)`)
  gọi sau chụp/lưu/mở, `_raise_editor()` un-minimize
  `setWindowState((windowState() & ~Qt.WindowMinimized)|Qt.WindowActive)`+show/raise/
  activate. Verify `scripts/test_recent_strip.py` + regression PASS. Launcher demo
  thêm 6 thumb mẫu (capture_id=2) cho QC. BÀI HỌC: `_sync_recent_highlight` phải
  `hasattr(self,"recent_strip")` guard vì load_image có thể chạy trước build dock
  (an toàn thứ tự __init__). MVP debt: chuyển ảnh = reload từ đĩa, edit chưa lưu sẽ mất.

- UPD2 (2026-06-25): UI cập nhật trong tray menu (`app_controller.py`, CHỈ file này,
  additive). `_UpdateCheckWorker(QObject)` chạy `updater.check_for_updates` ở luồng
  nền (`QThread`+`moveToThread`, `Signal(object)` finished) → tray KHÔNG đơ dù check
  chặn tới 8s. `_UpdateDialog(QDialog)` theme tối 5 trạng thái (idle/checking/
  available+Tải về/latest/error), nút action đa-vai (available→`QDesktopServices.openUrl`,
  else→phát `check_requested`). `_build_tray` thêm nhãn version disabled + "Kiểm tra
  cập nhật…". Controller: `_open_update_dialog` giữ ref + WA_DeleteOnClose + clear ref
  ở finished; `_start_update_check` guard không chạy chồng, url=config
  `update_manifest_url`; `_on_update_checked` guard dialog None (có thể đã đóng);
  `shutdown` quit+wait luồng.
  BÀI HỌC harness threading offscreen: (1) monkeypatch `updater.check_for_updates`
  phải CỐ ĐỊNH qua holder dict — KHÔNG restore trong finally ngay sau vòng chờ, vì
  worker chạy luồng nền, restore về hàm-mạng-thật trước khi worker đọc attribute →
  race gọi nhầm hàm 8s. (2) Phải mô phỏng đúng luồng nút: `action_btn.click()` mới
  set dialog sang "checking" (gọi `_start_update_check` trực tiếp KHÔNG đổi mode dialog
  → vòng `while mode=='checking'` thoát ngay, chờ hụt). (3) Chờ kết quả luồng nền:
  `while mode=='checking': app.processEvents(); time.sleep(0.01)` tới khi show_result đổi mode.
- UPD1 (2026-06-25): Backend updater THUẦN STDLIB (urllib/json/re/dataclasses,
  KHÔNG thêm dependency) — 2 file MỚI, KHÔNG đụng app_controller/__init__.
  `app/updater.py`: `UPDATE_MANIFEST_URL` placeholder; `parse_version(s)` dùng
  `re.findall(r"\d+")` bỏ tiền tố v/V → tuple int (rỗng/không-số→`(0,)`, an toàn
  pre-release lấy mọi nhóm số); `is_newer(remote,local)` so tuple; `@dataclass
  UpdateInfo(available,current,latest,url,notes,error=None)`; `check_for_updates(
  current, manifest_url, timeout=8.0)` — Request set User-Agent, urlopen, json.loads;
  KHÔNG raise: bắt URLError→"không kết nối", (ValueError,UnicodeDecodeError)→"dữ liệu
  không hợp lệ", Exception→"có lỗi", thiếu/sai version→error riêng, đều trả
  UpdateInfo(available=False, error=<tiếng Việt>). `scripts/test_updater.py`
  monkeypatch `urllib.request.urlopen` (class `_FakeResp` hỗ trợ context-manager +
  `.read()`) cho 4 ca → `=== UPDATER OK ===`. Quyết: tách bóc try thành nhánh lỗi
  riêng để thông điệp thân thiện đúng loại, không gộp 1 except chung.
  Nợ kỹ thuật/CHỜ user chốt (Planner đã hỏi): nguồn thật GitHub Releases vs JSON tự
  host; cơ chế cài = mở trình duyệt (MVP) vs tự tải+chạy installer. UPD2 (UI tray
  menu + dialog) chờ chốt.
- ED1 (2026-06-25): Tạo `scripts/launch_editor_demo.py` — launcher mở
  `EditorWindow` THẬT (QApplication không offscreen) với ảnh mẫu 1280×800
  (`make_sample_image`: gradient + rect bo góc + elip + tam giác + line + chữ).
  Mục đích: cung cấp đường vào để QC eyes-test UI Editor (trước đó mọi script
  test đều headless/offscreen).

- ED3 (2026-06-25): FIX cửa sổ hẹp mất tool icon (editor_window.py): zoom toolbar
  `addToolBarBreak` xuống hàng riêng + undo/redo `ToolButtonIconOnly` để nhãn động
  không giãn bar che nút ">>".
- ED4 (2026-06-25): Callout chỉ vẽ khi KÉO (giống Rect). canvas.py: `_add_callout`
  đổi chữ ký `(self, rect: QRectF)` (bỏ nhánh click-place cũ); mouseReleaseEvent
  nhánh CALLOUT gate `rect.w>=_CALLOUT_MIN_DRAG and rect.h>=...` (=20px) mới gọi.
  Click đơn/kéo nhỏ → KHÔNG tạo (dành click cho chọn object). test_callout.py: gate
  test qua QMouseEvent thật vào viewport (cần `c.resize()` + `processEvents()` để
  view-transform khả nghịch — `mapFromScene` đúng).

- LIB1 (2026-06-25): Theme tối cho `app/library/library_window.py` (đồng bộ Editor).
  Thêm hằng `LIBRARY_QSS` (mirror `EDITOR_QSS`: nền #2B2D31, toolbar #33363B,
  QToolButton/QLineEdit/QPushButton/QListWidget + selection #1E90FF, QLabel #C8C8C8),
  áp `setStyleSheet(LIBRARY_QSS)` cuối __init__. Toolbar chụp: bỏ emoji, mỗi QAction
  `tool_icon(capture_region/capture_full/video)` + `ToolButtonTextBesideIcon` +
  `iconSize(20,20)`. Bỏ `QLabel("🔍")` và các `setStyleSheet` cũ (toolbar + empty_hint).
  KHÔNG đụng logic/signals/DB. empty_hint giữ emoji (LIB2 sẽ thay bằng empty-state
  CTA mirror #emptyState Editor).

- LIB2 (2026-06-25): Empty-state + fix nền toolbar (`library_window.py`).
  (A) `tb.setObjectName("captureBar")` + QSS `#captureBar { background:#33363B; }`.
  ID-selector thắng mọi type-selector → hết bị `QMainWindow > QWidget` đè (Planner
  chốt dùng ID thay vì `QMainWindow > QToolBar` vì cách kia cùng specificity với
  `QMainWindow > QWidget`, chỉ thắng nhờ thứ tự khai báo → dễ vỡ).
  (B) Bỏ `self.empty_hint`, thay bằng `self.empty_state` QWidget objectName
  "emptyState": emptyTitle + emptySub (không emoji) + hàng CTA 3 QPushButton có
  `tool_icon`, nút "Quay video" objectName "secondary". QSS mirror #emptyState
  Editor. `refresh()` đổi sang `empty_state.setVisible(empty)`.
  Verify offscreen: cần `w.show()` mới đọc đúng `isVisible()` của child (parent
  chưa show → child luôn False). CTA click emit đúng [region,full,video].

- LIB3 (2026-06-25): Polish cuối đồng bộ theme. (A) `_make_item` bỏ emoji: video
  `🎬 {dur}`→`{dur}` (play badge tam giác đã đánh dấu video), tag `🏷 `→`# `.
  (B) Search icon: thêm drawer `_draw_search` vào `app/editor/tool_icons.py` (kính
  lúp drawEllipse + drawLine tay cầm, style chung) + đăng ký `"search"`; trong
  library `search_box.addAction(tool_icon("search"), QLineEdit.LeadingPosition)`.
  ADDITIVE — không sửa drawer cũ → Editor không hồi quy (`test_tool_icons.py` tự
  liệt kê toàn `_DRAWERS`, lên 27 icon, vẫn pass). (C) QSS item: `border:1px solid
  transparent` + hover `border:1px solid #55585E` (viền chỉ hiện khi hover, không
  xáo layout). → Task ĐỒNG BỘ THEME Library↔Editor hoàn tất (chờ QC eyes-test).

- FX1+FX2+FX3 (2026-06-25): 3 fix độc lập.
  FX1 (editor_window.py): 4 toolbar `setObjectName` (captureBar/toolBar/zoomBar/
  bottomBar) + QSS ID-selector nền #33363B (cùng pattern Library — ID thắng
  `QMainWindow>QWidget`). Lưu ý captureBar còn inline `setStyleSheet` padding/spacing
  — không đụng vì chỉ set padding/spacing, app-QSS #captureBar vẫn áp background.
  FX2 (canvas.py mousePressEvent): click ra ngoài Callout/Text đang soạn → thoát
  edit. Sau guard has_image, `fi=_scene.focusItem()`; nếu là QGraphicsTextItem đang
  soạn & `_annotation_at(pos) is not fi` → `fi.clearFocus()`. Guard is-not-fi giữ
  click TRONG bong bóng đặt được con trỏ. Tái dùng focusOutEvent có sẵn (không sửa).
  FX3 (CalloutItem.paint): gộp bong bóng+đuôi thành 1 `QPainterPath` (addRoundedRect
  ∪ tail), pen RoundJoin/RoundCap, drawPath 1 lần → viền liền, hết line cắt miệng đuôi.

- ESC1 (2026-06-25): Esc toàn cục hủy countdown / dừng quay (overlay+RecordBar
  không giữ focus → phải hook global). app_controller.py: signal `request_escape`
  → `_on_escape` (Queued, an toàn cross-thread vì `keyboard` callback ở luồng
  riêng). `_register_escape`/`_unregister_escape` (keyboard add/remove_hotkey, lưu
  `_esc_handle`, try-bọc, KHÔNG suppress). Đăng ký khi countdown bắt đầu /
  `_begin_recording`; gỡ ở mọi điểm kết thúc (delay-done, stop_recording,
  finished, error) để Esc không treo sau khi xong. `_on_escape`: timer active→
  `_cancel_countdown`, elif `_recording`→`stop_recording` (Stop=lưu, KHÔNG discard).
  record_bar.py: `keyPressEvent` Esc→`_on_stop` (local khi bar có focus).
  Sim test: dựng AppController offscreen, gọi `_on_escape` trực tiếp 2 nhánh
  (recorder giả có `.stop()`); không cần keyboard lib thật.

- MOVE1 (2026-06-25): Vệt sọc khi DI CHUYỂN callout = bug logic boundingRect (KHÁC
  FX4 = artifact GPU khi resize). canvas.py CalloutItem.boundingRect THIẾU nửa-bề-
  rộng-pen → Qt invalidate vùng quá nhỏ khi move → nét viền vẽ tràn ngoài path bị
  bỏ lại. Fix: `m=self._width/2.0+1.0`; `adjusted(-m,-m,m,self._TAIL_H+m)`. QUY TẮC
  CHUNG QGraphicsItem: boundingRect phải bao trọn vùng paint KỂ CẢ pen half-width,
  nếu không di chuyển để lại "ghost". Khi geometry phụ thuộc field (vd _width), mọi
  setter đổi field đó phải gọi `prepareGeometryChange()` TRƯỚC update (set_border).
  test_callout.py geom assert đổi theo: height extra = _TAIL_H + 2m.

## Quyết định kỹ thuật
- LIB1: dùng lại bộ `tool_icon` của Editor (`app/editor/tool_icons.py`) cho 3 nút
  chụp/quay để icon đồng bộ 100% với Editor — không tự vẽ icon riêng cho Library.
  QSS đặt làm hằng module (giống EDITOR_QSS) để dễ đối chiếu palette giữa 2 màn.
- Tái dùng `import _bootstrap` (sys.path + UTF-8) như các script khác.
- Khi `QT_QPA_PLATFORM=offscreen` → `QTimer.singleShot(0, app.quit)` để tự kiểm
  dựng-không-lỗi không bị treo; chạy bình thường thì hiện cửa sổ tới khi đóng.
- Ràng buộc ED1: CHỈ thêm file script, KHÔNG đụng module `app/`. Dùng đúng public
  API `EditorWindow()` + `load_image(image, capture_id=None)`.
- Windowed (bổ sung ED1): `w.resize(1100, 720)` + căn giữa qua
  `app.primaryScreen().availableGeometry()`, dùng `w.show()` (KHÔNG
  showMaximized/showFullScreen) để cửa sổ resize được và thử được ca thu nhỏ →
  menu ">>". Ảnh mẫu vẫn 1280×800 (> viewport) để thử scroll/zoom.
- Tự kiểm: `QT_QPA_PLATFORM=offscreen python scripts/launch_editor_demo.py` →
  EXIT=0 (import + khởi tạo OK).

## Nợ kỹ thuật / lưu ý
- Eyes-test thật (UI) thuộc QC (ED2) — Coder không tự chấm UI.
- Nếu QC báo lỗi hiển thị → fix nằm ở module `app/editor/*`, không ở launcher.
