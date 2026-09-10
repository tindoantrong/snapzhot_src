"""QC harness BG-TOPRIGHT: nút đổi nền vùng ảnh — icon ô caro, góc phải hàng trên.

Dựng EditorWindow THẬT offscreen; kiểm:
  - Nút nằm trên thanh tác vụ trên cùng ("Chụp & Quay"), sát mép PHẢI, cùng
    hàng (cùng tâm y) với Về thư viện / Chụp vùng / Chụp toàn màn hình / Quay video.
  - KHÔNG còn trên thanh Zoom → không rơi vào overflow ">>" khi cửa sổ hẹp.
  - Icon là ô caro (2x2 xen kẽ), KHÔNG phải mặt trời/mặt trăng.
  - Tooltip "Đổi nền vùng ảnh"; bấm vẫn cycle Tối → Trắng → Đen.
  - Màu icon tương phản với nền thanh công cụ ở cả trạng thái thường lẫn hover.
KHÔNG sửa app/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase

from app.editor.editor_window import EditorWindow
from app.editor.tool_icons import tool_icon
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

LOG = []


def pump(n=6):
    for _ in range(n):
        app.processEvents()


def shot_rect(rect, name):
    pump()
    w.grab(rect).save(os.path.join(OUT, name))
    LOG.append(name)


def _lum(c: QColor) -> float:
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def contrast(fg: QColor, bg: QColor) -> float:
    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


w = EditorWindow()
w.load_image(make_sample_image(1280, 800))
w.resize(1280, 820)
w.show()
pump()

print("=" * 66)
print("BG-TOPRIGHT: nút đổi nền vùng ảnh (ô caro) ở góc phải hàng trên cùng")
print("=" * 66)

bars = {tb.objectName(): tb for tb in w.findChildren(QToolBar)}
cap_tb, zoom_tb = bars["captureBar"], bars["zoomBar"]
btn = cap_tb.widgetForAction(w._bg_cycle_action)

# ---------- [1] Vị trí ----------
print("\n[1] Vị trí:")
print(f"    trên thanh tác vụ trên cùng = {btn is not None} "
      f"| KHÔNG còn trên thanh Zoom = "
      f"{zoom_tb.widgetForAction(w._bg_cycle_action) is None}")
right_gap = w.width() - btn.mapTo(w, btn.rect().topRight()).x()
print(f"    cách mép phải cửa sổ {right_gap}px")
ys = {a.text(): cap_tb.widgetForAction(a).mapTo(w, cap_tb.widgetForAction(a).rect().center()).y()
      for a in cap_tb.actions()
      if not a.isSeparator() and cap_tb.widgetForAction(a) is not None
      and cap_tb.widgetForAction(a).width() > 10}
print(f"    tâm y các nút cùng hàng: {ys}")
print(f"    ngang hàng hết = {len(set(ys.values())) == 1}")

# ---------- [2] Luôn thấy dù cửa sổ hẹp ----------
print("\n[2] Không rơi vào overflow khi cửa sổ hẹp:")
for width in (1000, 1100, 1280, 1600):
    w.resize(width, 820)
    pump()
    b = cap_tb.widgetForAction(w._bg_cycle_action)
    print(f"    cửa sổ {width}px → nút hiện = {b.isVisible()}")
w.resize(1280, 820)
pump()

# ---------- [3] Tooltip + chức năng ----------
print("\n[3] Tooltip & chức năng:")
print(f"    tooltip={w._bg_cycle_action.toolTip()!r}")
seq = [w.canvas.backgroundBrush().color().name().upper()]
for _ in range(3):
    w._cycle_canvas_bg()
    seq.append(w.canvas.backgroundBrush().color().name().upper())
print(f"    cycle nền: {seq} (mong Tối → Trắng → Đen → Tối)")
print(f"    tooltip sau khi bấm vẫn = {w._bg_cycle_action.toolTip()!r}")

# ---------- [4] Tương phản icon ----------
print("\n[4] Màu icon so với nền thanh công cụ:")
icon_fg = QColor("#E8E8E8")   # màu mặc định của tool_icon()
for bg_hex, nhan in (("#33363B", "thanh công cụ"), ("#3E4248", "hover"),
                     ("#2F3338", "pressed")):
    print(f"    trên nền {bg_hex} ({nhan}): {contrast(icon_fg, QColor(bg_hex)):.2f}:1")

# ---------- [5] Ảnh ----------
g = cap_tb.geometry()
shot_rect(QRect(0, g.y(), w.width(), g.height()), "bgtr_01_toprow.png")
shot_rect(QRect(w.width() - 200, g.y(), 200, g.height()), "bgtr_02_closeup.png")

from PySide6.QtGui import QPainter, QPixmap
prev = QPixmap(420, 150)
prev.fill(QColor("#33363B"))
p = QPainter(prev)
p.setFont(QFont(_fam or "Arial", 10))
for i, sz in enumerate((16, 26, 48, 96)):
    x = 20 + i * 100
    tool_icon("bg_cycle", size=sz).paint(p, QRect(x, 20 + (96 - sz) // 2, sz, sz))
    p.setPen(QColor("#E8E8E8"))
    p.drawText(QRect(x, 124, 96, 18), Qt.AlignLeft, f"{sz}px")
p.end()
prev.save(os.path.join(OUT, "bgtr_03_icon_sizes.png"))
LOG.append("bgtr_03_icon_sizes.png")

print("\nSAVED:")
for n in LOG:
    print("   ", n)
print("DIR:", OUT)
