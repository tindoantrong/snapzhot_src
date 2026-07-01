"""QC harness: dựng Editor THẬT (offscreen) + thao tác bằng mô phỏng chuột,
GRAB ảnh PNG thật của cửa sổ để eyes-test bằng mắt (đọc lại ảnh).

KHÔNG sửa app/. Chỉ dùng public API + mô phỏng QMouseEvent vào viewport như
người dùng. Ảnh lưu vào .ai-workspace/screens/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QMouseEvent

from app.editor.editor_window import EditorWindow
from app.editor.canvas import Tool
from launch_editor_demo import make_sample_image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])

# Offscreen QPA không nạp font hệ thống → chữ thành ô vuông (tofu). Nạp font
# Windows để chụp được chữ thật (artifact chụp, không phải lỗi app).
_first_fam = None
for _f in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
    if os.path.exists(_f):
        fams = QFontDatabase.applicationFontFamilies(
            QFontDatabase.addApplicationFont(_f))
        if fams and _first_fam is None:
            _first_fam = fams[0]
if _first_fam:
    app.setFont(QFont(_first_fam, 10))
IMG = make_sample_image(1280, 800)
LOG = []


def new_win() -> EditorWindow:
    w = EditorWindow()
    w.load_image(IMG)
    w.resize(1100, 720)
    w.show()
    for _ in range(3):
        app.processEvents()
    return w


def vp_pt(w: EditorWindow, scene_x, scene_y) -> QPoint:
    return w.canvas.mapFromScene(QPointF(scene_x, scene_y))


def _send(w, etype, vpos: QPoint, button, buttons):
    g = w.canvas.viewport().mapToGlobal(vpos)
    ev = QMouseEvent(etype, QPointF(vpos), QPointF(g),
                     button, buttons, Qt.NoModifier)
    app.sendEvent(w.canvas.viewport(), ev)


def drag(w, s0, s1, steps=8):
    p0, p1 = vp_pt(w, *s0), vp_pt(w, *s1)
    _send(w, QEvent.MouseButtonPress, p0, Qt.LeftButton, Qt.LeftButton)
    for i in range(1, steps + 1):
        t = i / steps
        p = QPoint(round(p0.x() + (p1.x() - p0.x()) * t),
                   round(p0.y() + (p1.y() - p0.y()) * t))
        _send(w, QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton)
    _send(w, QEvent.MouseButtonRelease, p1, Qt.LeftButton, Qt.NoButton)
    app.processEvents()


def press_move(w, s0, s1, steps=8):
    """Press + move nhưng KHÔNG release (để chụp preview đang kéo)."""
    p0, p1 = vp_pt(w, *s0), vp_pt(w, *s1)
    _send(w, QEvent.MouseButtonPress, p0, Qt.LeftButton, Qt.LeftButton)
    for i in range(1, steps + 1):
        t = i / steps
        p = QPoint(round(p0.x() + (p1.x() - p0.x()) * t),
                   round(p0.y() + (p1.y() - p0.y()) * t))
        _send(w, QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton)
    app.processEvents()
    return p1


def click(w, s):
    p = vp_pt(w, *s)
    _send(w, QEvent.MouseButtonPress, p, Qt.LeftButton, Qt.LeftButton)
    _send(w, QEvent.MouseButtonRelease, p, Qt.LeftButton, Qt.NoButton)
    app.processEvents()


def shot(w, name):
    app.processEvents()
    path = os.path.join(OUT, name)
    w.grab().save(path)
    LOG.append(name)


def tool(w, t):
    w._select_tool(t)
    app.processEvents()


# ---- 1) Toolbar + tool đang chọn (checked) ----
w = new_win()
tool(w, Tool.ARROW)
shot(w, "01_toolbar_arrow_selected.png")

# ---- 2) Vẽ nhóm hình: arrow / rect / ellipse / pen ----
tool(w, Tool.ARROW);   drag(w, (180, 470), (430, 600))
tool(w, Tool.RECT);    drag(w, (520, 430), (760, 600))
tool(w, Tool.ELLIPSE); drag(w, (840, 430), (1080, 600))
tool(w, Tool.PEN)
pts = [(180, 680), (240, 640), (300, 700), (360, 650), (420, 700)]
# vẽ pen bằng 1 chuỗi move
p0 = vp_pt(w, *pts[0])
_send(w, QEvent.MouseButtonPress, p0, Qt.LeftButton, Qt.LeftButton)
for s in pts[1:]:
    _send(w, QEvent.MouseMove, vp_pt(w, *s), Qt.NoButton, Qt.LeftButton)
_send(w, QEvent.MouseButtonRelease, vp_pt(w, *pts[-1]), Qt.LeftButton, Qt.NoButton)
app.processEvents()
shot(w, "02_shapes_arrow_rect_ellipse_pen.png")

# ---- 3) Vẽ annotation: text / callout / step / stamp / highlight ----
w2 = new_win()
tool(w2, Tool.TEXT);   click(w2, (160, 200))   # vào soạn chữ
tool(w2, Tool.STEP);   click(w2, (520, 200)); click(w2, (600, 200)); click(w2, (680, 200))
tool(w2, Tool.STAMP);  click(w2, (520, 320));
w2.canvas.state.stamp_name = "heart"; click(w2, (600, 320))
w2.canvas.state.stamp_name = "check"; click(w2, (680, 320))
tool(w2, Tool.HIGHLIGHT); drag(w2, (820, 440), (1080, 520))
tool(w2, Tool.CALLOUT);   drag(w2, (160, 560), (430, 700))
shot(w2, "03_annotations_text_step_stamp_highlight_callout.png")

# ---- 4) Spotlight + Blur ----
w3 = new_win()
tool(w3, Tool.SPOTLIGHT); drag(w3, (700, 200), (1050, 420))
shot(w3, "04_spotlight.png")
w4 = new_win()
tool(w4, Tool.BLUR); drag(w4, (140, 160), (470, 360))
shot(w4, "05_blur.png")

# ---- 5) Chọn object → 8 handle + panel style của rect ----
w5 = new_win()
tool(w5, Tool.RECT); drag(w5, (400, 300), (760, 560))
rect_item = w5.canvas.selected_annotation() or [
    it for it in w5.canvas._scene.items()
    if it is not w5.canvas._bg_item][0]
tool(w5, Tool.SELECT)
w5.canvas._scene.clearSelection()
rect_item.setSelected(True)
app.processEvents()
shot(w5, "06_select_handles_panel_rect.png")

# ---- 6) Express Style áp lên rect (preset Hộp vàng = fill) ----
from app.editor.editor_window import QUICK_STYLES
w5._apply_quick_style(QUICK_STYLES[2])   # "Hộp vàng" fill
app.processEvents()
shot(w5, "07_express_style_yellow_fill.png")

# ---- 7) Opacity + Shadow áp lên object ----
w5.canvas.apply_style_to_selection(shadow=True)
w5.canvas.apply_style_to_selection(opacity=0.5)
app.processEvents()
shot(w5, "08_shadow_opacity.png")

# ---- 8) Panel của ARROW (nhóm color+width, không fill/font) ----
w6 = new_win()
tool(w6, Tool.ARROW); drag(w6, (200, 250), (600, 450))
arrow_item = [it for it in w6.canvas._scene.items()
              if it is not w6.canvas._bg_item][0]
tool(w6, Tool.SELECT); w6.canvas._scene.clearSelection()
arrow_item.setSelected(True); app.processEvents()
shot(w6, "09_panel_arrow.png")

# ---- 9) Arrow preview ĐANG kéo (phải là mũi tên thật, không phải đoạn thẳng) ----
w7 = new_win()
tool(w7, Tool.ARROW)
press_move(w7, (200, 300), (760, 560))
shot(w7, "10_arrow_preview_dragging.png")
_send(w7, QEvent.MouseButtonRelease, vp_pt(w7, 760, 560),
      Qt.LeftButton, Qt.NoButton)
app.processEvents()

# ---- 10) Zoom in & fit ----
w8 = new_win()
w8.canvas.zoom_in(); w8.canvas.zoom_in(); app.processEvents()
shot(w8, "11_zoom_in.png")
w8.canvas.zoom_fit(); app.processEvents()
shot(w8, "12_zoom_fit.png")

# ---- 11) Overflow ">>" khi cửa sổ hẹp ----
w9 = new_win()
w9.resize(520, 700)
for _ in range(4):
    app.processEvents()
shot(w9, "13_narrow_overflow.png")

# ---- 12) Empty state (chưa có ảnh) ----
w10 = EditorWindow()
w10.resize(1100, 720)
w10.show()
for _ in range(3):
    app.processEvents()
shot(w10, "14_empty_state.png")

# ---- 13) Toast (gọi API hiển thị toast nếu có) ----
for cand in ("_show_toast", "show_toast", "_toast"):
    fn = getattr(w8, cand, None)
    if callable(fn):
        try:
            fn("Đã lưu vào thư viện")
            app.processEvents()
            shot(w8, "15_toast.png")
        except Exception as e:
            LOG.append(f"toast-fail({cand}):{e}")
        break

print("SAVED:")
for n in LOG:
    print("  ", n)
print("DIR:", OUT)
