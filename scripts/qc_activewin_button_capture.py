"""QC eyes-test: nút "Chụp app đang dùng" trên toolbar Editor (sáng + tối).

Chạy: python scripts/qc_activewin_button_capture.py
Ảnh ra: .ai-workspace/screens/awbtn_*.png
"""
import os
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_tmp_cfg = Path(tempfile.mktemp(suffix="_qc_awbtn.json"))
import app.common.config as _cfg_mod
_cfg_mod.config_path = lambda: _tmp_cfg

from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage
from PySide6.QtWidgets import QApplication

from app.common import theme
from app.editor.editor_window import EditorWindow
from app.editor.tool_icons import tool_icon

app = QApplication.instance() or QApplication([])
# Offscreen không có font hệ thống → chữ Việt thành ô vuông. Nạp font thật.
_fam = ""
for _f in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fontsrial.ttf"):
    if os.path.exists(_f):
        fams = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(_f))
        if fams:
            _fam = fams[0]
            break
if _fam:
    app.setFont(QFont(_fam, 10))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)
LOG = []


def shot(widget, name):
    for _ in range(5):
        app.processEvents()
    widget.grab().save(os.path.join(OUT, name))
    LOG.append(name)


img = QImage(900, 560, QImage.Format_RGB32)
img.fill(QColor("#2F6FB0"))

for mode in ("dark", "light"):
    theme.manager.set_mode(mode)
    theme.apply_to_app(app)
    w = EditorWindow()
    w.load_image(img)
    w.resize(1280, 760)
    w.show()
    shot(w, f"awbtn_01_editor_{mode}.png")
    bar = w.findChild(type(w.findChildren(type(w))[0]) if False else object, "captureBar")
    bar = next((c for c in w.children() if getattr(c, "objectName", lambda: "")() == "captureBar"), None)
    if bar is not None:
        shot(bar, f"awbtn_02_toolbar_{mode}.png")
    w.close()

# Icon riêng, phóng to để soi nét vẽ.
for mode in ("dark", "light"):
    theme.manager.set_mode(mode)
    pm = tool_icon("capture_window", size=96).pixmap(96, 96)
    name = f"awbtn_03_icon_{mode}.png"
    pm.save(os.path.join(OUT, name))
    LOG.append(name)

_tmp_cfg.unlink(missing_ok=True)
print("Kiểm tra bằng mắt:")
print("  - Toolbar: Về thư viện | Chụp vùng · Chụp toàn màn hình · Chụp app đang dùng · Quay video")
print("  - Nút mới nằm KẾ nút Quay video, icon là khung cửa sổ có thanh tiêu đề + 2 nút nhỏ.")
print("  - Icon phải cùng tông line-art với các icon xung quanh, rõ ở cả nền sáng lẫn tối.")
print("SAVED:", *LOG, sep="\n    ")
print("DIR:", OUT)
