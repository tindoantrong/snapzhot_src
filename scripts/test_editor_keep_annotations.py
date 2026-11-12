"""QC — Editor: vẽ chú thích trên ảnh A, chuyển sang ảnh B, quay lại A vẫn còn.

1. Vẽ mũi tên + chữ + số bước trên A → mở B → B sạch.
2. Quay lại A → đủ chú thích, đúng vị trí, vẫn là item (chọn được), số bước tiếp tục.
3. Làm mờ/cắt ảnh nền cũng được giữ (ảnh nền đã sửa, không đọc lại từ đĩa).
4. Ảnh chưa vẽ gì → không cất, mở lại dùng ảnh truyền vào.
5. Ảnh mới chụp (id mới) không dính chú thích ảnh cũ.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QGraphicsItem

app = QApplication([])

from app.editor.canvas import ArrowItem, ResizeHandle, StepItem
from app.editor.commands import AddItemCommand, CropCommand
from app.editor.editor_window import EditorWindow


def img(color: str, w=400, h=300) -> QImage:
    im = QImage(w, h, QImage.Format_ARGB32)
    im.fill(QColor(color))
    return im


def annotations(w):
    c = w.canvas
    return [it for it in c._scene.items()
            if it.parentItem() is None and it is not c._bg_item
            and not isinstance(it, ResizeHandle)]


w = EditorWindow()
c = w.canvas

# 1
w.load_image(img("#ffffff"), capture_id=1)
arrow = ArrowItem(QPointF(10, 10), QPointF(200, 150), QColor("red"), 4)
arrow.setFlag(QGraphicsItem.ItemIsSelectable, True)
c.undo_stack.push(AddItemCommand(c._scene, arrow))
step = StepItem(1, QColor("blue"), 30)
step.setPos(80, 80)
c.undo_stack.push(AddItemCommand(c._scene, step))
c.state.step_number = 2
assert len(annotations(w)) == 2

w.load_image(img("#000000"), capture_id=2)
assert annotations(w) == [], "ảnh B phải sạch"
assert c._bg_item.pixmap().toImage().pixelColor(5, 5) == QColor("#000000")
assert c.state.step_number == 1
print("OK 1: chuyển sang ảnh khác -> sạch")

# 2
w.load_image(img("#ffffff"), capture_id=1)
items = annotations(w)
assert arrow in items and step in items, items
assert step.pos() == QPointF(80, 80)
assert arrow.flags() & QGraphicsItem.ItemIsSelectable
assert c.state.step_number == 2 and w.step_spin.value() == 2
assert w.current_capture_id == 1
print("OK 2: quay lại ảnh A -> còn mũi tên + số bước, sửa tiếp được")

# 3
c.undo_stack.push(CropCommand(c._scene, c._bg_item, QRectF(0, 0, 300, 200).toRect()))
w.load_image(img("#000000"), capture_id=2)
w.load_image(img("#ffffff"), capture_id=1)  # ảnh trên đĩa vẫn 400x300
assert c._bg_item.pixmap().width() == 300 and c._scene.sceneRect().width() == 300
assert arrow in annotations(w)
print("OK 3: ảnh đã cắt -> giữ nguyên bản đã cắt")

# 4
assert 2 not in w._sessions, "ảnh B chưa vẽ gì -> không cất"
w.load_image(img("#00ff00"), capture_id=2)
assert c._bg_item.pixmap().toImage().pixelColor(5, 5) == QColor("#00ff00")
print("OK 4: ảnh chưa vẽ -> đọc ảnh truyền vào")

# 5
w.load_image(img("#ffffff"), capture_id=1)
w.load_image(img("#123456"), capture_id=99)
assert annotations(w) == []
w.load_image(img("#ffffff"), capture_id=1)
assert arrow in annotations(w) and step in annotations(w)
print("OK 5: ảnh mới không dính chú thích cũ; A vẫn còn")

# render vẫn gồm chú thích
out = c.render_to_image()
assert out.width() == 300
print("=== EDITOR KEEP ANNOTATIONS OK ===")
