"""Test P3: Express Styles (Quick Styles) — áp combo style 1-command + state."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication, QGraphicsRectItem
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QImage, QPen

app = QApplication([])

from app.editor.editor_window import EditorWindow, QUICK_STYLES

img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#dddddd"))


def preset_by_name(name):
    return next(p for p in QUICK_STYLES if p["name"] == name)


def add_rect(c, rect):
    r = QGraphicsRectItem(rect)
    r.setPen(QPen(QColor("#FF0000"), 4))
    c._finalize(r)
    return r


# ---- Chọn rect → áp preset "Hộp vàng" (color+width+fill) ----
ed = EditorWindow()
c = ed.canvas
c.load_image(img)
r = add_rect(c, QRectF(10, 10, 60, 40))
c._scene.clearSelection()
r.setSelected(True)

n_before = c.undo_stack.count()
hop_vang = preset_by_name("Hộp vàng")
ed._apply_quick_style(hop_vang)

assert r.pen().color().name() == "#e6a700", f"viền sai: {r.pen().color().name()}"
assert r.pen().width() == 2, f"độ dày sai: {r.pen().width()}"
assert r.brush().style() == Qt.SolidPattern, "fill phải bật"
assert r.brush().color().name() == "#ffe680", f"nền sai: {r.brush().color().name()}"
# State vẽ-mới cập nhật theo preset.
assert c.state.color.name() == "#e6a700", "state.color phải theo preset"
assert c.state.width == 2, "state.width phải theo preset"
print("OK: preset Hộp vàng áp đúng pen/width/fill + cập nhật state")

# ---- 1 command: undo 1 lần khôi phục toàn bộ ----
assert c.undo_stack.count() == n_before + 1, \
    f"preset phải tạo đúng 1 command, got {c.undo_stack.count() - n_before}"
c.undo_stack.undo()
assert r.pen().color().name() == "#ff0000", "undo phải khôi phục viền đỏ"
assert r.pen().width() == 4, "undo phải khôi phục độ dày 4"
assert r.brush().style() == Qt.NoBrush, "undo phải khôi phục NoBrush"
print("OK: 1 command/preset — undo khôi phục toàn bộ")

# ---- Preset có shadow → item có graphicsEffect ----
r2 = add_rect(c, QRectF(100, 10, 50, 50))
c._scene.clearSelection()
r2.setSelected(True)
ed._apply_quick_style(preset_by_name("Trắng đổ bóng"))
assert r2.graphicsEffect() is not None, "preset shadow phải tạo effect"
assert r2.pen().color().name() == "#ffffff", "viền phải trắng"
print("OK: preset shadow tạo graphicsEffect")

# ---- Không chọn gì → không lỗi, vẫn cập nhật state ----
c._scene.clearSelection()
n2 = c.undo_stack.count()
ed._apply_quick_style(preset_by_name("Xanh dương"))
assert c.state.color.name() == "#1e90ff", "state.color cập nhật dù không chọn"
assert c.state.width == 3, "state.width cập nhật dù không chọn"
assert c.undo_stack.count() == n2, "không chọn gì thì KHÔNG tạo command"
print("OK: không chọn gì → cập nhật state, không tạo command")

# ---- Chip pixmap render không lỗi ----
for p in QUICK_STYLES:
    pm = EditorWindow._quick_style_pixmap(p)
    assert not pm.isNull(), f"chip '{p['name']}' null"
print("OK: chip preview render hợp lệ cho", len(QUICK_STYLES), "preset")

print("=== QUICK STYLES OK ===")
