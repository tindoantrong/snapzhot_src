"""QC harness UI-ENH-03: nút thu gọn dời vào tiêu đề panel Thuộc tính.

Dựng EditorWindow THẬT offscreen + ảnh; kiểm:
  - Toolbar KHÔNG còn nút "Thuộc tính"; nút "Nền" vẫn ở cạnh nhóm zoom và có
    separator ngăn nhóm ngay trước nó.
  - Panel mở: tiêu đề "Thuộc tính" bên trái, nút chevron › bên phải.
  - Panel thu gọn: panel ẩn, dock CÒN LẠI một tab hẹp ở mép phải, chevron ‹.
  - F4 và tooltip vẫn hoạt động; bung ra giữ nguyên bề rộng cũ.
KHÔNG sửa app/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QKeySequence, QPainter, QPixmap

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


def pump(n=5):
    for _ in range(n):
        app.processEvents()


def shot_window(name):
    pump()
    w.grab().save(os.path.join(OUT, name))
    LOG.append(name)


def shot_rect(rect, name):
    pump()
    w.grab(rect).save(os.path.join(OUT, name))
    LOG.append(name)


w = EditorWindow()
w.load_image(make_sample_image(1280, 800))
w.resize(1180, 760)
w.show()
pump()

print("=" * 62)
print("UI-ENH-03: nút thu gọn nằm trong tiêu đề panel Thuộc tính")
print("=" * 62)

# ---------- [1] Toolbar: bớt một nút, Nền vẫn cạnh zoom ----------
bars = {tb.windowTitle(): tb for tb in w.findChildren(QToolBar)}
zoom_tb = bars["Zoom"]
acts = zoom_tb.actions()
names = [("|SEP|" if a.isSeparator() else (a.text() or "<widget>")) for a in acts]
print("\n[1] Thanh zoom:")
print(f"    Thứ tự action: {names}")
print(f"    KHÔNG còn nút 'Thuộc tính' trên toolbar = "
      f"{zoom_tb.widgetForAction(w._props_toggle_action) is None}")
# Nền đã rời thanh Zoom, sang mép phải hàng tác vụ trên cùng.
cap_tb = bars["Chụp & Quay"]
bg_btn = cap_tb.widgetForAction(w._bg_cycle_action)
print(f"    Nền KHÔNG còn trên thanh zoom = "
      f"{zoom_tb.widgetForAction(w._bg_cycle_action) is None}")
print(f"    Nền nằm ở hàng trên cùng, sát mép phải: x={bg_btn.mapTo(w, bg_btn.rect().topRight()).x()} "
      f"/ bề ngang {w.width()}")
print(f"    Nền vẫn icon-only = {bg_btn.toolButtonStyle().name}")

shot_rect(QRect(0, 0, w.width(), 96), "uienh3_01_toolbar_no_props_btn.png")

# ---------- [2] Panel mở: tiêu đề trái + chevron phải ----------
print("\n[2] Panel MỞ:")
print(f"    expanded={w._props_expanded} | nhãn tiêu đề="
      f"{w._props_title_label.text()!r} hiện={w._props_title_label.isVisible()}")
print(f"    tooltip nút thu gọn={w._props_collapse_btn.toolTip()!r}")
print(f"    dock width={w.props_dock.width()} | canvas vp={w.canvas.viewport().width()}")
lbl_x = w._props_title_label.mapTo(w.props_dock, w._props_title_label.rect().center()).x()
btn_x = w._props_collapse_btn.mapTo(w.props_dock, w._props_collapse_btn.rect().center()).x()
print(f"    nhãn ở TRÁI nút (x {lbl_x} < {btn_x}) = {lbl_x < btn_x}")

dock_geo = w.props_dock.geometry()
shot_rect(dock_geo, "uienh3_02_panel_open_titlebar.png")
shot_window("uienh3_03_window_open.png")

w_open = w.props_dock.width()
vp_open = w.canvas.viewport().width()

# ---------- [3] Bấm nút thu gọn ----------
w._props_collapse_btn.click()
pump()
print("\n[3] Panel THU GỌN (bấm chevron ›):")
print(f"    expanded={w._props_expanded} | panel ẩn={not w._props_panel.isVisible()}")
print(f"    dock CÒN hiện (tab ở mép phải) = {w.props_dock.isVisible()} "
      f"| dock width={w.props_dock.width()}px")
print(f"    nút mở lại vẫn thấy = {w._props_collapse_btn.isVisible()} "
      f"| tooltip={w._props_collapse_btn.toolTip()!r}")
print(f"    canvas vp {vp_open} → {w.canvas.viewport().width()} "
      f"(nới rộng={w.canvas.viewport().width() > vp_open})")

shot_window("uienh3_04_window_collapsed.png")
# Cận cảnh mép phải: tab thu gọn.
shot_rect(QRect(w.width() - 120, 88, 120, 260), "uienh3_05_tab_closeup.png")

# ---------- [4] F4 bung lại, giữ bề rộng ----------
w._props_toggle_action.trigger()
pump()
print("\n[4] F4 bung lại:")
print(f"    phím tắt action = {w._props_toggle_action.shortcut().toString()!r} "
      f"(mong 'F4') | action.isChecked()={w._props_toggle_action.isChecked()}")
print(f"    dock width {w_open} → {w.props_dock.width()} "
      f"(giữ nguyên={w.props_dock.width() == w_open})")
print(f"    canvas vp trở lại {w.canvas.viewport().width()} "
      f"(khớp lúc đầu={w.canvas.viewport().width() == vp_open})")
print(f"    tooltip={w._props_collapse_btn.toolTip()!r}")

# ---------- [5] Cận cảnh 2 chevron ----------
closeup = QPixmap(320, 150)
closeup.fill(QColor("#33363B"))
p = QPainter(closeup)
p.setFont(QFont(_fam or "Arial", 11))
for i, (nm, key) in enumerate((("chevron_right (thu gon)", "chevron_right"),
                               ("chevron_left (mo lai)", "chevron_left"))):
    x = 20 + i * 160
    tool_icon(key, size=96).paint(p, QRect(x + 24, 16, 96, 96))
    p.setPen(QColor("#E8E8E8"))
    p.drawText(QRect(x - 5, 118, 160, 24), Qt.AlignHCenter, nm)
p.end()
closeup.save(os.path.join(OUT, "uienh3_06_chevrons_closeup.png"))
LOG.append("uienh3_06_chevrons_closeup.png")

print("\nSAVED:")
for n in LOG:
    print("   ", n)
print("DIR:", OUT)
