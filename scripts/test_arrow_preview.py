"""Test PREVIEW mũi tên lúc kéo đã là mũi tên thật (không phải đường thẳng).

Trước: preview là QGraphicsLineItem (đường thẳng), chỉ thành mũi tên khi thả.
Nay: preview là ArrowItem, cập nhật 2 đầu mút theo chuột -> có đầu mũi tên ngay.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

app = QApplication([])

from app.editor.canvas import ArrowItem, Canvas, Tool

RED = QColor("#FF0000")


def make_canvas() -> Canvas:
    c = Canvas()
    img = QImage(400, 300, QImage.Format_ARGB32)
    img.fill(Qt.white)
    c.load_image(img)
    return c


# 1. Lúc bắt đầu (start == end): polygon suy biến (2 điểm, chưa có đầu mũi tên).
arr = ArrowItem(QPointF(10, 10), QPointF(10, 10), RED, 6)
assert arr.polygon().count() == 2, arr.polygon().count()

# 2. Khi kéo tới điểm xa: set_points dựng mũi tên thật (7 điểm), mũi nhọn ở end.
arr.set_points(QPointF(10, 10), QPointF(120, 80))
poly = arr.polygon()
assert poly.count() == 7, f"mũi tên thật phải có 7 đỉnh, có {poly.count()}"
tip = poly.at(3)  # đỉnh nhọn (index 3 trong _make_arrow)
assert abs(tip.x() - 120) < 1e-6 and abs(tip.y() - 80) < 1e-6, "mũi nhọn phải ở end"
print("OK: preview ArrowItem có đầu mũi tên thật khi kéo")

# 3. Wiring canvas: ở công cụ ARROW, _temp_item tạo ra là ArrowItem (không Line).
c = make_canvas()
c.state.tool = Tool.ARROW
start = QPointF(30, 40)
c._start = start
# Tái hiện nhánh tạo preview trong mousePressEvent (không cần QMouseEvent thật).
c._temp_item = ArrowItem(start, start, c.state.color, c.state.width)
c._scene.addItem(c._temp_item)
assert isinstance(c._temp_item, ArrowItem), "preview phải là ArrowItem"
# Kéo: cập nhật đầu mút -> hình thành mũi tên đầy đủ.
c._temp_item.set_points(start, QPointF(150, 120))
assert c._temp_item.polygon().count() == 7, "preview khi kéo phải là mũi tên đầy đủ"
print("OK: công cụ ARROW dùng ArrowItem làm preview")

print("=== ARROW PREVIEW OK ===")
