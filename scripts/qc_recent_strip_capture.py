"""QC harness REC1: eyes-test dải 'Ảnh gần đây' (filmstrip) trong Editor.

Dựng EditorWindow THẬT (offscreen), nạp 6 thumbnail mẫu + ảnh full KHÁC NHAU
theo id (để thấy canvas đổi khi click). MÔ PHỎNG controller: connect
open_capture_requested → load ảnh id đó + set_recent_captures lại (giống
_refresh_editor_recents) → kiểm highlight nhảy theo + canvas load đúng ảnh.

GRAB PNG vào .ai-workspace/screens/ để Read nhìn bằng mắt. KHÔNG sửa app/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter

from app.editor.editor_window import EditorWindow

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])

# Nạp font Windows để chữ không thành tofu khi offscreen (artifact chụp).
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
PALETTE = [
    ("#FF6B6B", "anh_do.png"),
    ("#4DABF7", "anh_xanh.png"),
    ("#51CF66", "anh_la.png"),
    ("#FFD43B", "anh_vang.png"),
    ("#CC5DE8", "anh_tim.png"),
    ("#FF922B", "anh_cam.png"),
]


def make_full(idx, hexc):
    """Ảnh full để load vào canvas: nền màu + số to → dễ phân biệt khi đổi."""
    img = QImage(1000, 640, QImage.Format_RGB32)
    img.fill(QColor(hexc))
    p = QPainter(img)
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont(_fam or "Arial", 180, QFont.Bold))
    p.drawText(img.rect(), Qt.AlignCenter, f"#{idx}")
    p.setFont(QFont(_fam or "Arial", 28, QFont.Bold))
    p.drawText(img.rect().adjusted(0, 60, 0, 0), Qt.AlignHCenter | Qt.AlignTop,
               PALETTE[idx - 1][1])
    p.end()
    return img


def make_thumbs():
    import tempfile
    tmp = tempfile.gettempdir()
    items = []
    for i, (hexc, name) in enumerate(PALETTE, start=1):
        th = QImage(120, 80, QImage.Format_RGB32)
        th.fill(QColor(hexc))
        pp = QPainter(th)
        pp.setPen(QColor("#ffffff"))
        pp.setFont(QFont(_fam or "Arial", 30, QFont.Bold))
        pp.drawText(th.rect(), Qt.AlignCenter, str(i))
        pp.end()
        path = os.path.join(tmp, f"qc_recent_{i}.png")
        th.save(path, "PNG")
        items.append({"id": i, "thumb": path, "label": name})
    return items


FULLS = {i: make_full(i, hexc) for i, (hexc, _n) in enumerate(PALETTE, start=1)}
ITEMS = make_thumbs()


def shot(w, name):
    for _ in range(3):
        app.processEvents()
    w.grab().save(os.path.join(OUT, name))
    LOG.append(name)


def selected_id(w):
    it = w.recent_strip.currentItem()
    return None if it is None else it.data(Qt.UserRole)


w = EditorWindow()

# Mô phỏng controller: click thumbnail → load ảnh id đó + refresh strip.
def on_request(cid):
    LOG.append(f"signal:open_capture_requested({cid})")
    w.load_image(FULLS[cid], capture_id=cid)
    w.set_recent_captures(ITEMS)   # giống _refresh_editor_recents


w.open_capture_requested.connect(on_request)

# Khởi tạo giống launcher: load ảnh #2 + nạp strip.
w.load_image(FULLS[2], capture_id=2)
w.set_recent_captures(ITEMS)
w.resize(1100, 720)
w.show()
shot(w, "rec_01_open_id2_highlight.png")
print("STATE after open id2: current_capture_id =", w.current_capture_id,
      "| strip selected id =", selected_id(w),
      "| dock visible =", w.recent_dock.isVisible(),
      "| count =", w.recent_strip.count())

# Crop cận cảnh filmstrip để soi viền highlight.
dockshot = w.recent_dock.grab()
dockshot.save(os.path.join(OUT, "rec_02_filmstrip_closeup_id2.png"))
LOG.append("rec_02_filmstrip_closeup_id2.png")

# Click thumbnail KHÁC (id=4) qua handler thật → emit signal → controller load.
item4 = w.recent_strip.item(3)
w._on_recent_item_clicked(item4)
shot(w, "rec_03_after_click_id4.png")
print("STATE after click id4: current_capture_id =", w.current_capture_id,
      "| strip selected id =", selected_id(w))
w.recent_dock.grab().save(os.path.join(OUT, "rec_04_filmstrip_closeup_id4.png"))
LOG.append("rec_04_filmstrip_closeup_id4.png")

# Click lại chính ảnh đang mở (id=4) → KHÔNG load lại (no-op), highlight giữ.
before = list(LOG)
w._on_recent_item_clicked(w.recent_strip.item(3))
noop = (LOG == before)   # không có signal mới append
print("STATE click same id4: no new signal =", noop,
      "| selected id =", selected_id(w))

# Strip rỗng → ẩn dock.
w.set_recent_captures([])
shot(w, "rec_05_empty_dock_hidden.png")
print("STATE empty: dock visible =", w.recent_dock.isVisible(),
      "| count =", w.recent_strip.count())

# Sample màu pixel viền item selected để xác nhận accent #1E90FF.
w.set_recent_captures(ITEMS)
w.load_image(FULLS[1], capture_id=1)
for _ in range(3):
    app.processEvents()
img = w.recent_dock.grab().toImage()
# Quét tìm pixel xanh accent quanh item đầu.
target = QColor("#1E90FF")
found = 0
for y in range(0, img.height(), 2):
    for x in range(0, img.width(), 2):
        c = img.pixelColor(x, y)
        if (abs(c.red() - target.red()) < 24 and abs(c.green() - target.green()) < 24
                and abs(c.blue() - target.blue()) < 30):
            found += 1
print("ACCENT #1E90FF-ish pixels in filmstrip (id=1 selected):", found)

print("SAVED:")
for n in LOG:
    print("  ", n)
print("DIR:", OUT)
