"""Test P4b: công cụ Spotlight — overlay tối ngoài vùng chọn, undo, render."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QGraphicsItem

app = QApplication([])

from app.editor.canvas import Canvas, SpotlightItem

# Ảnh nền sáng đều để dễ so độ sáng trong/ngoài hole.
img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#FFFFFF"))


def spots(c):
    return [it for it in c._scene.items() if isinstance(it, SpotlightItem)]


# ---- _add_spotlight tạo overlay + undo/redo ----
c = Canvas()
c.load_image(img)
n0 = c.undo_stack.count()
c._add_spotlight(QRectF(120, 90, 160, 120))
sp = spots(c)
assert len(sp) == 1, f"phải có 1 spotlight, got {len(sp)}"
assert c.undo_stack.count() == n0 + 1, "thêm spotlight phải +1 command"
item = sp[0]
print("OK: _add_spotlight tạo overlay + 1 command")

# ---- boundingRect == sceneRect; non-selectable/non-movable ----
assert item.boundingRect() == c._scene.sceneRect(), "boundingRect phải = sceneRect"
assert not (item.flags() & QGraphicsItem.ItemIsSelectable), "spotlight KHÔNG selectable"
assert not (item.flags() & QGraphicsItem.ItemIsMovable), "spotlight KHÔNG movable"
assert item.zValue() == -500, "zValue phải -500"
print("OK: boundingRect=sceneRect, non-selectable/movable, z=-500")

# ---- selected_annotation None dù spotlight tồn tại ----
c._scene.clearSelection()
assert c.selected_annotation() is None, "spotlight không được lọt selection"
print("OK: selected_annotation None (spotlight ngoài selection)")

# ---- undo/redo ----
c.undo_stack.undo()
assert len(spots(c)) == 0, "undo phải gỡ spotlight"
c.undo_stack.redo()
assert len(spots(c)) == 1, "redo phải thêm lại spotlight"
print("OK: undo/redo spotlight")

# ---- render: pixel NGOÀI hole tối hơn pixel TRONG hole ----
out = c.render_to_image()
assert not out.isNull(), "render phải hợp lệ"
# hole = (120,90,160,120) → tâm (200,150) trong; (20,20) ngoài.
inside = QColor(out.pixel(200, 150))
outside = QColor(out.pixel(20, 20))
def lum(col):
    return col.red() + col.green() + col.blue()
assert lum(outside) < lum(inside), \
    f"ngoài hole phải tối hơn trong: out={lum(outside)} in={lum(inside)}"
print(f"OK: render — ngoài hole tối ({lum(outside)}) < trong hole ({lum(inside)})")

# ---- hole quá nhỏ → không tạo item, không tăng undo ----
c2 = Canvas(); c2.load_image(img)
n = c2.undo_stack.count()
c2._add_spotlight(QRectF(10, 10, 1, 1))   # w<2,h<2
assert len(spots(c2)) == 0, "hole quá nhỏ KHÔNG tạo overlay"
assert c2.undo_stack.count() == n, "hole quá nhỏ KHÔNG tăng undo"
print("OK: hole quá nhỏ bị bỏ qua")

print("=== SPOTLIGHT OK ===")
