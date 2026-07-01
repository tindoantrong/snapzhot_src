"""Test P5a: Delete/Backspace KHÔNG xoá object khi đang gõ text; vẫn xoá khi không edit."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent

app = QApplication([])

from app.editor.canvas import Canvas

img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#FFFFFF"))


def backspace_event():
    return QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)


# ---- ĐANG GÕ TEXT: Backspace không được xoá object ----
c = Canvas()
c.load_image(img)
c._add_text(QPointF(50, 50))                    # tạo text item ở chế độ edit + setFocus
# Lấy text item vừa thêm (focusItem chính là nó).
focus = c._scene.focusItem()
assert focus is not None, "text item phải có focus sau _add_text"
assert focus.textInteractionFlags() & Qt.TextEditorInteraction, "text item phải ở chế độ edit"
n_items_before = len(c._scene.items())

c.keyPressEvent(backspace_event())

assert focus in c._scene.items(), "ĐANG GÕ: Backspace KHÔNG được xoá text object"
assert len(c._scene.items()) == n_items_before, "ĐANG GÕ: số item không đổi"
print("OK: đang gõ text — Backspace không xoá object")

# ---- KHÔNG edit: Backspace vẫn xoá object đang chọn ----
c2 = Canvas()
c2.load_image(img)
c2._add_stamp(QPointF(120, 120))                # stamp item bình thường
stamp = [it for it in c2._scene.items()
         if it is not c2._bg_item and type(it).__name__ == "StampItem"][0]
c2._scene.clearFocus()
c2._scene.clearSelection()
stamp.setSelected(True)
assert c2._scene.focusItem() is None or \
    type(c2._scene.focusItem()).__name__ != "QGraphicsTextItem", \
    "không được có text item edit đang focus"
assert stamp in c2._scene.items(), "stamp phải tồn tại trước khi xoá"

c2.keyPressEvent(backspace_event())

assert stamp not in c2._scene.items(), "KHÔNG edit: Backspace phải xoá object đang chọn"
print("OK: không edit — Backspace xoá object đang chọn")

# undo phục hồi để chắc chắn dùng DeleteItemsCommand
c2.undo_stack.undo()
assert stamp in c2._scene.items(), "undo phải phục hồi object đã xoá (qua DeleteItemsCommand)"
print("OK: xoá đi qua DeleteItemsCommand (undo phục hồi được)")

print("=== TEXT DELETE GUARD OK ===")
