"""Test di chuyển + đổi kích thước (resize) item trong Editor (offscreen).

Trọng tâm: toán transform của resize dễ sai nên kiểm bằng hàm thuần
(rect_for_handle, transform_for_resize) + ResizeItemCommand undo/redo,
và xác nhận move cũ vẫn hoạt động, không hồi quy.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGraphicsRectItem, QGraphicsTextItem
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPen, QTransform

app = QApplication([])

from app.editor.canvas import (
    Canvas, Tool,
    HANDLE_TL, HANDLE_T, HANDLE_TR, HANDLE_R, HANDLE_BR, HANDLE_B, HANDLE_BL, HANDLE_L,
    HANDLE_CURSORS,
    rect_for_handle, transform_for_resize,
)
from app.editor.commands import MoveItemCommand, ResizeItemCommand

EPS = 1e-6


def approx_rect(a: QRectF, b: QRectF, tol: float = 1e-4) -> bool:
    return (abs(a.x() - b.x()) < tol and abs(a.y() - b.y()) < tol
            and abs(a.width() - b.width()) < tol
            and abs(a.height() - b.height()) < tol)


# ----------------------------------------------------------------------
# 1. rect_for_handle: cạnh đối diện đứng yên, góc/cạnh kéo bám con trỏ
# ----------------------------------------------------------------------
base = QRectF(100, 100, 200, 100)   # left100 top100 right300 bottom200

# Kéo góc dưới-phải tới (360, 260) → top-left giữ nguyên, mở rộng
r = rect_for_handle(HANDLE_BR, base, QPointF(360, 260))
assert approx_rect(r, QRectF(100, 100, 260, 160)), f"BR sai: {r}"

# Kéo góc trên-trái tới (60, 60) → bottom-right (300,200) giữ nguyên
r = rect_for_handle(HANDLE_TL, base, QPointF(60, 60))
assert approx_rect(r, QRectF(60, 60, 240, 140)), f"TL sai: {r}"

# Handle cạnh phải: chỉ đổi chiều ngang, chiều dọc giữ nguyên
r = rect_for_handle(HANDLE_R, base, QPointF(400, 9999))
assert approx_rect(r, QRectF(100, 100, 300, 100)), f"R sai: {r}"

# Handle cạnh dưới: chỉ đổi chiều dọc
r = rect_for_handle(HANDLE_B, base, QPointF(9999, 250))
assert approx_rect(r, QRectF(100, 100, 200, 150)), f"B sai: {r}"

# Clamp kích thước tối thiểu (kéo qua anchor không làm lật/biến mất)
r = rect_for_handle(HANDLE_BR, base, QPointF(100, 100), min_size=8.0)
assert r.width() >= 8.0 and r.height() >= 8.0, f"clamp min sai: {r}"
print("OK: rect_for_handle (góc + cạnh + clamp) đúng")


# ----------------------------------------------------------------------
# 2. transform_for_resize: khung bao scene đi đúng old_rect -> new_rect
# ----------------------------------------------------------------------
def check_transform(old_local: QTransform, pos: QPointF,
                    local_rect: QRectF, new_rect: QRectF) -> None:
    old_full = old_local * QTransform.fromTranslate(pos.x(), pos.y())
    old_scene = old_full.mapRect(local_rect)
    new_local = transform_for_resize(old_local, pos, old_scene, new_rect)
    new_full = new_local * QTransform.fromTranslate(pos.x(), pos.y())
    got = new_full.mapRect(local_rect)
    assert approx_rect(got, new_rect), f"transform sai: muốn {new_rect} được {got}"


# item ở gốc, transform đơn vị
check_transform(QTransform(), QPointF(0, 0),
                QRectF(0, 0, 50, 40), QRectF(0, 0, 100, 80))
# item có pos khác 0
check_transform(QTransform(), QPointF(30, 20),
                QRectF(0, 0, 50, 40), QRectF(10, 10, 200, 120))
# item đã có sẵn scale rồi resize tiếp (kiểm cộng dồn)
check_transform(QTransform.fromScale(2.0, 3.0), QPointF(15, 5),
                QRectF(0, 0, 10, 10), QRectF(0, 0, 77, 33))
print("OK: transform_for_resize đưa khung bao scene đúng đích (kể cả có pos/scale)")


# ----------------------------------------------------------------------
# 3. ResizeItemCommand trên item thật: kích thước + undo/redo
# ----------------------------------------------------------------------
img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#dddddd"))

c = Canvas()
c.load_image(img)
# Cấp kích thước viewport thật để view-transform khả nghịch (cần cho mapFromScene
# / items() ở phần direct-select; offscreen mặc định không tự layout).
c.resize(500, 400)
app.processEvents()

rect_item = QGraphicsRectItem(QRectF(50, 50, 100, 60))
rect_item.setPen(QPen(QColor("#FF0000"), 6))   # nét dày như app vẽ thật
c._finalize(rect_item)   # qua AddItemCommand, pos=(0,0)

O = rect_item.sceneBoundingRect()
old_t = QTransform(rect_item.transform())

# Phóng to gấp đôi quanh góc trên-trái (anchor = topLeft)
target = QRectF(O.left(), O.top(), O.width() * 2, O.height() * 2)
new_t = transform_for_resize(old_t, rect_item.pos(), O, target)
c.undo_stack.push(ResizeItemCommand(rect_item, old_t, new_t))

after = rect_item.sceneBoundingRect()
assert approx_rect(after, target, tol=1.0), \
    f"resize phải ra ~{target} got {after}"
print(f"OK: resize item {O.width():.0f}x{O.height():.0f} -> "
      f"{after.width():.0f}x{after.height():.0f}")

c.undo_stack.undo()
assert approx_rect(rect_item.sceneBoundingRect(), O, tol=1.0), \
    "undo resize phải khôi phục khung bao ban đầu"
assert rect_item.transform() == old_t, "undo phải khôi phục transform cũ"
print("OK: undo resize khôi phục kích thước ban đầu")

c.undo_stack.redo()
assert approx_rect(rect_item.sceneBoundingRect(), target, tol=1.0), \
    "redo resize phải áp lại kích thước mới"
print("OK: redo resize áp lại kích thước mới")


# ----------------------------------------------------------------------
# 4. Move cũ vẫn hoạt động (không hồi quy)
# ----------------------------------------------------------------------
c.undo_stack.undo()  # về nguyên trạng
pos0 = QPointF(rect_item.pos())
new_pos = pos0 + QPointF(40, 25)
c.undo_stack.push(MoveItemCommand(rect_item, pos0, new_pos))
assert rect_item.pos() == new_pos, "move phải dời item tới vị trí mới"
c.undo_stack.undo()
assert rect_item.pos() == pos0, "undo move phải về vị trí cũ"
c.undo_stack.redo()
assert rect_item.pos() == new_pos, "redo move phải dời lại"
print("OK: MoveItemCommand (move/undo/redo) vẫn đúng")


# ----------------------------------------------------------------------
# 5. Handle hiển thị đúng theo lựa chọn (mọi công cụ — direct-select)
# ----------------------------------------------------------------------
c.state.tool = Tool.SELECT
rect_item.setSelected(True)
c._update_handles()
assert c._resize_target is rect_item, "phải có target khi chọn 1 item ở công cụ Chọn"
assert len(c._handles) == 8 and all(h.isVisible() for h in c._handles), \
    "phải hiện đủ 8 handle"

# Direct-select: đổi sang công cụ vẽ mà vẫn còn 1 item được chọn → handle VẪN hiện
c.state.tool = Tool.ARROW
c.refresh_handles()
assert c._resize_target is rect_item and all(h.isVisible() for h in c._handles), \
    "ở công cụ vẽ + 1 item được chọn vẫn phải hiện handle (direct-select)"

# Bỏ chọn → ẩn handle (ở bất kỳ công cụ nào)
rect_item.setSelected(False)
c._update_handles()
assert c._resize_target is None and all(not h.isVisible() for h in c._handles), \
    "bỏ chọn phải ẩn handle + xoá target"
c.state.tool = Tool.SELECT
print("OK: handle hiện khi đúng 1 item được chọn (kể cả công cụ vẽ), ẩn khi bỏ chọn")


# ----------------------------------------------------------------------
# 5b. Direct-select: _annotation_at hit/miss + chọn-được ở công cụ vẽ
# ----------------------------------------------------------------------
# Các test trước để item lệch pos → đưa về (0,0) cho khớp toạ độ scene hardcode.
rect_item.setPos(0, 0)
app.processEvents()
# rect_item rect (50,50)-(150,110), nét dày 6 → trúng cạnh trên (100,50).
on_edge_view = c.mapFromScene(QPointF(100, 50))
empty_view = c.mapFromScene(QPointF(380, 280))  # góc xa, ngoài rect_item

hit = c._annotation_at(on_edge_view)
assert hit is rect_item, f"_annotation_at phải trúng nét rect_item, got {hit}"
miss = c._annotation_at(empty_view)
assert miss is None, f"_annotation_at vùng trống phải None, got {miss}"

# Nền và handle không bao giờ bị _annotation_at trả về
rect_item.setSelected(True)
c.state.tool = Tool.SELECT
c._update_handles()                # handle đang hiện, zValue rất cao
on_handle = c.mapFromScene(c._handles[HANDLE_TL].pos())
ann = c._annotation_at(on_handle)
assert not isinstance(ann, type(c._handles[0])), "không được trả ResizeHandle"
rect_item.setSelected(False)
c._update_handles()
print("OK: _annotation_at trúng object, bỏ qua nền + handle, miss ở vùng trống")


# ----------------------------------------------------------------------
# 5c. Resize được khi ĐANG ở công cụ vẽ (không cần về công cụ Chọn)
# ----------------------------------------------------------------------
c.state.tool = Tool.RECT          # đang ở công cụ vẽ
rect_item.setSelected(True)
c._update_handles()
assert c._resize_target is rect_item, "phải có target ngay ở công cụ vẽ"
Ob = rect_item.sceneBoundingRect()
c._begin_resize(HANDLE_BR)
c._resize_to(QPointF(Ob.left() + Ob.width() * 1.4, Ob.top() + Ob.height() * 1.4))
c._commit_resize()
after_dir = rect_item.sceneBoundingRect()
assert after_dir.width() > Ob.width() and after_dir.height() > Ob.height(), \
    "resize phải hoạt động ngay khi đang ở công cụ vẽ"
c.undo_stack.undo()               # trả nguyên trạng cho các test sau
rect_item.setSelected(False)
c._update_handles()
c.state.tool = Tool.SELECT
print("OK: resize hoạt động ở công cụ vẽ (không cần đổi về công cụ Chọn)")


# ----------------------------------------------------------------------
# 6. M2-A: giữ tỉ lệ (Shift) + từ tâm (Alt)
# ----------------------------------------------------------------------
b = QRectF(100, 100, 200, 100)   # tỉ lệ 2:1, tâm (200,150)

# Góc BR + giữ tỉ lệ: hộp lớn hơn, vẫn 2:1, neo top-left
r = rect_for_handle(HANDLE_BR, b, QPointF(360, 260), keep_aspect=True)
assert approx_rect(r, QRectF(100, 100, 320, 160)), f"BR keep_aspect sai: {r}"
assert abs(r.width() / r.height() - 2.0) < 1e-6, "phải giữ tỉ lệ 2:1"

# Cạnh phải + giữ tỉ lệ: suy ra chiều cao, đối xứng quanh tâm y
r = rect_for_handle(HANDLE_R, b, QPointF(400, 9999), keep_aspect=True)
assert approx_rect(r, QRectF(100, 75, 300, 150)), f"R keep_aspect sai: {r}"

# Góc BR + từ tâm: tâm giữ nguyên
r = rect_for_handle(HANDLE_BR, b, QPointF(360, 260), from_center=True)
assert approx_rect(r, QRectF(40, 40, 320, 220)), f"BR from_center sai: {r}"
assert abs(r.center().x() - 200) < 1e-6 and abs(r.center().y() - 150) < 1e-6, \
    "from_center phải giữ tâm cố định"
print("OK: rect_for_handle giữ tỉ lệ (Shift) + từ tâm (Alt) đúng")


# ----------------------------------------------------------------------
# 7. M2-B: di chuyển bằng phím mũi tên (1px / Shift=10px) có undo
# ----------------------------------------------------------------------
def press(canvas, key, mod=Qt.NoModifier):
    canvas.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, mod))


c.state.tool = Tool.SELECT
for it in c._scene.selectedItems():
    it.setSelected(False)
rect_item.setSelected(True)
p0 = QPointF(rect_item.pos())

press(c, Qt.Key_Right)
assert rect_item.pos() == p0 + QPointF(1, 0), f"→ 1px sai: {rect_item.pos()}"
press(c, Qt.Key_Down, Qt.ShiftModifier)
assert rect_item.pos() == p0 + QPointF(1, 10), f"↓ Shift 10px sai: {rect_item.pos()}"
c.undo_stack.undo()   # hoàn tác bước Shift
assert rect_item.pos() == p0 + QPointF(1, 0), "undo phải về sau bước 1px"
c.undo_stack.undo()   # hoàn tác bước 1px
assert rect_item.pos() == p0, "undo tiếp phải về vị trí gốc"
print("OK: phím mũi tên di chuyển 1px/10px + undo từng bước")

# Không nuốt phím khi đang gõ trong text item
txt = QGraphicsTextItem("abc")
txt.setTextInteractionFlags(Qt.TextEditorInteraction)
txt.setPos(10, 10)
c._scene.addItem(txt)
txt.setSelected(True)
txt.setFocus()
assert c._scene.focusItem() is txt, "text item phải đang có focus"
tp = QPointF(txt.pos())
press(c, Qt.Key_Right)
assert txt.pos() == tp, "đang gõ text: phím mũi tên KHÔNG được di chuyển item"
print("OK: phím mũi tên không nuốt khi đang gõ text")
txt.clearFocus()
c._scene.removeItem(txt)


# ----------------------------------------------------------------------
# 7b. M2-fix: cursor 4 hướng gán trên handle + handle bám khi item dời
# ----------------------------------------------------------------------
for it in c._scene.selectedItems():
    it.setSelected(False)
rect_item.setSelected(True)
c.state.tool = Tool.SELECT
c._update_handles()

for h in c._handles:
    assert h.cursor().shape() == HANDLE_CURSORS[h.index], \
        f"handle {h.index} cursor sai: {h.cursor().shape()}"
shapes = {h.cursor().shape() for h in c._handles}
assert {Qt.SizeFDiagCursor, Qt.SizeBDiagCursor,
        Qt.SizeVerCursor, Qt.SizeHorCursor} <= shapes, "phải đủ 4 hướng cursor"
print("OK: cursor 4 hướng (FDiag/BDiag/Ver/Hor) gán đúng trên từng handle")

tl_before = QPointF(c._handles[HANDLE_TL].pos())
rect_item.moveBy(20, 15)
c._position_handles()
assert c._handles[HANDLE_TL].pos() == tl_before + QPointF(20, 15), \
    f"handle TL phải bám theo item dời: {tl_before} -> {c._handles[HANDLE_TL].pos()}"
rect_item.moveBy(-20, -15)
c._position_handles()
print("OK: handle bám vị trí khi item di chuyển")


# ----------------------------------------------------------------------
# 8. M2-C: readout W×H phát signal khi resize + finished khi xong
# ----------------------------------------------------------------------
for it in c._scene.selectedItems():
    it.setSelected(False)
rect_item.setSelected(True)
c.state.tool = Tool.SELECT
c._update_handles()

preview = []
finished = []
c.resize_preview.connect(lambda w, h: preview.append((w, h)))
c.resize_finished.connect(lambda: finished.append(True))

O2 = rect_item.sceneBoundingRect()
c._begin_resize(HANDLE_BR)
c._resize_to(QPointF(O2.left() + O2.width() * 1.5,
                     O2.top() + O2.height() * 1.5))
assert preview, "resize phải phát resize_preview"
pw, ph = preview[-1]
assert pw > O2.width() and ph > O2.height(), \
    f"readout phải phản ánh kích thước lớn hơn: {pw}x{ph}"
c._commit_resize()
assert finished, "kết thúc resize phải phát resize_finished"
print(f"OK: readout phát W×H khi resize ({round(pw)}×{round(ph)}) + finished khi xong")

# render không kèm handle (handle ẩn sau clearSelection)
rect_item.setSelected(True)
c._update_handles()
out = c.render_to_image()
assert out.width() == 400 and out.height() == 300, "render sai kích thước nền"
assert all(not h.isVisible() for h in c._handles), \
    "render_to_image phải ẩn handle (qua clearSelection)"
print("OK: render_to_image ẩn handle, không lẫn vào ảnh xuất")


# ----------------------------------------------------------------------
# 9. Direct-select qua mousePress thật: vẽ vùng trống vẫn tạo nét;
#    nhấn trúng object thì CHỌN (không vẽ)
# ----------------------------------------------------------------------
def press_at(canvas, scene_pt, button=Qt.LeftButton, mod=Qt.NoModifier):
    vp = canvas.mapFromScene(scene_pt)
    pos = QPointF(vp)
    ev = QMouseEvent(QEvent.MouseButtonPress, pos, button, button, mod)
    canvas.mousePressEvent(ev)


# Đưa rect_item về trạng thái sạch (các test trước để lại scale/pos) để toạ độ
# hardcode dưới đây trúng nét.
rect_item.setTransform(QTransform())
rect_item.setPos(0, 0)
for it in c._scene.selectedItems():
    it.setSelected(False)
c._update_handles()
app.processEvents()

# (a) Công cụ vẽ + nhấn vùng trống → bắt đầu nét (tạo _temp_item), không chọn
c.state.tool = Tool.RECT
press_at(c, QPointF(370, 270))   # góc xa, ngoài rect_item
assert c._temp_item is not None, "click vùng trống ở công cụ vẽ phải tạo _temp_item"
assert not c._select_drag, "vẽ vùng trống không được vào chế độ select-drag"
# dọn trạng thái vẽ dở
if c._temp_item is not None and c._temp_item.scene() is not None:
    c._scene.removeItem(c._temp_item)
c._temp_item = None
c._start = None
print("OK: công cụ vẽ + vùng trống → tạo nét vẽ (không chọn)")

# (b) Công cụ vẽ + nhấn TRÚNG nét object → vào select-drag, KHÔNG tạo nét vẽ.
#     (Việc QGraphicsScene đánh dấu selected diễn ra khi chạy GUI thật; event
#      tổng hợp ở offscreen không kích hoạt selection nội bộ của Qt — nên ở đây
#      chỉ kiểm quyết định nhánh: không vẽ + bật cờ select-drag.)
c.state.tool = Tool.RECT
press_at(c, QPointF(100, 50))    # trên cạnh trên của rect_item
assert c._temp_item is None, "nhấn trúng object ở công cụ vẽ KHÔNG được tạo nét"
assert c._select_drag, "nhấn trúng object phải vào chế độ select-drag"
# kết thúc drag để reset cờ
rel = QMouseEvent(QEvent.MouseButtonRelease, QPointF(c.mapFromScene(QPointF(100, 50))),
                  Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
c.mouseReleaseEvent(rel)
assert not c._select_drag, "release phải reset _select_drag"
print("OK: công cụ vẽ + trúng object → direct-select (không vẽ), bật select-drag")

print("=== MOVE + RESIZE OK ===")
