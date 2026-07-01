"""Test mũi tên (ArrowItem) đổi được ĐỘ DÀY NÉT + màu, có undo/redo.

Trước đây độ dày mũi tên bị "nướng" vào hình lúc vẽ nên panel chỉ hiện màu.
Nay ArrowItem lưu 2 đầu mút + width, dựng lại hình khi đổi width:
- item_style_props phải hiện cả nhóm "width" -> panel tự hiện slider độ dày.
- apply_style_to_selection(width=...) đổi hình (to/nhỏ nét) + undo/redo đúng.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

app = QApplication([])

from app.editor.canvas import (
    ArrowItem,
    Canvas,
    capture_item_style,
    item_style_props,
)

RED = QColor("#FF0000")
BLUE = QColor("#0000FF")


def make_canvas() -> Canvas:
    c = Canvas()
    img = QImage(400, 300, QImage.Format_ARGB32)
    img.fill(Qt.white)
    c.load_image(img)
    return c


def add_arrow(c: Canvas, width: int) -> ArrowItem:
    arr = ArrowItem(QPointF(10, 10), QPointF(120, 80), RED, width)
    arr.setFlag(arr.GraphicsItemFlag.ItemIsSelectable, True)
    c._scene.addItem(arr)
    return arr


def perp_extent(arr: ArrowItem) -> float:
    """Bề rộng vuông góc (chiều ngang khung bao polygon) ~ tỉ lệ với độ dày."""
    return arr.polygon().boundingRect().height()


# ----------------------------------------------------------------------
# 1. Panel: ArrowItem hiện nhóm color + width, width = giá trị hiện tại
# ----------------------------------------------------------------------
c = make_canvas()
arr = add_arrow(c, 6)
props = item_style_props(arr)
assert props["groups"] == ["color", "width", "opacity", "shadow"], props["groups"]
assert props["width"] == 6, props["width"]
assert props["color"].name() == "#ff0000"
print("OK: panel mũi tên hiện cả màu lẫn độ dày nét")

# ----------------------------------------------------------------------
# 2. Đổi độ dày -> hình dựng lại to hơn, _width cập nhật, có undo/redo
# ----------------------------------------------------------------------
arr.setSelected(True)
extent6 = perp_extent(arr)
assert c.apply_style_to_selection(width=20), "phải áp được độ dày mới"
assert arr._width == 20, arr._width
extent20 = perp_extent(arr)
assert extent20 > extent6, f"nét dày hơn phải có khung bao lớn hơn ({extent20} > {extent6})"
print(f"OK: đổi độ dày dựng lại hình ({extent6:.1f} -> {extent20:.1f})")

c.undo_stack.undo()
assert arr._width == 6, "undo phải khôi phục width cũ"
assert abs(perp_extent(arr) - extent6) < 1e-6, "undo phải khôi phục hình cũ"
c.undo_stack.redo()
assert arr._width == 20 and abs(perp_extent(arr) - extent20) < 1e-6, \
    "redo phải dựng lại hình dày"
print("OK: undo/redo độ dày mũi tên")

# ----------------------------------------------------------------------
# 3. Đổi màu mũi tên: pen + brush đổi, KHÔNG đổi hình/độ dày
# ----------------------------------------------------------------------
c = make_canvas()
arr = add_arrow(c, 8)
arr.setSelected(True)
extent_before = perp_extent(arr)
assert c.apply_style_to_selection(color=BLUE)
assert arr.pen().color().name() == "#0000ff" and arr.brush().color().name() == "#0000ff"
assert arr._width == 8, "đổi màu không được đụng độ dày"
assert abs(perp_extent(arr) - extent_before) < 1e-6, "đổi màu không đổi hình"
print("OK: đổi màu mũi tên giữ nguyên độ dày/hình")

# ----------------------------------------------------------------------
# 4. Đổi đồng thời màu + độ dày trong một command, undo gộp
# ----------------------------------------------------------------------
c = make_canvas()
arr = add_arrow(c, 5)
arr.setSelected(True)
old_snap = capture_item_style(arr)
assert c.apply_style_to_selection(color=BLUE, width=16)
assert arr.pen().color().name() == "#0000ff" and arr._width == 16
c.undo_stack.undo()
assert arr.pen().color().name() == "#ff0000" and arr._width == 5, \
    "một undo khôi phục cả màu lẫn độ dày"
# Khôi phục đúng polygon cũ.
assert arr.polygon() == old_snap["arrow_polygon"], "undo khôi phục đúng hình cũ"
print("OK: đổi màu+độ dày trong một command, undo gộp đúng")

print("=== ARROW WIDTH OK ===")
