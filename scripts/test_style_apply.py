"""Test sửa style của item ĐÃ CHỌN (Slice 1): màu/độ dày/cỡ chữ + undo.

Trọng tâm: apply_style_to_selection() áp đúng thuộc tính theo loại item, tạo
StyleCommand hoàn tác/làm lại được, và an toàn khi không có item nào được chọn.
Chạy offscreen, thao tác trực tiếp trên scene (không cần sự kiện chuột thật).
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPen, QPolygonF

app = QApplication([])

from app.editor.canvas import (
    Canvas,
    StepItem,
    capture_item_style,
    mutate_item_style,
)
from app.editor.commands import StyleCommand


def make_canvas() -> Canvas:
    c = Canvas()
    img = QImage(400, 300, QImage.Format_ARGB32)
    img.fill(Qt.white)
    c.load_image(img)
    return c


def add(c: Canvas, item):
    item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
    c._scene.addItem(item)
    return item


RED = QColor("#FF0000")
BLUE = QColor("#0000FF")

# ----------------------------------------------------------------------
# 1. Rect: đổi màu + độ dày pen, có undo/redo
# ----------------------------------------------------------------------
c = make_canvas()
rect = add(c, QGraphicsRectItem(0, 0, 80, 50))
rect.setPen(QPen(RED, 6))
rect.setSelected(True)

assert c.apply_style_to_selection(color=BLUE, width=12), "phải áp được style"
assert rect.pen().color().name() == "#0000ff", "màu pen phải đổi sang xanh"
assert rect.pen().width() == 12, "độ dày pen phải = 12"
print("OK: rect đổi màu + độ dày")

c.undo_stack.undo()
assert rect.pen().color().name() == "#ff0000" and rect.pen().width() == 6, \
    "undo phải khôi phục màu/độ dày cũ"
c.undo_stack.redo()
assert rect.pen().color().name() == "#0000ff" and rect.pen().width() == 12, \
    "redo phải áp lại style mới"
print("OK: undo/redo style rect")

# ----------------------------------------------------------------------
# 2. Text: đổi màu chữ + cỡ chữ; width bị bỏ qua
# ----------------------------------------------------------------------
c = make_canvas()
txt = add(c, QGraphicsTextItem("Xin chào"))
f = QFont(); f.setPointSize(20); txt.setFont(f)
txt.setDefaultTextColor(RED)
txt.setSelected(True)

assert c.apply_style_to_selection(color=BLUE, width=99, font_size=40)
assert txt.defaultTextColor().name() == "#0000ff", "màu chữ phải đổi"
assert txt.font().pointSize() == 40, "cỡ chữ phải = 40"
print("OK: text đổi màu + cỡ chữ (bỏ qua width)")

# ----------------------------------------------------------------------
# 3. StepItem: chỉ đổi màu badge
# ----------------------------------------------------------------------
c = make_canvas()
step = StepItem(1, RED, 40.0)
c._scene.addItem(step)
step.setSelected(True)
assert c.apply_style_to_selection(color=BLUE, width=10)
assert step._color.name() == "#0000ff", "màu badge phải đổi sang xanh"
c.undo_stack.undo()
assert step._color.name() == "#ff0000", "undo khôi phục màu badge"
print("OK: StepItem đổi màu badge + undo")

# ----------------------------------------------------------------------
# 4. Highlight (rect tô có alpha): đổi màu nhưng GIỮ alpha
# ----------------------------------------------------------------------
c = make_canvas()
hl = add(c, QGraphicsRectItem(0, 0, 60, 40))
fill = QColor(RED); fill.setAlpha(90)
hl.setBrush(QBrush(fill))
hl.setPen(QPen(Qt.NoPen))
hl.setSelected(True)
assert c.apply_style_to_selection(color=BLUE, width=8)
assert hl.brush().color().red() == 0 and hl.brush().color().blue() == 255, \
    "màu tô phải đổi sang xanh"
assert hl.brush().color().alpha() == 90, "alpha highlight phải giữ nguyên"
assert hl.pen().style() == Qt.NoPen, "pen NoPen không bị thêm nét"
print("OK: highlight đổi màu giữ alpha, không thêm nét")

# ----------------------------------------------------------------------
# 5. Mũi tên (polygon tô đặc): màu áp pen+brush, width KHÔNG đổi hình
# ----------------------------------------------------------------------
c = make_canvas()
poly = add(c, QGraphicsPolygonItem(QPolygonF()))
poly.setPen(QPen(RED, 1))
poly.setBrush(QBrush(RED))
poly.setSelected(True)
assert c.apply_style_to_selection(color=BLUE, width=20)
assert poly.pen().color().name() == "#0000ff", "pen mũi tên đổi màu"
assert poly.brush().color().name() == "#0000ff", "brush mũi tên đổi màu"
assert poly.pen().width() == 1, "độ dày pen mũi tên KHÔNG đổi (giữ 1)"
print("OK: mũi tên đổi màu pen+brush, width không tác động")

# ----------------------------------------------------------------------
# 6. Không có item nào được chọn -> trả False, không tạo command
# ----------------------------------------------------------------------
c = make_canvas()
ell = add(c, QGraphicsEllipseItem(0, 0, 30, 30))
ell.setPen(QPen(RED, 4))  # không select
before = c.undo_stack.count()
assert c.apply_style_to_selection(color=BLUE) is False, "không chọn gì -> False"
assert c.undo_stack.count() == before, "không được tạo command khi không chọn"
print("OK: không chọn item -> không tạo command")

# ----------------------------------------------------------------------
# 7. Gọi không có tham số nào -> False
# ----------------------------------------------------------------------
c = make_canvas()
r2 = add(c, QGraphicsRectItem(0, 0, 10, 10))
r2.setPen(QPen(RED, 3))
r2.setSelected(True)
assert c.apply_style_to_selection() is False, "không truyền gì -> False"
print("OK: không truyền tham số -> False")

# ----------------------------------------------------------------------
# 8. Style không đổi (cùng màu/độ dày) -> không tạo command
# ----------------------------------------------------------------------
c = make_canvas()
r3 = add(c, QGraphicsRectItem(0, 0, 10, 10))
r3.setPen(QPen(BLUE, 5))
r3.setSelected(True)
before = c.undo_stack.count()
assert c.apply_style_to_selection(color=BLUE, width=5) is False, \
    "áp đúng style cũ -> không thay đổi -> False"
assert c.undo_stack.count() == before, "không tạo command khi không có thay đổi"
print("OK: style trùng -> bỏ qua, không tạo command")

# ----------------------------------------------------------------------
# 9. Nhiều item cùng chọn -> một StyleCommand áp cho tất cả, undo cùng lúc
# ----------------------------------------------------------------------
c = make_canvas()
a = add(c, QGraphicsRectItem(0, 0, 20, 20)); a.setPen(QPen(RED, 4))
b = add(c, QGraphicsEllipseItem(0, 0, 20, 20)); b.setPen(QPen(RED, 4))
a.setSelected(True); b.setSelected(True)
assert c.apply_style_to_selection(color=BLUE)
assert a.pen().color().name() == "#0000ff" and b.pen().color().name() == "#0000ff"
c.undo_stack.undo()
assert a.pen().color().name() == "#ff0000" and b.pen().color().name() == "#ff0000", \
    "một lần undo phải khôi phục cả hai item"
print("OK: đa chọn -> một command, undo đồng loạt")

print("=== STYLE APPLY OK ===")
