"""Test P2a: Opacity + Shadow per-object (undo/redo, multi-select, render)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication, QGraphicsRectItem, QGraphicsEllipseItem
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QImage, QPen

app = QApplication([])

from app.editor.canvas import Canvas, item_style_props

img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#dddddd"))


def add_rect(c, rect):
    r = QGraphicsRectItem(rect)
    r.setPen(QPen(QColor("#FF0000"), 4))
    c._finalize(r)
    return r


def add_ellipse(c, rect):
    e = QGraphicsEllipseItem(rect)
    e.setPen(QPen(QColor("#00AA00"), 4))
    c._finalize(e)
    return e


def add_highlight(c, rect):
    # Highlight = brush mờ + NoPen (giống công cụ HIGHLIGHT thực tế).
    h = QGraphicsRectItem(rect)
    fill = QColor("#FFCC00"); fill.setAlpha(90)
    h.setBrush(QBrush(fill))
    h.setPen(QPen(Qt.NoPen))
    c._finalize(h)
    return h


def select_only(c, item):
    c._scene.clearSelection()
    item.setSelected(True)


# ---- Opacity: apply / undo / redo ----
c = Canvas()
c.load_image(img)
r = add_rect(c, QRectF(10, 10, 50, 50))
c._scene.clearSelection()
r.setSelected(True)
assert c.apply_style_to_selection(opacity=0.5) is True
assert abs(r.opacity() - 0.5) < 1e-6, f"opacity phải 0.5, got {r.opacity()}"
c.undo_stack.undo()
assert abs(r.opacity() - 1.0) < 1e-6, f"undo opacity phải 1.0, got {r.opacity()}"
c.undo_stack.redo()
assert abs(r.opacity() - 0.5) < 1e-6, f"redo opacity phải 0.5, got {r.opacity()}"
print("OK: opacity apply/undo/redo")

# ---- Shadow: apply / undo / redo ----
assert c.apply_style_to_selection(shadow=True) is True
assert r.graphicsEffect() is not None, "shadow phải tạo effect"
c.undo_stack.undo()
assert r.graphicsEffect() is None, "undo shadow phải gỡ effect"
c.undo_stack.redo()
assert r.graphicsEffect() is not None, "redo shadow phải tạo lại effect"
print("OK: shadow apply/undo/redo")

# ---- item_style_props chứa opacity/shadow ----
props = item_style_props(r)
assert "opacity" in props["groups"], "groups phải có opacity"
assert "shadow" in props["groups"], "groups phải có shadow"
assert abs(props["opacity"] - 0.5) < 1e-6, f"props opacity sai: {props['opacity']}"
assert props["shadow"] is True, "props shadow phải True"
print("OK: item_style_props có opacity/shadow + giá trị đúng")

# ---- Multi-select: 1 command khôi phục cả 2 ----
c2 = Canvas()
c2.load_image(img)
a = add_rect(c2, QRectF(0, 0, 30, 30))
b = add_rect(c2, QRectF(60, 0, 30, 30))
c2._scene.clearSelection()
a.setSelected(True)
b.setSelected(True)
before = c2.undo_stack.count()
assert c2.apply_style_to_selection(opacity=0.3) is True
assert c2.undo_stack.count() == before + 1, "multi-select phải gộp 1 command"
assert abs(a.opacity() - 0.3) < 1e-6 and abs(b.opacity() - 0.3) < 1e-6
c2.undo_stack.undo()
assert abs(a.opacity() - 1.0) < 1e-6 and abs(b.opacity() - 1.0) < 1e-6, \
    "undo 1 lần phải khôi phục cả 2 item"
print("OK: multi-select opacity gộp 1 command")

# ---- render_to_image với shadow + opacity không lỗi ----
c.apply_style_to_selection(opacity=0.6)
c.apply_style_to_selection(shadow=True)
out = c.render_to_image()
assert not out.isNull(), "render phải ra ảnh hợp lệ"
print("OK: render_to_image với shadow+opacity, size",
      out.width(), "x", out.height())

# ====================================================================
# P2b: FILL
# ====================================================================
cf = Canvas()
cf.load_image(img)

# ---- rect fill apply / undo / redo ----
rf = add_rect(cf, QRectF(10, 10, 50, 50))
assert rf.brush().style() == Qt.NoBrush, "rect ban đầu không có nền"
select_only(cf, rf)
assert cf.apply_style_to_selection(fill=QColor("#FF0000")) is True
assert rf.brush().style() == Qt.SolidPattern, "fill phải tạo brush solid"
assert rf.brush().color().red() == 255 and rf.brush().color().green() == 0, \
    f"nền phải đỏ, got {rf.brush().color().name()}"
cf.undo_stack.undo()
assert rf.brush().style() == Qt.NoBrush, "undo fill phải về NoBrush"
cf.undo_stack.redo()
assert rf.brush().color().red() == 255, "redo fill phải về đỏ"
print("OK: rect fill apply/undo/redo")

# ---- fill_enabled=False → NoBrush, undo khôi phục ----
assert cf.apply_style_to_selection(fill_enabled=False) is True
assert rf.brush().style() == Qt.NoBrush, "tắt fill phải NoBrush"
cf.undo_stack.undo()
assert rf.brush().style() == Qt.SolidPattern, "undo phải khôi phục nền"
print("OK: fill_enabled=False + undo")

# ---- Regression A: highlight đổi color vẫn recolor brush + GIỮ alpha ----
hl = add_highlight(cf, QRectF(100, 10, 40, 40))
select_only(cf, hl)
old_alpha = hl.brush().color().alpha()
assert cf.apply_style_to_selection(color=QColor("#0000FF")) is True
assert hl.brush().color().blue() == 255, "highlight phải đổi màu brush"
assert hl.brush().color().alpha() == old_alpha, "highlight phải giữ alpha"
print("OK: regression highlight — đổi color recolor brush + giữ alpha")

# ---- Regression: rect đổi color (viền) KHÔNG đụng brush ----
rf2 = add_rect(cf, QRectF(160, 10, 40, 40))
select_only(cf, rf2)
cf.apply_style_to_selection(fill=QColor("#00FF00"))   # bật nền xanh lá
before_fill = QColor(rf2.brush().color())
cf.apply_style_to_selection(color=QColor("#FF00FF"))  # đổi viền tím
assert rf2.pen().color().name() == "#ff00ff", "viền phải đổi tím"
assert rf2.brush().color().name() == before_fill.name(), \
    "đổi viền KHÔNG được đụng màu nền"
print("OK: regression rect — đổi color chỉ đổi viền, giữ nền")

# ---- item_style_props: fill cho rect/ellipse có viền, KHÔNG cho loại khác ----
assert "fill" in item_style_props(add_rect(cf, QRectF(0, 100, 20, 20)))["groups"]
assert "fill" in item_style_props(add_ellipse(cf, QRectF(40, 100, 20, 20)))["groups"]
assert "fill" not in item_style_props(hl)["groups"], "highlight KHÔNG có fill"
from app.editor.canvas import StepItem
from PySide6.QtWidgets import QGraphicsTextItem
assert "fill" not in item_style_props(QGraphicsTextItem("x"))["groups"], \
    "text KHÔNG có fill"
assert "fill" not in item_style_props(StepItem(1, QColor("#FF0000"), 30.0))["groups"], \
    "step KHÔNG có fill"
print("OK: item_style_props fill chỉ rect/ellipse có viền")

# ---- Multi-select rect gộp 1 command ----
ca = Canvas(); ca.load_image(img)
a1 = add_rect(ca, QRectF(0, 0, 30, 30))
b1 = add_rect(ca, QRectF(60, 0, 30, 30))
ca._scene.clearSelection(); a1.setSelected(True); b1.setSelected(True)
n0 = ca.undo_stack.count()
assert ca.apply_style_to_selection(fill=QColor("#123456")) is True
assert ca.undo_stack.count() == n0 + 1, "multi-select fill phải gộp 1 command"
assert a1.brush().color().name() == "#123456" and b1.brush().color().name() == "#123456"
ca.undo_stack.undo()
assert a1.brush().style() == Qt.NoBrush and b1.brush().style() == Qt.NoBrush, \
    "undo 1 lần khôi phục cả 2"
print("OK: multi-select fill gộp 1 command")

print("=== STYLE P2 (OPACITY + SHADOW + FILL) OK ===")
