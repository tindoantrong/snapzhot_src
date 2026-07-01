"""Test công cụ Crop + Zoom trong Editor (offscreen)."""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGraphicsRectItem
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage

app = QApplication([])

from app.editor.canvas import Canvas, Tool, StepItem
from app.editor.editor_window import EditorWindow

img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#dddddd"))


def count_annotations(c):
    return sum(1 for it in c._scene.items() if it is not c._bg_item)


ed = EditorWindow()
c = ed.canvas
c.load_image(img)

# --- Thêm vài annotation tại vị trí biết trước ---
rect = QGraphicsRectItem(QRectF(100, 90, 20, 20))
c._finalize(rect)                      # pos = (0,0)
c.state.tool = Tool.STEP
c.state.step_number = 1
c._add_step(QPointF(200, 150))         # StepItem.setPos quanh (200,150)
step = next(it for it in c._scene.items() if isinstance(it, StepItem))

rect_pos0 = QPointF(rect.pos())
step_pos0 = QPointF(step.pos())
assert count_annotations(c) == 2, f"phải 2 chú thích, got {count_annotations(c)}"
assert c._scene.sceneRect() == QRectF(0, 0, 400, 300), "sceneRect ban đầu sai"
print("OK: chuẩn bị ảnh 400x300 + 2 annotation")

# --- Crop vùng (50,40, 200x150) ---
crop_rect = QRectF(50, 40, 200, 150)
c.state.tool = Tool.CROP
c._apply_crop(crop_rect)

assert c._scene.sceneRect() == QRectF(0, 0, 200, 150), \
    f"sceneRect sau crop phải 0,0,200,150 got {c._scene.sceneRect()}"
assert c._bg_item.pixmap().width() == 200 and c._bg_item.pixmap().height() == 150, \
    "pixmap nền phải bị cắt còn 200x150"
print("OK: sceneRect + pixmap nền cắt đúng 200x150")

# Item dời đi -topLeft = (-50,-40)
assert rect.pos() == rect_pos0 - QPointF(50, 40), \
    f"rect phải dời -50,-40: {rect_pos0} -> {rect.pos()}"
assert step.pos() == step_pos0 - QPointF(50, 40), \
    f"step phải dời -50,-40: {step_pos0} -> {step.pos()}"
assert count_annotations(c) == 2, "crop không được làm mất annotation"
print("OK: annotation dời đúng -50,-40 và vẫn còn đủ")

# render ra đúng kích thước cắt
out = c.render_to_image()
assert out.width() == 200 and out.height() == 150, \
    f"render sau crop phải 200x150 got {out.width()}x{out.height()}"
print("OK: render_to_image() ra đúng 200x150")

# --- Undo crop: khôi phục nguyên trạng ---
c.undo_stack.undo()
assert c._scene.sceneRect() == QRectF(0, 0, 400, 300), "undo phải khôi phục sceneRect"
assert c._bg_item.pixmap().width() == 400 and c._bg_item.pixmap().height() == 300, \
    "undo phải khôi phục pixmap nền 400x300"
assert rect.pos() == rect_pos0, f"undo phải khôi phục vị trí rect, got {rect.pos()}"
assert step.pos() == step_pos0, f"undo phải khôi phục vị trí step, got {step.pos()}"
out2 = c.render_to_image()
assert out2.width() == 400 and out2.height() == 300, "undo: render về 400x300"
print("OK: undo crop khôi phục nguyên trạng (sceneRect, pixmap, vị trí item, render)")

# redo lại
c.undo_stack.redo()
assert c._scene.sceneRect() == QRectF(0, 0, 200, 150), "redo phải áp dụng lại crop"
print("OK: redo crop áp dụng lại")
c.undo_stack.undo()  # về nguyên trạng cho phần zoom

# --- Zoom: không ảnh hưởng render, có tắt auto_fit ---
c.zoom_fit()
assert c._auto_fit is True, "fit phải bật auto_fit"
c.zoom_in()
assert c._auto_fit is False, "zoom thủ công phải tắt auto_fit"
scale_in = c.transform().m11()
c.zoom_out()
assert c.transform().m11() < scale_in, "zoom out phải nhỏ hơn zoom in"
c.zoom_actual()
assert abs(c.transform().m11() - 1.0) < 1e-6, "100% phải reset transform về 1.0"
print("OK: zoom in/out/fit/100% + cờ auto_fit hoạt động đúng")

# Zoom không đổi kích thước ảnh xuất
c.zoom_in()
c.zoom_in()
out3 = c.render_to_image()
assert out3.width() == 400 and out3.height() == 300, \
    f"zoom KHÔNG được ảnh hưởng render, got {out3.width()}x{out3.height()}"
print("OK: render_to_image() độc lập với mức zoom")

# resize khi auto_fit=False không ghi đè zoom
c._auto_fit = False
zoom_before = c.transform().m11()
c.resize(800, 600)
assert abs(c.transform().m11() - zoom_before) < 1e-6, \
    "resize khi auto_fit=False không được ghi đè zoom thủ công"
print("OK: resize không ghi đè zoom thủ công khi auto_fit=False")

print("=== CROP + ZOOM OK ===")
