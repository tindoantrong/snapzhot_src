"""QC harness FX1/FX2/FX3: dựng Editor THẬT offscreen, sample màu 4 toolbar,
vẽ callout (eyes hình bong bóng), assert logic exit-edit/giữ-con-trỏ/reselect.

KHÔNG sửa app/. Mô phỏng QMouseEvent vào viewport như người dùng.
Ảnh lưu .ai-workspace/screens/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import (
    QFont, QFontDatabase, QGuiApplication, QMouseEvent,
)
from PySide6.QtWidgets import QGraphicsTextItem

from app.editor.editor_window import EditorWindow
from app.editor.canvas import Tool, CalloutItem
from launch_editor_demo import make_sample_image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
_fam = None
for _f in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
    if os.path.exists(_f):
        fams = QFontDatabase.applicationFontFamilies(
            QFontDatabase.addApplicationFont(_f))
        if fams and _fam is None:
            _fam = fams[0]
if _fam:
    app.setFont(QFont(_fam, 10))
IMG = make_sample_image(1280, 800)


def new_win():
    w = EditorWindow()
    w.load_image(IMG)
    w.resize(1100, 720)
    w.show()
    for _ in range(4):
        app.processEvents()
    return w


def vp_pt(w, sx, sy):
    return w.canvas.mapFromScene(QPointF(sx, sy))


def _send(w, etype, vpos, button, buttons):
    g = w.canvas.viewport().mapToGlobal(vpos)
    ev = QMouseEvent(etype, QPointF(vpos), QPointF(g), button, buttons, Qt.NoModifier)
    app.sendEvent(w.canvas.viewport(), ev)


def drag(w, s0, s1, steps=10):
    p0, p1 = vp_pt(w, *s0), vp_pt(w, *s1)
    _send(w, QEvent.MouseButtonPress, p0, Qt.LeftButton, Qt.LeftButton)
    for i in range(1, steps + 1):
        t = i / steps
        p = QPoint(round(p0.x() + (p1.x() - p0.x()) * t),
                   round(p0.y() + (p1.y() - p0.y()) * t))
        _send(w, QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton)
    _send(w, QEvent.MouseButtonRelease, p1, Qt.LeftButton, Qt.NoButton)
    app.processEvents()


def click(w, s):
    p = vp_pt(w, *s)
    _send(w, QEvent.MouseButtonPress, p, Qt.LeftButton, Qt.LeftButton)
    _send(w, QEvent.MouseButtonRelease, p, Qt.LeftButton, Qt.NoButton)
    app.processEvents()


def shot(w, name):
    app.processEvents()
    w.grab().save(os.path.join(OUT, name))
    print("SAVED", name)


# ============ FX1: 4 toolbar nền #33363B ============
w = new_win()
img = w.grab().toImage()
print("--- FX1 toolbar backgrounds ---")
for tb in w.findChildren(QToolBar):
    name = tb.objectName()
    g = tb.geometry()
    cy = g.center().y()
    # sample vài x từ phải qua (vùng trống), lấy màu khác text
    samples = [img.pixelColor(x, cy).name()
               for x in (g.right() - 8, g.right() - 30, g.center().x())]
    print(f"  {name:10s} geom={g.x(),g.y(),g.width(),g.height()} samples={samples}")
shot(w, "fx_01_editor_toolbars.png")

# ============ FX3: hình callout (bong bóng liền mạch) ============
w2 = new_win()
w2._select_tool(Tool.CALLOUT)
app.processEvents()
drag(w2, (380, 280), (780, 520))   # kéo lớn → tạo callout + vào edit
app.processEvents()
shot(w2, "fx_02_callout_shape.png")

# zoom-in để soi viền/đuôi rõ hơn
w2.canvas.zoom_in(); w2.canvas.zoom_in()
app.processEvents()
shot(w2, "fx_03_callout_zoom.png")

# ============ FX2: exit-edit / giữ con trỏ / reselect ============
print("--- FX2 logic ---")
co = next((it for it in w2.canvas._scene.items()
           if isinstance(it, CalloutItem)), None)
fi0 = w2.canvas._scene.focusItem()
print("  sau khi tao: focusItem la CalloutItem?",
      isinstance(fi0, CalloutItem),
      "| interaction!=No?",
      fi0.textInteractionFlags() != Qt.NoTextInteraction if fi0 else None)

# reset về zoom thường để toạ độ scene khớp
w2.canvas.zoom_fit(); app.processEvents()
br = co.sceneBoundingRect()
inside = (br.center().x(), br.center().y())
empty = (120, 120)  # góc trên-trái, xa callout

# (a) click TRONG callout đang soạn → vẫn giữ con trỏ (không clearFocus)
co.enter_edit(); app.processEvents()
click(w2, inside)
fi_in = w2.canvas._scene.focusItem()
print("  click TRONG callout: van giu focus (CalloutItem)?",
      isinstance(fi_in, CalloutItem))

# (b) click VÙNG TRỐNG → thoát edit (focusItem mất TextEditorInteraction/None)
co.enter_edit(); app.processEvents()
click(w2, empty)
fi_out = w2.canvas._scene.focusItem()
print("  click VUNG TRONG: thoat edit (focusItem None)?", fi_out is None)
print("    interaction cua callout sau thoat:",
      co.textInteractionFlags(), "(NoTextInteraction =", Qt.NoTextInteraction, ")")

# (c) reselect: click vào callout (tool SELECT) → chọn + 8 handle
w2._select_tool(Tool.SELECT); app.processEvents()
click(w2, inside)
sel = [it for it in w2.canvas._scene.selectedItems()]
vis_handles = [h for h in w2.canvas._handles if h.isVisible()]
print("  reselect 1-click: callout selected?", co.isSelected(),
      "| so handle hien:", len(vis_handles),
      "| resize_target is callout?", w2.canvas._resize_target is co)
shot(w2, "fx_04_callout_reselected.png")

w.close(); w2.close(); app.processEvents()
print("DIR:", OUT)
