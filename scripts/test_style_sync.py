"""Test Slice 2: panel đồng bộ theo ITEM đang chọn (nhóm thuộc tính + giá trị).

Trọng tâm:
- item_style_props() trả đúng nhóm + giá trị theo loại item.
- EditorWindow._refresh_props() hiện đúng nhóm cho item đang chọn (cả ở Select),
  đồng bộ slider/màu về style item, và KHÔNG phát sinh undo khi sync.
Chạy offscreen.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QGraphicsRectItem,
    QGraphicsTextItem,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPen

app = QApplication([])

from app.editor.canvas import StepItem, Tool, item_style_props
from app.editor.editor_window import EditorWindow

RED = QColor("#FF0000")
img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#dddddd"))


def fresh():
    ed = EditorWindow()
    ed.canvas.load_image(img)
    return ed, ed.canvas


def add(c, item):
    item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
    c._scene.addItem(item)
    return item


def visible(ed, key):
    # Cửa sổ không .show() khi test offscreen nên isVisible() luôn False; dùng
    # isHidden() phản ánh đúng cờ setVisible() mà _refresh_props đặt.
    return not ed._prop_groups[key].isHidden()


# ----------------------------------------------------------------------
# 1. item_style_props theo loại item
# ----------------------------------------------------------------------
rect = QGraphicsRectItem(0, 0, 10, 10)
rect.setPen(QPen(QColor("#123456"), 7))
# P2a: opacity/shadow là nhóm universal → luôn đứng cuối list groups.
# P2b: rect/ellipse có viền thêm "fill" (đứng trước opacity/shadow).
EXTRA = ["opacity", "shadow"]
p = item_style_props(rect)
assert p["groups"] == ["color", "width", "fill"] + EXTRA, p["groups"]
assert p["color"].name() == "#123456" and p["width"] == 7
assert p["font_size"] is None
print("OK: props rect = color+width, đúng giá trị")

txt = QGraphicsTextItem("x")
f = QFont(); f.setPointSize(33); txt.setFont(f)
txt.setDefaultTextColor(QColor("#00ff00"))
p = item_style_props(txt)
assert p["groups"] == ["color", "font"] + EXTRA and p["font_size"] == 33
assert p["color"].name() == "#00ff00" and p["width"] is None
print("OK: props text = color+font, đúng cỡ chữ")

step = StepItem(2, RED, 30.0)
p = item_style_props(step)
assert p["groups"] == ["color"] + EXTRA and p["color"].name() == "#ff0000"
print("OK: props step = color")

hl = QGraphicsRectItem(0, 0, 10, 10)
fill = QColor(RED); fill.setAlpha(90)
hl.setBrush(QBrush(fill)); hl.setPen(QPen(Qt.NoPen))
p = item_style_props(hl)
assert p["groups"] == ["color"] + EXTRA and p["width"] is None, p
assert p["color"].red() == 255
print("OK: props highlight = chỉ color (NoPen)")

# ----------------------------------------------------------------------
# 2. Chọn item ở công cụ CHỌN → panel hiện đúng nhóm + sync giá trị, không undo
# ----------------------------------------------------------------------
ed, c = fresh()
ed._select_tool(Tool.SELECT)
# Select rỗng: SELECT không có thuộc tính → các nhóm ẩn.
assert not visible(ed, "color") and not visible(ed, "width")

r = add(c, QGraphicsRectItem(0, 0, 40, 30))
r.setPen(QPen(QColor("#0a0b0c"), 15))
before = c.undo_stack.count()
r.setSelected(True)            # → selection_changed → _refresh_props
assert visible(ed, "color") and visible(ed, "width"), "phải hiện color+width"
assert not visible(ed, "font"), "rect không hiện nhóm cỡ chữ"
assert ed.width_slider.value() == 15, "slider phải đồng bộ = 15"
assert ed.width_label.text() == "15 pt"
assert c.undo_stack.count() == before, "đồng bộ KHÔNG được tạo undo"
print("OK: chọn rect ở công cụ Chọn → panel + sync đúng, không undo")

# ----------------------------------------------------------------------
# 3. Chọn TEXT ở công cụ vẽ (ARROW) → vẫn hiện nhóm của text, sync cỡ chữ
# ----------------------------------------------------------------------
ed, c = fresh()
ed._select_tool(Tool.ARROW)
t = add(c, QGraphicsTextItem("hello"))
tf = QFont(); tf.setPointSize(28); t.setFont(tf)
t.setDefaultTextColor(QColor("#ff8800"))
before = c.undo_stack.count()
t.setSelected(True)
assert visible(ed, "color") and visible(ed, "font"), "text → color+font"
assert not visible(ed, "width"), "text không hiện độ dày nét"
assert ed.font_slider.value() == 28, "cỡ chữ phải đồng bộ = 28"
assert c.undo_stack.count() == before, "sync text không tạo undo"
print("OK: chọn text ở công cụ vẽ → panel theo text, sync cỡ chữ, không undo")

# ----------------------------------------------------------------------
# 4. Bỏ chọn → panel quay về theo công cụ hiện tại
# ----------------------------------------------------------------------
ed, c = fresh()
ed._select_tool(Tool.RECT)         # RECT: color+width
r = add(c, QGraphicsTextItem("y"))  # text → chỉ color+font khi chọn
r.setSelected(True)
assert visible(ed, "font") and not visible(ed, "width")
c._scene.clearSelection()           # → _refresh_props → theo công cụ RECT
assert visible(ed, "width") and not visible(ed, "font"), \
    "bỏ chọn phải quay lại nhóm của công cụ RECT"
print("OK: bỏ chọn → panel quay về theo công cụ")

# ----------------------------------------------------------------------
# 5. Đổi công cụ khi đang chọn item → vẫn ưu tiên item
# ----------------------------------------------------------------------
ed, c = fresh()
t = add(c, QGraphicsTextItem("z"))
t.setSelected(True)
ed._select_tool(Tool.RECT)          # đang có item chọn → panel theo item (text)
assert visible(ed, "font") and not visible(ed, "width"), \
    "đang chọn text thì đổi công cụ vẫn hiện nhóm của text"
print("OK: đổi công cụ khi đang chọn → ưu tiên item")

print("=== STYLE SYNC OK ===")
