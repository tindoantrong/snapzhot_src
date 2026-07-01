---
name: AI QC Memory — Editor eyes-test
description: Ca test UI Editor, cách chụp offscreen, lỗi đã biết, checklist regression
type: project
---

# AI_QC_MEMORY — SnagTin

## BUGR2-2/2-3 — window z-order + library search escape (2026-07-01) → PASS
Không UI thấy được → verify HÀNH VI offscreen.
- BUGR2-3 (library_manager.list_captures:147-161): escape `\`→`%`→`_` + `LIKE ? ESCAPE '\'`.
  Harness DB tmp: patch `database_path/library_dir/thumbnails_dir` TẠI module library_manager
  (không đụng DB thật). search '%'→chỉ record chứa %; '_'→chỉ record chứa _; '50%'→chỉ '50%off';
  ''→tất cả; '\'→backslash literal. Coder test scripts/test_library_search.py đủ, PASS.
- BUGR2-2 (window_selector.window_rect_at_point:34-69): GetTopWindow(0)+GetWindow(GW_HWNDNEXT)
  topmost-first thay EnumWindows. Mock win32gui/win32con/_HAS_WIN32 TẠI module window_selector.
  2 cửa sổ chồng→trả topmost; exclude/invisible/iconic/no-title/zero-size bị lọc; ngoài→None;
  GetTopWindow throw→None; _HAS_WIN32=False→None; GetWindow throw giữa chừng→break→None.
  Coder test scripts/test_window_zorder.py đủ, PASS.
  [LOW robustness note] vòng `while hwnd` chỉ break khi GetWindow raise; nếu API trả hwnd LẶP
  (cyclic) sẽ kẹt vô hạn (đã tái hiện bằng mock trái contract → timeout 124). KHÔNG phải bug
  thực: Win32 GW_HWNDNEXT bảo đảm trả 0 ở cuối. Chỉ ghi chú, không blocking.
Regression PASS 6/6: test_library_search, test_window_zorder, smoke_test, test_window_delayed,
test_recent_delete, test_recent_strip.
Live-only: Z-order với cửa sổ desktop THẬT (user eyes-test phiên thật).

## BUGR2-1 — recorder.py fix (harness behavior, 2026-07-01) → PASS
Không có UI thấy được (VideoRecorder = QThread) → verify HÀNH VI, không eyes-test.
mss.grab CHẠY ĐƯỢC cả khi QT_QPA_PLATFORM=offscreen (có display thật). Harness controller:
nối REAL VideoRecorder.finished_recording/error vào FakeController (đếm add_video + toast)
mô phỏng đúng wiring app_controller.py:603-604.
- CA1 dual-emit: monkeypatch mss.mss→_BrokenMSS (grab lần>1 raise). KẾT QUẢ: chỉ `error`
  emit, `finished_recording` KHÔNG → add_video=0, 0 toast success, 1 toast lỗi.
- CA2 pause duration: quay0.5s→pause1s→quay0.5s→stop. duration emit=1.000s (=frames/fps
  active) vs wall≈2.03s → dùng active_seconds đúng, KHÔNG wall-clock.
- CA3 bình thường: add_video=1, 1 toast success, file>0B (14KB).
Regression PASS 5/5 offscreen: smoke_test, test_video, test_audio_recording,
test_video_player, test_escape. Coder đã tự thêm CA1-3 vào scripts/test_video.py (đủ, PASS).
Live-only: toast tray THẬT + video hỏng có bị thêm vào thư viện thật không (chỉ verify qua stub).

## REC2 — Xoá ảnh từ filmstrip Editor (eyes-test 2026-06-26, 6 ca) → PASS
Harness `scripts/qc_recent_delete_capture.py`. Mô phỏng controller
`delete_capture_requested → _on_delete_capture` (bỏ ảnh; xoá ảnh đang mở→nhảy recents[0]).
KỸ THUẬT grab popup theme (offscreen): QMenu/QMessageBox parent=editor window KẾ THỪA
EDITOR_QSS → dựng `QMenu(w).addAction("Xoá ảnh")` rồi `.show()`+`.grab()` (KHÔNG exec,
tránh block); `QMessageBox(...,w); setDefaultButton(No); .show()+.grab()`. Confirm Yes/No
qua `QMessageBox.question = staticmethod(lambda *a,**k: QMessageBox.Yes/No)` rồi gọi
`w._request_delete_capture(id)`. Phím Delete: `w.eventFilter(w.recent_strip, QKeyEvent(KeyPress,Key_Delete))` trả True.
- 6 ca: menu tối / confirm default No (assert `defaultButton is No`) không xoá / Yes→thumb
  biến mất / xoá ảnh đang mở→nhảy ảnh còn lại (highlight) / xoá hết→dock ẩn / Delete-key xoá qua confirm.
- MVP non-blocking: xoá HẾT → canvas giữ ảnh cuối (không về empty-state). Đúng ticket.
- Ảnh rec2_01_baseline / rec2_02_after_delete_id5 / rec2_03_after_delete_current_id2 /
  rec2_04_after_delete_all_dock_hidden / rec2_05_context_menu / rec2_06_confirm_dialog.

## REC1 — Filmstrip "Ảnh gần đây" trong Editor (eyes-test 2026-06-26) → PASS
Harness `scripts/qc_recent_strip_capture.py`. KỸ THUẬT QUAN TRỌNG: editor decoupled
(KHÔNG import LibraryManager) → click thumbnail CHỈ emit `open_capture_requested(id)`;
canvas KHÔNG tự đổi ảnh nếu không có controller. Để eyes-test "canvas đổi khi click",
harness phải MÔ PHỎNG controller: `editor.open_capture_requested.connect(lambda cid:
(editor.load_image(FULLS[cid], capture_id=cid), editor.set_recent_captures(ITEMS)))`.
Tạo ảnh full KHÁC NHAU theo id (màu+số to) để mắt thấy canvas thật sự load ảnh khác.
Click qua `w._on_recent_item_clicked(w.recent_strip.item(idx))` (gọi handler thật).
- Highlight: item `current_capture_id` selected, viền `#1E90FF` (QSS `#recentStrip::item:selected`),
  nền chọn `#1E3A5F`. Quét pixel dock tìm ~149 px màu accent → xác nhận viền.
- Click ảnh ĐANG mở → no-op (không emit signal mới). Rỗng → `recent_dock` ẩn hẳn.
- Cosmetic non-blocking: thumbnail có dải tối trống dưới icon (không nhãn chữ — đúng design).
- Live-only: active-show/un-minimize editor sau CHỤP thật = user phiên thật.
Ảnh: rec_01_open_id2 / rec_02_closeup_id2 / rec_03_after_click_id4 / rec_04_closeup_id4 /
rec_05_empty_dock_hidden trong `.ai-workspace/screens/`.


## Cách eyes-test Editor (offscreen, an toàn — KHÔNG điều khiển desktop thật)

App là **PySide6/Qt desktop** (KHÔNG phải Electron) ⇒ Playwright KHÔNG drive được.
Cách QC dùng: render cửa sổ Qt **offscreen** rồi `window.grab()` ra PNG → `Read` để nhìn.

Gotcha quan trọng:
- **Offscreen QPA không nạp font hệ thống** → mọi chữ thành ô vuông (tofu □), KỂ CẢ
  chữ ASCII vẽ bằng QPainter. ĐÂY LÀ ARTIFACT CHỤP, KHÔNG phải lỗi app. Khắc phục
  trong harness QC: `QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\segoeui.ttf")`
  + `app.setFont(...)` trước khi dựng cửa sổ.
- **Synthetic QMouseEvent gọi thẳng `canvas.mousePressEvent`**: VẼ được (press/move/
  release vào pipeline vẽ) nhưng **click-select của QGraphicsView KHÔNG kích hoạt**
  (cần event đi qua viewport thật). Để chụp trạng thái chọn/handle: chọn qua scene API
  `item.setSelected(True)` (kích `selectionChanged` → hiện 8 handle), resize qua
  `canvas._begin_resize(idx)/_resize_to(scene_pt)/_commit_resize()`.
- Harness QC tái lập: `scripts/qc_editor_capture.py` (offscreen + nạp font Windows
  segoeui/arial qua addApplicationFont + app.setFont, mô phỏng QMouseEvent vào
  viewport, grab 15 PNG → `.ai-workspace/screens/`). Chạy:
  `QT_QPA_PLATFORM=offscreen python scripts/qc_editor_capture.py`. Ảnh mẫu dùng
  `make_sample_image` import từ `launch_editor_demo`.
- CHƯA nạp font ⇒ tofu; nạp font xong chữ Việt + tiêu đề ảnh render OK (đã xác nhận).

## UPD2 — Dialog cập nhật (2026-06-25) — VERDICT PASS (1 lỗi [low] non-blocking)

Harness `scripts/qc_update_dialog_capture.py` (offscreen + nạp font Windows;
monkeypatch `updater.check_for_updates` qua holder — KHÔNG cần mạng; grab 6 PNG
`.ai-workspace/screens/upd_01..06`). Chạy:
`python scripts/qc_update_dialog_capture.py` → `=== UPDATE DIALOG QC OK ===`.

5 trạng thái dialog (`_UpdateDialog`) — eyes-test ảnh, chữ Việt KHÔNG tofu, theme tối:
- **upd_01_idle**: "Phiên bản hiện tại: 0.1.0" + nút "Kiểm tra cập nhật" (xanh): PASS.
- **upd_02_checking**: "Đang kiểm tra…" + nút disable: PASS (xem lỗi [low] bên dưới).
- **upd_03_available**: "Đã có phiên bản mới: 1.5.0 (bạn đang dùng 0.1.0)" + ô notes
  (bullet "• Sửa lỗi callout / • Thêm cập nhật tự động") + nút "Tải về" xanh enable: PASS.
- **upd_04_available_no_url**: url rỗng → "Tải về" disable + tooltip "Manifest không có
  liên kết tải về.": PASS (logic). [low] nút disable vẫn nền xanh nhạt (xem dưới).
- **upd_05_latest**: "Bạn đang dùng phiên bản mới nhất." + nút "Kiểm tra lại": PASS.
- **upd_06_error**: "Không kết nối được tới máy chủ cập nhật. Vui lòng kiểm tra mạng."
  + nút "Thử lại": PASS.

Theme (sample pixel grab): nền QDialog = `#2b2d31` (3 điểm), nút primary fill = `#1e90ff`
(GOTCHA sample: center nút dính chữ trắng → blend `#339aff`; phải sample LỆCH khỏi chữ,
x≈6px trong padding 16px → đọc đúng `#1e90ff`). Nhất quán Editor/Library: PASS.

Nút "Tải về" → `QDesktopServices.openUrl` đúng URL (monkeypatch bắt): PASS.

Luồng bất đồng bộ (AppController + QThread): bấm nút → mode "checking" NGAY (GUI không
đơ) → kết quả về qua signal. Xác nhận `check_for_updates` chạy LUỒNG NỀN (thread
`Dummy-1`, KHÁC `MainThread`) — không gọi trực tiếp trên GUI: PASS (3 ca available/
latest/error). Đóng dialog → clear ref (`_update_dialog=None`): PASS.

Tray menu: nhãn "Về snapzhot (phiên bản 0.1.0)" disabled + mục "Kiểm tra cập nhật…"
enabled: PASS.

**Lỗi [low] — ĐÃ VÁ ở UPD3**: nút primary khi disabled trước đây vẫn nền xanh (QSS
`#primary` ID-selector thắng `:disabled`). UPD3 thêm `QPushButton#primary:disabled
{background:#2F3136;color:#7A7D82}` (ID+pseudo, specificity cao hơn `#primary`). QC
re-grab: upd_04 sample pixel nút "Tải về" disabled = `#2f3136` (xám), upd_02 nút "Kiểm
tra cập nhật" disabled cũng xám — phân biệt rõ với nút bấm được. assert thêm vào harness
`dis_color == "#2f3136"`. → CLOSED.

NOTE nguồn cập nhật: `updater.UPDATE_MANIFEST_URL` đã được chốt = GitHub Releases asset
`github.com/doanleox/snapzhot/releases/latest/download/latest.json` (file JSON đính kèm
release, schema `{version,url,notes}`). UI đọc config `update_manifest_url` fallback hằng
này → vận hành = user upload `latest.json` vào release. Live-only (cần phiên thật + mạng):
tải manifest GitHub thật + nút "Tải về" mở trình duyệt tới trang release.

## Ca đã test (ED2 — 2026-06-25) + kết quả

VERDICT: PASS. Ảnh: 01..18 trong captures/session-1782368508710.
- Toolbar icon line-art (không emoji), tool active highlight xanh đúng: PASS (01,03-08).
- Panel theo TOOL: Arrow=màu+độ dày; Text=màu+cỡ chữ; Step=+Số bước; Stamp=Biểu tượng
  (6 glyph) + màu; Callout=màu+độ dày+cỡ chữ: PASS.
- Panel theo ITEM đang chọn (rect có viền): màu+độ dày+Độ trong suốt+Đổ bóng+Tô nền: PASS (15).
- Vẽ arrow(đầu mũi tên thật)/rect/ellipse/step badge ①②: PASS (08).
- 8 resize handle + dashed selection: PASS (15). Resize kéo handle BR: PASS (18).
- Express Style "Hộp vàng" áp combo (viền+độ dày+fill #ffe680): PASS (16).
- Đổi màu viền swatch (#1e90ff) giữ nguyên fill: PASS (17).
- Callout kéo to + vào soạn chữ (tail trỏ xuống): PASS (11,13).
- Empty state CTA (3 nút): PASS (02). Toast "Đã lưu" pill đáy canvas: PASS (12).
- Zoom 100% → scrollbar; status "1280×800 px | 100%": PASS (13).
- Cửa sổ nhỏ → toolbar overflow: PASS (14).

## Re-test ED2 qua launcher windowed (2026-06-25) — VERDICT PASS
Harness `qc_editor_capture.py`, 15 ảnh `.ai-workspace/screens/01..15`:
- Toolbar 13 tool line-art không emoji + capture/undo/redo/zoom; tool active xanh: PASS (01).
- Vẽ arrow(đầu mũi tên thật)/rect/ellipse/pen: PASS (02). Arrow preview ĐANG kéo cũng là
  mũi tên thật có đầu: PASS (10).
- Text/step ①②③ (số tăng)/stamp star+heart+check/highlight mờ/callout bong bóng+đuôi+soạn
  chữ: PASS (03). Spotlight phủ tối chừa hole: PASS (04). Blur: yếu (vẽ trên vùng phẳng) → đề
  xuất QC test lại blur trên vùng nhiều chi tiết ở launcher thật.
- Chọn rect → 8 handle xanh + panel đúng nhóm (màu+độ dày+opacity+shadow+tô nền): PASS (06).
  Arrow panel = màu+độ dày (không font/fill): PASS (09).
- Express "Hộp vàng" fill: PASS (07). Shadow + opacity 50%: PASS (08).
- Zoom in → scrollbar; fit: PASS (11,12). Empty-state 3 CTA: PASS (14). Toast "Đã lưu vào
  thư viện" pill đáy canvas: PASS (15). Cửa sổ hẹp 520px overflow: PASS (13).

## Ca đã test (LIB1 — màn Thư viện theme tối — 2026-06-25) — VERDICT PASS
Harness `scripts/qc_library_capture.py` (offscreen + nạp font + LibraryManager GIẢ
duck-typed, KHÔNG đụng DB thật, thumbnail vẽ vào temp). 4 ảnh `.ai-workspace/screens/lib_01..04`:
- lib_01_populated: nền tối #2B2D31 toàn bộ, không vùng trắng; 4 card ảnh gradient +
  1 card video (play badge tam giác trắng trên nền đen); count "4 ảnh · 1 video"; nút
  dưới (Mở trong Editor/Sửa tag/Xoá) nền tối chữ sáng: PASS.
- lib_02_item_selected: item chọn nền xanh accent #1E90FF: PASS.
- lib_03_search_focus_filter: gõ "ui" lọc realtime còn 2 item; search box viền focus
  xanh #1E90FF (xác minh focusWidget=QLineEdit, fill #3e4248): PASS.
- lib_04_empty_state: empty_hint chữ sáng canh giữa, đủ tương phản: PASS.
- Toolbar 3 nút icon line-art (capture_region/capture_full/video) + chữ bên phải,
  KHÔNG emoji: PASS.
Gotcha harness Library:
- LibraryManager() mở DB thật của user → DÙNG FakeLibrary duck-typed (list_captures/get)
  + FakeCapture (thumbnail_path/is_video/tag_list/duration) để KHÔNG ghi vào DB/thumbnail thật.
- Nút toolbar đầu "Chụp vùng" trông sáng hơn = `:hover` (#3e4248) do con trỏ offscreen
  nằm (0,0) đè lên nút → ARTIFACT, không phải checked (đã assert isChecked=False).
- 🏷/🎬 trong _make_item & 📷🖥🎬 trong empty_hint → tofu □ khi chụp (offscreen thiếu
  font emoji màu); trên Windows thật sẽ render. KHÔNG phải lỗi app (empty_hint emoji là
  by-design chờ LIB2).

## Ca đã test (LIB2 — empty-state + fix toolbar — 2026-06-25) — VERDICT PASS
Harness `qc_library_capture.py` mở rộng: thêm assert wiring + sample màu pixel.
- Nền toolbar #33363B NỔI TÁCH THÂN: pixel mọi vùng trống = #33363b (trước LIB1 là
  #2b2d31). Fix Coder: `tb.setObjectName("captureBar")` + QSS `#captureBar{background:#33363B}`
  — ID-selector thắng specificity của `QMainWindow>QWidget`. → lỗi [low] LIB1 CLOSED.
- Empty-state card `#emptyState` nền #3a3d42 bo góc (geom ~882×503): title đậm sáng,
  sub xám có phím tắt KHÔNG emoji tofu, 3 CTA icon line-art (2 primary #1E90FF + 1
  secondary viền). Ảnh lib_04_empty_state.
- Wiring assert (offscreen, click 3 nút CTA): fired = [region, full, video]; icon non-null
  cả 3; objectName ['','','secondary']. Cách spy: connect signal vào lambda append rồi
  `btn.click()`.
- CÒN tofu 🏷/🎬 trong `_make_item` (tag/video label): artifact chụp offscreen + thuộc
  LIB3, KHÔNG phải lỗi LIB2.

## Ca đã test (LIB3 — polish, phase cuối — 2026-06-25) — VERDICT PASS → TASK ĐỒNG BỘ THEME HOÀN TẤT
Harness `qc_library_capture.py` thêm: hover item (gửi QMouseEvent MouseMove vào
list.viewport() tại visualItemRect.center() → kích `::item:hover`) + assert search/emoji.
- Lưới KHÔNG còn tofu: tag `\n# ...` (bỏ 🏷), video `{duration}` (bỏ 🎬) — nhận biết qua
  play badge tam giác. Assert ITEM_LABELS_HAVE_EMOJI=False. Ảnh lib_01_populated.
- Search box: kính lúp line-art bên trái (`_draw_search` ADDITIVE trong tool_icons.py +
  `addAction(tool_icon("search"), QLineEdit.LeadingPosition)`). Assert 1 leading action
  icon non-null.
- Hover item: viền card #55585E + nền #3E4248 (lib_05_item_hover). Không xáo layout vì
  `::item` đã có `border:1px solid transparent` mặc định.
- Tổng thể nhất quán Editor: #2B2D31 / accent #1E90FF / toolbar #33363B / icon cùng bộ.
- Gotcha: chụp hover offscreen = gửi MouseMove vào viewport tại tâm visualItemRect (KHÔNG
  cần nút nhấn); WA_Hover tự bật do stylesheet có :hover.

## Ca đã test (FX1/FX2/FX3 — toolbar Editor + Callout — 2026-06-25) — VERDICT PASS
Harness `scripts/qc_editor_fx_capture.py` (offscreen + font; sample màu 4 toolbar +
vẽ callout drag + assert exit-edit/reselect bằng QMouseEvent gửi vào canvas.viewport()).
- FX1 nền 4 toolbar Editor = #33363b: sample pixel vùng trống captureBar/toolBar/zoomBar/
  bottomBar đều #33363b. Lưu ý: captureBar còn `tb.setStyleSheet("QToolBar{padding;spacing}")`
  inline NHƯNG không set background → app-QSS `#captureBar{background:#33363B}` vẫn áp được
  (inline chỉ thắng property nó khai báo). Ảnh fx_01_editor_toolbars.
- FX2 (exit-edit) ASSERT ĐƯỢC qua synthetic event vì canvas.mousePressEvent là override
  trên view + gọi super() cho nhánh select → selection/handle KÍCH HOẠT thật (khác ghi chú
  cũ "click-select không activate" — đúng khi gửi thẳng canvas chứ KHÔNG qua super()):
  tạo callout→focusItem=CalloutItem(edit); click TÂM callout→giữ focus; click (120,120)
  trống→focusItem None + co.textInteractionFlags()==NoTextInteraction; tool Chọn + click
  callout→co.isSelected()=True, len([h visible])==8, _resize_target is co. Ảnh fx_04.
- FX3 hình bong bóng: 1 QPainterPath (addRoundedRect(10) united tail), pen RoundJoin/
  RoundCap, drawPath 1 lần → viền liền mạch, đuôi thông thân, KHÔNG line cắt miệng, góc mượt.
  Ảnh fx_02 + fx_03(zoom). Lúc enter_edit có ô xanh = vùng chữ bôi chọn (không phải lỗi hình);
  thoát edit fill về trắng (fx_04).

## Ca đã test (ESC2 — Esc hủy/dừng chụp+quay — 2026-06-25) — VERDICT PASS
Harness `scripts/test_escape.py` (offscreen + MOCK module `keyboard` để
`_register/_unregister_escape` chạy không cần lib/quyền admin). Phần bắt Esc TOÀN
CỤC THẬT (user ở app khác) chỉ verify được phiên tương tác thật — KHÔNG giả lập
low-level hook. Gotcha mock: `sys.modules["keyboard"]=FakeKeyboard` TRƯỚC khi import
AppController; FakeKeyboard.add_hotkey trả handle giả + ghi (key,cb), remove_hotkey
ghi handle gỡ. Chặn side-effect: stub `_do_fullscreen_capture`/`library.add_video`/
`library_window.refresh`/`tray.showMessage`.
- (1) Countdown cancel: `capture_fullscreen_delayed(3)`→ timer active + overlay
  visible + `_esc_handle` set + hotkey 'esc'. `_on_escape()`→ timer dừng, overlay
  ẩn, `_esc_handle is None`, remove_hotkey gọi, KHÔNG chụp (captured==[]).
- (2) Recording stop: `_recording=True`+recorder giả(.stop)+`_register_escape()`→
  `_on_escape()`→ recorder.stop=True, record_bar ẩn, `_esc_handle is None`.
- (2b) Loại trừ: countdown active + `_recording=True` → Esc CHỈ hủy countdown,
  recorder.stop KHÔNG gọi (if/elif đúng thứ tự ưu tiên).
- (3) RecordBar Esc local: `QKeyEvent(Key_Escape)`→ `keyPressEvent`→ stopped phát +
  finish (bar ẩn + `_timer` dừng).
- (4) Lifecycle gỡ hotkey: `_on_recording_finished` + `_on_recording_error` đều set
  `_esc_handle=None` + tắt `_recording`; `_unregister_escape()` khi rỗng = no-op an toàn.
Chạy: `QT_QPA_PLATFORM=offscreen python scripts/test_escape.py` → 7 OK + dòng kết.
User phải tự eyes-test phiên thật: Esc khi đếm ngược (hủy, không chụp); Esc khi đang
quay ở app khác (dừng + LƯU video tới thời điểm đó, KHÔNG discard).

## Ca đã test (MOVE2 — Callout HẾT vệt sọc khi DI CHUYỂN — 2026-06-25) — VERDICT PASS
Harness `scripts/qc_callout_move_capture.py` (offscreen + font). Vì `grab()` LUÔN
full-repaint → KHÔNG tái hiện được "ghost" tăng-trưởng bằng ảnh. Thay vào đó verify
ROOT CAUSE deterministic: render `CalloutItem.paint()` ra QImage cỡ boundingRect+PAD,
đo bbox pixel THỰC vẽ (alpha>16), khẳng định NẰM TRỌN boundingRect MỚI và TRÀN ra
ngoài boundingRect CŨ (chứng minh đúng nguyên nhân vệt sọc).
- (1) Callout viền dày width=20: paint_bbox=(-10,-10, 561×100) NẰM TRỌN new_br=
  (-11,-11, 564×103). → move chỉ invalidate boundingRect, pixel vẽ đã trong đó → KHÔNG ghost.
- (2) Tràn ngoài old_br=(0,0, 542×81): left=10 top=10 right=9 bottom=9 px = ĐÚNG nửa-
  bề-rộng-pen (20/2) → xác nhận root cause: boundingRect cũ thiếu lề pen nên để vệt.
- (3) set_border(width 4→24) nới boundingRect 216×87 → 236×107 (prepareGeometryChange
  có hiệu lực); paint sau mutate vẫn trọn boundingRect. Ảnh move_02_callout_mutated_w24.png.
- (4) Regression: đuôi vẫn vẽ dưới thân (paint_bottom > body_bottom), viền pen phủ
  quanh thân (paint trùm tới/ra mép) — không bị cắt. Ảnh move_01_callout_w20.png render
  bong bóng đỏ sạch, góc bo, đuôi trỏ xuống, KHÔNG artifact.
Chạy: `QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 python scripts/qc_callout_move_capture.py`
→ `=== CALLOUT MOVE (no-ghost) OK ===` (6/6). User nên eyes-test phiên thật: kéo callout
viền dày qua nền có chi tiết → KHÔNG còn vệt dọc đường đi.

## Ca đã test (DEL2 — Thư viện xoá đơn/nhiều/tất cả + phím Delete — 2026-06-25) — VERDICT PASS
Harness `scripts/qc_library_delete_capture.py` (offscreen + font; FakeLibrary
STATEFUL duck-typed: delete xoá khỏi list + ghi log, set_tags log, search filter).
Gotcha quan trọng để verify hộp thoại xác nhận offscreen: `QMessageBox.question`
là MODAL → KHÔNG chụp được; thay bằng **monkeypatch** `QMessageBox.question =
staticmethod(fake)` ghi (title,text) vào list + trả `DLG["answer"]` (Yes/No điều
khiển). Tương tự `QInputDialog.getText` cho _edit_tags. 27/27 check PASS:
- (1) Chọn nhiều {2,4}→`_delete_selected`: message "Xoá **2 mục đã chọn** khỏi thư
  viện?" (số ít = "Xoá mục này khỏi thư viện?"); xoá đúng→còn {1,3,5}, count "3 ảnh".
  Ảnh del_01_multi_selected (2 card accent #1E90FF) / del_02_after_multi_delete.
- (2) Phím Delete: `keyPressEvent` Key_Delete khi list focus + có selection→`_delete_
  selected` (VẪN qua hộp thoại). AN TOÀN: Delete khi focus `search_box`→QLineEdit
  nuốt trước (sendEvent vào search_box), CHỈ sửa text 'abc'→'bc', `library.delete`
  KHÔNG gọi. Bubble lên QMainWindow chỉ khi child ignore.
- (3) Xoá tất cả: không filter→"Xoá toàn bộ **5** mục đang hiển thị?"→list rỗng +
  empty-state hiện (del_03). CÓ filter 'ui'→"toàn bộ **3** mục", chỉ xoá phần HIỂN
  THỊ {1,3,5}, mục bị filter ẩn {2,4} CÒN NGUYÊN sau bỏ filter (del_04).
- (4) An toàn: `DLG["answer"]=No`→0 xoá, list nguyên 5; no-op + KHÔNG mở hộp thoại
  khi không chọn / list rỗng; Delete key khi không chọn = no-op (guard selectedItems).
- (5) Regression: `_selected_id` vẫn trả 1 mục (mục đầu) khi chọn nhiều→_open_selected
  emit open_in_editor(cid), _edit_tags set_tags mục đầu — không vỡ open/edit.
Chạy: `QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 python scripts/qc_library_delete_capture.py`.
Helper `select_ids(w, ids)`: loop item set Selected (ExtendedSelection cho phép chọn nhiều qua API).

## Lỗi đã biết (Editor — low — chưa blocking, để Coder cân nhắc)
- [low] Nút Hoàn tác/Làm lại đổi nhãn động theo lệnh ("Hoàn tác Thêm callout"/"Đổi
  kích thước"…) → toolbar giãn rộng, đẩy layout. Cân nhắc giữ nhãn cố định "Hoàn tác",
  đưa tên lệnh vào tooltip. (Hành vi mặc định của QUndoStack.createUndoAction.)
- [FIXED 2026-06-25 ED3] Cửa sổ hẹp mất tool icon + zoom overflow: zoom toolbar trước
  đây CHUNG HÀNG với tool toolbar → tranh chỗ, nút ">>" của tool toolbar không tới được
  nên các tool (Bút vẽ/Chữ/Callout/Đánh dấu/Làm mờ/Số bước) biến mất âm thầm. Fix: zoom
  toolbar xuống HÀNG RIÊNG (addToolBarBreak) + undo/redo icon-only (nhãn động không giãn
  bar). Verify: scripts/qc_narrow_check.py @740px → tool y=47, zoom y=117, ">>" visible,
  6 tool ẩn truy cập qua ">>". Ảnh 16_narrow_overflow_fixed.png.

## CHƯA phủ được (cần phiên tương tác THẬT — ngoài phạm vi offscreen an toàn)
- Hover state nút; cursor đổi khi hover handle; Shift giữ tỉ lệ/Alt từ tâm (hình ảnh).
- Mũi tên nudge 1/10px; double-click callout vào soạn lại; phím 1-ký-tự không bị nuốt
  khi gõ text; Backspace không xoá object. (Logic CÓ trong code + script test riêng:
  test_text_delete_guard.py, test_move_resize.py, test_quick_styles.py…)
- Tooltip popup; nội dung menu overflow ">>".

## Regression checklist nhanh lần sau
1. Chạy harness offscreen + nạp font → chụp 01 (default), 02 (empty), panel từng tool.
2. Vẽ 4 hình + step badge → 08. Chọn rect qua scene API → 8 handle (15).
3. Express fill (16) + đổi màu viền (17) + resize handle (18).
4. Toast (12), zoom 100% scrollbar (13), cửa sổ nhỏ overflow (14).
5. So màu/độ dày/fill bằng cả ẢNH lẫn assert (rect.brush()/pen()).
