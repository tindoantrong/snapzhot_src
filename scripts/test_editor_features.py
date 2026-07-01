"""Test Undo/Redo + Step tool (offscreen)."""
import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage

app = QApplication([])

from app.editor.canvas import Canvas, Tool, StepItem
from app.editor.editor_window import EditorWindow

img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#dddddd"))


def count_annotations(c):
    return sum(1 for it in c._scene.items() if it is not c._bg_item)


# --- Undo/Redo với item thường (rect) ---
ed = EditorWindow()
c = ed.canvas
c.load_image(img)
assert count_annotations(c) == 0, "ban đầu phải 0 chú thích"

# Mô phỏng thêm 1 rect qua _finalize
from PySide6.QtWidgets import QGraphicsRectItem
r = QGraphicsRectItem(QRectF(10, 10, 50, 50))
c._finalize(r)
assert count_annotations(c) == 1, f"sau khi thêm phải 1, got {count_annotations(c)}"

c.undo_stack.undo()
assert count_annotations(c) == 0, "undo phải gỡ item"
c.undo_stack.redo()
assert count_annotations(c) == 1, "redo phải thêm lại item"
print("OK: Undo/Redo item thường")

# --- Step tool: đặt 3 badge, số tăng dần ---
c.state.tool = Tool.STEP
c.state.step_number = 1
for i in range(3):
    c._add_step(QPointF(50 + i * 40, 100))
steps = [it for it in c._scene.items() if isinstance(it, StepItem)]
numbers = sorted(s._number for s in steps)
assert numbers == [1, 2, 3], f"số bước phải 1,2,3 got {numbers}"
assert c.state.step_number == 4, f"số kế tiếp phải 4 got {c.state.step_number}"
print("OK: Step tool tăng số 1->2->3, kế tiếp =", c.state.step_number)

# Undo 1 badge -> còn 2, redo lại
c.undo_stack.undo()
steps = [it for it in c._scene.items() if isinstance(it, StepItem)]
assert len(steps) == 2, f"sau undo còn 2 badge, got {len(steps)}"
print("OK: Undo badge số bước")

# --- Blur undo/redo ---
c.state.tool = Tool.BLUR
before = c._bg_item.pixmap().toImage().pixel(20, 20)
c._apply_blur(QRectF(0, 0, 100, 100))
c.undo_stack.undo()
after_undo = c._bg_item.pixmap().toImage().pixel(20, 20)
assert before == after_undo, "undo blur phải khôi phục pixel gốc"
print("OK: Undo blur khôi phục pixel")

# --- spinbox đồng bộ ---
assert ed.step_spin.value() == c.state.step_number, "spinbox phải đồng bộ số bước"
print("OK: SpinBox số bước đồng bộ =", ed.step_spin.value())

# render ra ảnh để chắc StepItem.paint không lỗi
out = c.render_to_image()
assert not out.isNull()
print("OK: render có badge số bước, kích thước", out.width(), "x", out.height())

print("=== UNDO/REDO + STEP TOOL OK ===")
