"""QC harness UI-ENH-02: nút Nền trên thanh trên → icon-only.

Dựng EditorWindow THẬT offscreen + ảnh; grab thanh công cụ trên + cận cảnh 2 icon;
verify toolButtonStyle=IconOnly (không chữ), tooltip đúng, chức năng cycle.
LƯU Ý: nút "Thuộc tính" đã rời toolbar ở UI-ENH-03 (dời vào tiêu đề panel);
phần kiểm nút đó nằm ở qc_uienh03_capture.py.
KHÔNG sửa app/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar
from PySide6.QtCore import QSize, Qt, QRect
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap

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


def shot_widget(wdg, name):
    for _ in range(4):
        app.processEvents()
    wdg.grab().save(os.path.join(OUT, name))
    LOG.append(name)


w = EditorWindow()
w.load_image(make_sample_image(1280, 800))
w.resize(1180, 760)
w.show()
for _ in range(5):
    app.processEvents()

bars = {tb.windowTitle(): tb for tb in w.findChildren(QToolBar)}
tool_tb, zoom_tb = bars.get("Công cụ"), bars.get("Zoom")

print("=" * 60)
print("UI-ENH-02: nút Nền icon-only")
print("=" * 60)

bg_act = w._bg_cycle_action
props_act = w._props_toggle_action
# Nút Nền đã dời sang góc phải thanh tác vụ trên cùng (REC-BG-TOPRIGHT).
capture_tb = bars.get("Chụp & Quay")
bg_btn = capture_tb.widgetForAction(bg_act)

print("\n[1/2] Style & text:")
for nm, act, btn in (("Nền", bg_act, bg_btn),):
    style = btn.toolButtonStyle().name if btn else "n/a"
    # icon-only → nút KHÔNG vẽ chữ (dù action.text() vẫn có để dùng trong menu ">>").
    print(f"    [{nm}] style={style} (mong ToolButtonIconOnly) "
          f"| action.text={act.text()!r} (giữ cho menu overflow) "
          f"| icon rỗng={act.icon().isNull()}")

print("\n[3] Tooltip:")
print(f"    Nền     tooltip={bg_act.toolTip()!r}")
print(f"    Thuộc tính (F4, nút nay ở tiêu đề panel) tooltip={props_act.toolTip()!r}")

# Grab thanh zoom (chứa 2 nút) — full bar.
shot_widget(zoom_tb, "uienh2_01_zoombar_icononly.png")
# Grab cả 2 hàng toolbar trên (crop từ window top ~94px).
top_pix = w.grab(QRect(0, 0, w.width(), 96))
top_pix.save(os.path.join(OUT, "uienh2_02_toptoolbars.png"))
LOG.append("uienh2_02_toptoolbars.png")

# --- Cận cảnh 2 icon: render icon lớn 96px trên nền toolbar (#33363B) ---
closeup = QPixmap(320, 150)
closeup.fill(QColor("#2B2D31"))
p = QPainter(closeup)
p.setFont(QFont(_fam or "Arial", 11))
for i, (nm, key) in enumerate((("Nen (bg_cycle)", "bg_cycle"),
                               ("Thu gon panel (chevron_right)", "chevron_right"))):
    x = 20 + i * 160
    ic = tool_icon(key, size=96)
    ic.paint(p, QRect(x + 24, 20, 96, 96))
    p.setPen(QColor("#E8E8E8"))
    p.drawText(QRect(x, 120, 150, 24), Qt.AlignHCenter, nm)
p.end()
closeup.save(os.path.join(OUT, "uienh2_03_icons_closeup.png"))
LOG.append("uienh2_03_icons_closeup.png")

# ---------- [4] Chức năng còn nguyên ----------
print("\n[4] Chức năng:")
seq = []
for _ in range(4):
    seq.append(w.canvas.backgroundBrush().color().name().upper())
    w._cycle_canvas_bg()
print(f"    Cycle nền: {seq} (mong #3A3D42→#FFFFFF→#000000→#3A3D42)")

vp0 = w.canvas.viewport().width()
props_act.trigger()
for _ in range(4):
    app.processEvents()
vp1 = w.canvas.viewport().width()
props_act.trigger()
for _ in range(4):
    app.processEvents()
vp2 = w.canvas.viewport().width()
print(f"    Toggle panel: vp {vp0}→(ẩn){vp1}→(hiện){vp2} "
      f"| ẩn rộng ra={vp1 > vp0} | hiện lại={vp2 == vp0}")

print("\nSAVED:")
for n in LOG:
    print("   ", n)
print("DIR:", OUT)
