"""Test P4a: công cụ Stamp — chèn biểu tượng vector, chọn/đổi màu/undo/render."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage

app = QApplication([])

from app.editor.canvas import Canvas, Tool, StampItem, STAMP_NAMES, item_style_props
from app.editor.editor_window import EditorWindow

img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#dddddd"))


def stamps(c):
    return [it for it in c._scene.items() if isinstance(it, StampItem)]


# ---- _add_stamp tạo item + undo/redo ----
ed = EditorWindow()
c = ed.canvas
c.load_image(img)
c.state.tool = Tool.STAMP
c.state.stamp_name = "star"
c.state.color = QColor("#FF3B30")

n0 = c.undo_stack.count()
c._add_stamp(QPointF(100, 80))
st = stamps(c)
assert len(st) == 1, f"phải có 1 stamp, got {len(st)}"
assert c.undo_stack.count() == n0 + 1, "thêm stamp phải +1 command"
item = st[0]
assert item._name == "star", f"tên stamp sai: {item._name}"
assert item._color.name() == "#ff3b30", f"màu stamp sai: {item._color.name()}"
print("OK: _add_stamp tạo StampItem theo state")

c.undo_stack.undo()
assert len(stamps(c)) == 0, "undo phải gỡ stamp"
c.undo_stack.redo()
assert len(stamps(c)) == 1, "redo phải thêm lại stamp"
print("OK: undo/redo stamp")

# ---- set_color đổi _color ----
item = stamps(c)[0]
item.set_color(QColor("#00AA00"))
assert item._color.name() == "#00aa00", "set_color phải đổi _color"
print("OK: set_color đổi màu trực tiếp")

# ---- apply_style_to_selection(color) trên stamp đã chọn + undo/redo ----
c._scene.clearSelection()
item.setSelected(True)
assert c.apply_style_to_selection(color=QColor("#1E90FF")) is True
assert item._color.name() == "#1e90ff", "đổi màu qua panel phải hiệu lực"
c.undo_stack.undo()
assert item._color.name() == "#00aa00", "undo phải khôi phục màu cũ"
c.undo_stack.redo()
assert item._color.name() == "#1e90ff", "redo phải về màu mới"
print("OK: apply_style_to_selection màu stamp + undo/redo (qua stamp_color)")

# ---- item_style_props: color + opacity/shadow, KHÔNG width/fill ----
props = item_style_props(item)
assert "color" in props["groups"], "stamp phải có color"
assert "opacity" in props["groups"] and "shadow" in props["groups"]
assert "width" not in props["groups"], "stamp KHÔNG có width"
assert "fill" not in props["groups"], "stamp KHÔNG có fill"
print("OK: item_style_props stamp = color (+opacity/shadow), không width/fill")

# ---- Mọi glyph render được, render_to_image không null ----
c2 = Canvas(); c2.load_image(img)
for nm in STAMP_NAMES:
    c2.state.stamp_name = nm
    c2._add_stamp(QPointF(50, 50))
assert len(stamps(c2)) == len(STAMP_NAMES)
out = c2.render_to_image()
assert not out.isNull(), "render với stamp phải hợp lệ"
print("OK: render_to_image với", len(STAMP_NAMES), "glyph:", ", ".join(STAMP_NAMES))

# ---- Panel: nút chọn stamp cập nhật state ----
ed._select_stamp("heart")
assert ed.canvas.state.stamp_name == "heart", "nút stamp phải đặt state.stamp_name"
assert ed._stamp_buttons["heart"].isChecked(), "nút heart phải được đánh dấu"
print("OK: panel chọn glyph cập nhật state + đánh dấu nút")

print("=== STAMP OK ===")
