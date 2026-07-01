"""Smoke test toàn pipeline (chạy offscreen). Không thuộc app, chỉ để kiểm thử."""
import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor

app = QApplication([])

from app.library.library_manager import LibraryManager
from app.editor.canvas import Canvas, _make_arrow
from app.capture import capture_manager

img = capture_manager.capture_fullscreen()
print("capture:", img.width(), "x", img.height(), "null?", img.isNull())

lib = LibraryManager()
cap = lib.add_capture(img, tags="test, demo")
print("library add id =", cap.id, "thumb exists:", cap.thumbnail_path.exists())
print("list count:", len(lib.list_captures()))
print("search 'demo':", len(lib.list_captures("demo")))

c = Canvas()
c.load_image(img)
poly = _make_arrow(QPointF(10, 10), QPointF(120, 90), QColor("#FF0000"), 6)
print("arrow polygon points:", poly.count())
c._apply_blur(QRectF(20, 20, 100, 100))
out = c.render_to_image()
print("render:", out.width(), "x", out.height(), "null?", out.isNull())

lib.update_image(cap.id, out)
print("update OK")
lib.delete(cap.id)
print("delete OK, remaining:", len(lib.list_captures()))
lib.close()
print("=== TAT CA PIPELINE OK ===")
