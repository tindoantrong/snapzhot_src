"""ED3 verify: cửa sổ hẹp → tool toolbar hiện nút overflow ">>" (mọi tool tới
được), zoom controls nằm HÀNG RIÊNG. Grab ảnh + in trạng thái.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar, QToolButton
from PySide6.QtGui import QFont, QFontDatabase

from app.editor.editor_window import EditorWindow
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

w = EditorWindow()
w.load_image(make_sample_image(1280, 800))
w.resize(740, 720)
w.show()
for _ in range(5):
    app.processEvents()

w.grab().save(os.path.join(OUT, "16_narrow_overflow_fixed.png"))

# Báo cáo: tìm tool toolbar + zoom toolbar, kiểm nút overflow ">>" và hàng (y).
bars = w.findChildren(QToolBar)
print("=== Toolbars (title @ y) ===")
for tb in bars:
    print(f"  '{tb.windowTitle()}'  y={tb.y()}  x={tb.x()}  w={tb.width()}")

tool_tb = next(tb for tb in bars if tb.windowTitle() == "Công cụ")
zoom_tb = next(tb for tb in bars if tb.windowTitle() == "Zoom")
print(f"\nTool toolbar y={tool_tb.y()} ; Zoom toolbar y={zoom_tb.y()} ; "
      f"khác hàng = {tool_tb.y() != zoom_tb.y()}")

ext = tool_tb.findChild(QToolButton, "qt_toolbar_ext_button")
print(f"Nút overflow '>>' của tool toolbar: tồn tại={ext is not None} "
      f"visible={ext.isVisible() if ext else False}")

# Đếm tool icon bị ẩn (sẽ nằm trong menu ">>") để chứng minh không mất "âm thầm".
from app.editor.editor_window import TOOLS
hidden = []
for tool, name, *_ in TOOLS:
    act = w._tool_actions[tool]
    btn = tool_tb.widgetForAction(act)
    vis = btn.isVisible() if btn is not None else False
    if not vis:
        hidden.append(name)
print(f"Tool ẩn-trong-overflow (vẫn truy cập qua '>>'): {hidden}")

# Undo/redo phải icon-only (bề ngang ổn định).
for a, nm in ((w.undo_action, "undo"), (w.redo_action, "redo")):
    b = tool_tb.widgetForAction(a)
    print(f"{nm} style icon-only = "
          f"{b.toolButtonStyle().name if b else 'n/a'}")
