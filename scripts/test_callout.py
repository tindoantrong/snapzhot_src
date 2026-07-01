"""Test C1: công cụ Callout / Speech bubble — lõi item + style + undo/redo.

Trọng tâm: CalloutItem dựng đúng (bbox chứa cả đuôi), _add_callout tạo item qua
undo stack, apply_style_to_selection đổi fill/màu viền/độ dày/cỡ chữ + undo/redo,
item_style_props trả đủ 4 nhóm, và render scene ra ảnh hợp lệ (có nét vẽ).
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGraphicsTextItem
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFocusEvent, QFont, QImage, QMouseEvent, QTransform

app = QApplication([])

from app.editor.canvas import (
    Canvas, Tool, CalloutItem, item_style_props, HANDLE_BR,
)
from app.editor.commands import ResizeItemCommand

img = QImage(400, 300, QImage.Format_RGB32)
img.fill(QColor("#ffffff"))


def callouts(c):
    return [it for it in c._scene.items() if isinstance(it, CalloutItem)]


def make_canvas() -> Canvas:
    c = Canvas()
    c.load_image(img)
    return c


# ---- boundingRect chứa cả vùng đuôi + lề pen (cao/rộng hơn bbox text thuần) ----
# boundingRect nới: trên/trái/phải thêm m = width/2 + 1 (phủ nét viền tràn ngoài,
# tránh vệt sọc khi di chuyển), dưới thêm _TAIL_H + m (đuôi + lề pen).
co = CalloutItem("Chú thích", QColor("#FFFFFF"), QColor("#FF3B30"), 6, 24)
m = co._width / 2.0 + 1.0
plain = QGraphicsTextItem("Chú thích")
plain.document().setDocumentMargin(10)
plain.setFont(QFont("", 24))
extra = co.boundingRect().height() - plain.boundingRect().height()
assert abs(extra - (CalloutItem._TAIL_H + 2 * m)) < 0.5, \
    f"bbox callout phải cao hơn text ~{CalloutItem._TAIL_H + 2 * m}px (đuôi + lề pen), got {extra}"
assert co.boundingRect().width() >= plain.boundingRect().width() - 0.5, \
    "bề rộng callout không nhỏ hơn text"
print("OK: boundingRect mở rộng chứa đuôi + lề pen viền")

# ---- đổi _width qua set_border → boundingRect nới rộng thêm theo width mới ----
h_before = co.boundingRect().height()
co.set_border(QColor("#FF3B30"), width=20)
h_after = co.boundingRect().height()
assert h_after > h_before, "tăng width phải nới boundingRect (prepareGeometryChange)"
print("OK: set_border đổi width → boundingRect cập nhật theo")

# ---- _add_callout tạo item qua undo stack + undo/redo ----
c = make_canvas()
c.state.tool = Tool.CALLOUT
c.state.color = QColor("#FF3B30")
c.state.width = 6
c.state.font_size = 24
n0 = c.undo_stack.count()
c._add_callout(QRectF(100, 80, 180, 100))
cs = callouts(c)
assert len(cs) == 1, f"phải có 1 callout, got {len(cs)}"
assert c.undo_stack.count() == n0 + 1, "thêm callout phải +1 command"
item = cs[0]
assert item._border.name() == "#ff3b30", f"viền theo state.color, got {item._border.name()}"
assert item._fill.name() == "#ffffff", f"nền mặc định trắng, got {item._fill.name()}"
assert item._width == 6, "độ dày viền theo state.width"
assert item.defaultTextColor().name() == "#ff3b30", "chữ cùng màu viền"
print("OK: _add_callout tạo CalloutItem theo state")

c.undo_stack.undo()
assert len(callouts(c)) == 0, "undo phải gỡ callout"
c.undo_stack.redo()
assert len(callouts(c)) == 1, "redo phải thêm lại callout"
print("OK: undo/redo callout")

# ---- đổi FILL (màu nền bong bóng) + undo/redo ----
item = callouts(c)[0]
c._scene.clearSelection()
item.setSelected(True)
assert c.apply_style_to_selection(fill=QColor("#FFF59D")) is True, "đổi fill phải hiệu lực"
assert item._fill.name() == "#fff59d", f"fill phải đổi, got {item._fill.name()}"
c.undo_stack.undo()
assert item._fill.name() == "#ffffff", "undo khôi phục fill cũ"
c.undo_stack.redo()
assert item._fill.name() == "#fff59d", "redo về fill mới"
print("OK: đổi fill + undo/redo")

# ---- đổi MÀU VIỀN (kéo theo màu chữ) + undo/redo ----
assert c.apply_style_to_selection(color=QColor("#1E90FF")) is True
assert item._border.name() == "#1e90ff", "viền phải đổi"
assert item.defaultTextColor().name() == "#1e90ff", "chữ phải đổi theo viền"
c.undo_stack.undo()
assert item._border.name() == "#ff3b30" and item.defaultTextColor().name() == "#ff3b30", \
    "undo khôi phục viền + chữ"
c.undo_stack.redo()
assert item._border.name() == "#1e90ff", "redo về viền mới"
print("OK: đổi màu viền + chữ + undo/redo")

# ---- đổi ĐỘ DÀY viền + undo/redo ----
assert c.apply_style_to_selection(width=12) is True
assert item._width == 12, "độ dày viền phải = 12"
c.undo_stack.undo()
assert item._width == 6, "undo khôi phục độ dày"
c.undo_stack.redo()
assert item._width == 12, "redo về độ dày mới"
print("OK: đổi độ dày viền + undo/redo")

# ---- đổi CỠ CHỮ + undo/redo ----
assert c.apply_style_to_selection(font_size=40) is True
assert item.font().pointSize() == 40, "cỡ chữ phải = 40"
c.undo_stack.undo()
assert item.font().pointSize() == 24, "undo khôi phục cỡ chữ"
c.undo_stack.redo()
assert item.font().pointSize() == 40, "redo về cỡ chữ mới"
print("OK: đổi cỡ chữ + undo/redo")

# ---- item_style_props: đủ 4 nhóm color/width/fill/font (+opacity/shadow) ----
props = item_style_props(item)
for g in ("color", "width", "fill", "font", "opacity", "shadow"):
    assert g in props["groups"], f"callout thiếu nhóm {g}: {props['groups']}"
assert props["fill_enabled"] is True, "callout fill_enabled phải True"
assert props["fill_color"] is not None, "callout phải có fill_color"
assert props["font_size"] == 40, "font_size phản ánh giá trị hiện tại"
print("OK: item_style_props callout = color+width+fill+font (+opacity/shadow)")

# ---- render scene ra ảnh hợp lệ + có nét vẽ (không phải toàn trắng) ----
c2 = make_canvas()
c2.state.color = QColor("#FF3B30")
c2.state.width = 6
c2.state.font_size = 24
c2.state.tool = Tool.CALLOUT
c2._add_callout(QRectF(120, 90, 180, 100))
out = c2.render_to_image()
assert not out.isNull(), "render với callout phải hợp lệ"
white = QColor("#ffffff").rgb()
non_white = any(
    out.pixel(x, y) != white
    for y in range(0, out.height(), 5)
    for x in range(0, out.width(), 5)
)
assert non_white, "ảnh phải có nét callout (không toàn trắng)"
print("OK: render_to_image có nét callout")

# ---- CR1: vòng đời edit (chọn/move/resize được; double-click soạn; thoát) ----
c3 = make_canvas()
c3.state.tool = Tool.CALLOUT
c3.state.color = QColor("#FF3B30")
c3.state.width = 6
c3.state.font_size = 24
c3._add_callout(QRectF(80, 60, 180, 100))
it = callouts(c3)[0]
# Vừa tạo → đang soạn chữ (gõ liền được).
assert it.textInteractionFlags() & Qt.TextEditorInteraction, \
    "callout vừa tạo phải ở chế độ soạn chữ"
print("OK: _add_callout vào soạn chữ ngay")

# Thoát soạn (focus-out) → NoTextInteraction → chọn/move/resize được.
# Headless không cấp focus thật nên gửi thẳng sự kiện FocusOut vào item.
it.focusOutEvent(QFocusEvent(QEvent.FocusOut))
assert it.textInteractionFlags() == Qt.NoTextInteraction, \
    "rời focus phải thoát soạn chữ (NoTextInteraction)"
print("OK: focus-out thoát soạn chữ")

# Click-đơn chọn → _update_handles hiện 8 handle, target đúng item.
c3._scene.clearSelection()
it.setSelected(True)
c3._update_handles()
assert c3._resize_target is it, "chọn callout phải đặt _resize_target = item"
assert len(c3._handles) == 8 and all(h.isVisible() for h in c3._handles), \
    "chọn callout phải hiện 8 resize handle"
print("OK: chọn callout hiện 8 handle (resize được)")

# Double-click bật lại soạn chữ (qua enter_edit).
it.enter_edit()
assert it.textInteractionFlags() & Qt.TextEditorInteraction, \
    "enter_edit phải bật lại chế độ soạn chữ"
print("OK: enter_edit (double-click) bật lại soạn chữ")

# ---- CR2: kéo-chọn-cỡ → scale-fit vào rect đã kéo ----
c4 = make_canvas()
c4.state.tool = Tool.CALLOUT
c4.state.color = QColor("#1E90FF")
c4.state.width = 4
c4.state.font_size = 20
drag = QRectF(50, 40, 260, 150)   # rect lớn → scale-fit
c4._add_callout(drag)
big_it = callouts(c4)[0]
sbr = big_it.sceneBoundingRect()
assert abs(sbr.width() - drag.width()) < 1.0 and abs(sbr.height() - drag.height()) < 1.0, \
    f"callout phải khít rect đã kéo, got {sbr} vs {drag}"
assert abs(sbr.x() - drag.x()) < 1.0 and abs(sbr.y() - drag.y()) < 1.0, \
    "vị trí callout phải trùng góc rect kéo"
print("OK: kéo lớn → callout scale-fit khít rect")

# Undo gỡ callout đã scale (transform không phá undo).
c4.undo_stack.undo()
assert len(callouts(c4)) == 0, "undo phải gỡ callout scale-fit"
c4.undo_stack.redo()
assert len(callouts(c4)) == 1, "redo phải thêm lại callout scale-fit"
print("OK: undo/redo callout scale-fit")

# ---- CR2b: GATE — Callout CHỈ vẽ khi kéo đủ lớn (giống Rect). Click đơn /
# kéo nhỏ hơn _CALLOUT_MIN_DRAG → KHÔNG tạo bong bóng (để click dùng chọn object).
c5 = Canvas()
c5.load_image(img)
c5.resize(500, 400)          # viewport thật để view-transform khả nghịch
app.processEvents()
c5.state.tool = Tool.CALLOUT
c5.state.color = QColor("#FF3B30")
c5.state.width = 6
c5.state.font_size = 24


def _mouse(kind, scene_pt):
    """Dựng QMouseEvent ở viewport-pos tương ứng scene_pt."""
    vp_pt = c5.mapFromScene(scene_pt)
    g = c5.viewport().mapToGlobal(vp_pt)
    return QMouseEvent(kind, QPointF(vp_pt), QPointF(g),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


def sim_drag(p0, p1):
    """Mô phỏng press→move→release qua pipeline vẽ của Canvas."""
    c5.mousePressEvent(_mouse(QEvent.MouseButtonPress, p0))
    c5.mouseMoveEvent(_mouse(QEvent.MouseMove, p1))
    c5.mouseReleaseEvent(_mouse(QEvent.MouseButtonRelease, p1))


# Click đơn (start ≈ cur) → không tạo callout.
n_click = len(callouts(c5))
sim_drag(QPointF(120, 120), QPointF(121, 120))
assert len(callouts(c5)) == n_click, \
    "click đơn KHÔNG được tạo callout (dành click cho chọn object)"
print("OK: click đơn → không tạo callout")

# Kéo nhỏ hơn ngưỡng → vẫn không tạo.
sim_drag(QPointF(120, 120), QPointF(120 + c5._CALLOUT_MIN_DRAG - 2,
                                    120 + c5._CALLOUT_MIN_DRAG - 2))
assert len(callouts(c5)) == n_click, \
    "kéo nhỏ hơn _CALLOUT_MIN_DRAG KHÔNG được tạo callout"
print("OK: kéo nhỏ hơn ngưỡng → không tạo callout")

# Kéo đủ lớn → tạo đúng 1 callout.
sim_drag(QPointF(60, 60), QPointF(300, 220))
assert len(callouts(c5)) == n_click + 1, \
    f"kéo lớn phải tạo đúng 1 callout, got {len(callouts(c5)) - n_click}"
print("OK: kéo đủ lớn → tạo đúng 1 callout")

# ---- CR3: resize qua handle (kéo handle góc) → scale cả bong bóng lẫn chữ ----
c6 = Canvas()
c6.load_image(img)
# Viewport thật để view-transform khả nghịch (giống test_move_resize).
c6.resize(500, 400)
app.processEvents()
c6.state.tool = Tool.CALLOUT
c6.state.color = QColor("#FF3B30")
c6.state.width = 6
c6.state.font_size = 24
c6._add_callout(QRectF(120, 90, 180, 100))
ci = callouts(c6)[0]
ci.focusOutEvent(QFocusEvent(QEvent.FocusOut))   # thoát soạn để chọn được

c6.state.tool = Tool.SELECT
ci.setSelected(True)
c6._update_handles()
assert c6._resize_target is ci, "phải có target khi chọn callout"
assert len(c6._handles) == 8 and all(h.isVisible() for h in c6._handles), \
    "chọn callout phải hiện 8 handle"

before = QTransform(ci.transform())
O = ci.sceneBoundingRect()
n_before = c6.undo_stack.count()
# Kéo handle góc dưới-phải để phóng khung to ra.
c6._begin_resize(HANDLE_BR)
c6._resize_to(QPointF(O.left() + O.width() * 1.6, O.top() + O.height() * 1.6))
c6._commit_resize()

after = ci.sceneBoundingRect()
assert ci.transform() != before, "kéo handle phải đổi transform (đã scale)"
assert after.width() > O.width() and after.height() > O.height(), \
    f"sceneBoundingRect phải to hơn: {O} -> {after}"
assert c6.undo_stack.count() == n_before + 1, "resize phải đẩy 1 ResizeItemCommand"
# Chứng minh "chữ co theo": transform scale toàn item (m11/m22 > 1 → glyph phóng to),
# không phải text reflow.
t = ci.transform()
assert t.m11() > 1.0 or t.m22() > 1.0, \
    f"phải scale (m11/m22 > 1) để chữ phóng theo, got m11={t.m11()} m22={t.m22()}"
print("OK: kéo handle resize callout (chữ co theo qua transform scale)")

c6.undo_stack.undo()
assert ci.transform() == before, "undo resize phải khôi phục transform"
c6.undo_stack.redo()
assert ci.transform() != before, "redo resize phải áp lại transform mới"
print("OK: undo/redo resize qua handle")

print("=== CALLOUT OK ===")
