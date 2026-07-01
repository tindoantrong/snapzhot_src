"""QC harness: dựng màn Thư viện (LibraryWindow) THẬT offscreen + GRAB PNG để
eyes-test theme tối (LIB1).

KHÔNG đụng DB thật của user: dùng LibraryManager GIẢ (duck-typed) trả về capture
mẫu, thumbnail vẽ vào thư mục TEMP. Chỉ dùng public API của LibraryWindow.
Ảnh lưu vào .ai-workspace/screens/.
"""
import os
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter,
)

from app.library.library_window import LibraryWindow

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="qc_lib_"))

app = QApplication([])

# Offscreen không nạp font hệ thống → tofu. Nạp font Windows (artifact chụp).
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


def make_thumb(path: Path, c1: str, c2: str, label: str) -> None:
    img = QImage(220, 140, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 220, 140)
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    p.fillRect(img.rect(), g)
    p.setPen(QColor("white"))
    p.setFont(QFont(_fam or "Arial", 14, QFont.Bold))
    p.drawText(img.rect(), Qt.AlignCenter, label)
    p.end()
    img.save(str(path), "PNG")


class FakeCapture:
    def __init__(self, cid, label, created_at, tags, is_video=False,
                 duration=0.0, thumb=None):
        self.id = cid
        self.filename = f"{label}.png"
        self.path = str(TMP / f"{label}.png")
        self.created_at = created_at
        self.tags = tags
        self._is_video = is_video
        self.duration = duration
        self._thumb = thumb or (TMP / f"{cid}.png")

    @property
    def thumbnail_path(self):
        return self._thumb

    @property
    def is_video(self):
        return self._is_video

    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


def build_caps():
    caps = []
    specs = [
        (1, "Trang dang nhap", "2026-06-25T09:14:00", "ui, login", "#1E90FF", "#0A3D62"),
        (2, "Bao loi 500", "2026-06-25T08:02:11", "bug", "#E74C3C", "#641E16"),
        (3, "Dashboard", "2026-06-24T17:40:30", "report, ui", "#2ECC71", "#145A32"),
        (4, "Hoa don PDF", "2026-06-24T11:20:00", "", "#9B59B6", "#4A235A"),
    ]
    for cid, label, ts, tags, c1, c2 in specs:
        thumb = TMP / f"{cid}.png"
        make_thumb(thumb, c1, c2, label)
        caps.append(FakeCapture(cid, label, ts, tags, thumb=thumb))
    # 1 video: thumbnail null → window tự vẽ play badge nền đen.
    caps.append(FakeCapture(5, "Demo quay man hinh",
                            "2026-06-24T10:00:00", "demo, video",
                            is_video=True, duration=92.0,
                            thumb=TMP / "nonexistent.png"))
    return caps


class FakeLibrary:
    def __init__(self, caps):
        self._caps = caps

    def list_captures(self, search=""):
        s = (search or "").lower().strip()
        if not s:
            return list(self._caps)
        return [c for c in self._caps
                if s in c.filename.lower() or s in c.tags.lower()]

    def get(self, cid):
        return next((c for c in self._caps if c.id == cid), None)


def shot(w, name):
    app.processEvents()
    w.grab().save(os.path.join(OUT, name))
    LOG.append(name)


# ---- 1) Thư viện có dữ liệu (lưới thumbnail, theme tối) ----
lib = FakeLibrary(build_caps())
w = LibraryWindow(lib)
w.resize(900, 640)
w.show()
for _ in range(4):
    app.processEvents()
shot(w, "lib_01_populated.png")

# ---- 2) Item được chọn (selection accent xanh) ----
w.list.setCurrentRow(0)
w.list.item(0).setSelected(True)
app.processEvents()
shot(w, "lib_02_item_selected.png")

# ---- 2b) Hover item (viền card hiện) — di chuột vào item thứ 2 (chưa chọn) ----
from PySide6.QtCore import QEvent, QPoint, QPointF
from PySide6.QtGui import QMouseEvent
w.list.clearSelection()
vp = w.list.viewport()
it = w.list.item(1)  # "Bao loi 500" — item chưa chọn
rect = w.list.visualItemRect(it)
hp = rect.center()
gp = vp.mapToGlobal(hp)
ev = QMouseEvent(QEvent.MouseMove, QPointF(hp), QPointF(gp),
                 Qt.NoButton, Qt.NoButton, Qt.NoModifier)
app.sendEvent(vp, ev)
for _ in range(3):
    app.processEvents()
shot(w, "lib_05_item_hover.png")

# ---- 3) Ô tìm kiếm có focus + đang lọc ----
w.search_box.setFocus()
w.search_box.setText("ui")
for _ in range(3):
    app.processEvents()
shot(w, "lib_03_search_focus_filter.png")

# ---- 4) Trạng thái rỗng (empty-state card) ----
w2 = LibraryWindow(FakeLibrary([]))
w2.resize(900, 640)
w2.show()
for _ in range(4):
    app.processEvents()
shot(w2, "lib_04_empty_state.png")

# ---- Kiểm wiring + màu (assert, không phải eyes) ----
from PySide6.QtWidgets import QPushButton, QToolBar

# (a) màu nền toolbar tại vùng trống (phải = #33363B, KHÔNG bị #2B2D31 đè)
tb = w2.findChildren(QToolBar)[0]
img = w2.grab().toImage()
ty = tb.geometry().center().y()
tb_colors = [img.pixelColor(x, ty).name() for x in (440, 550, 700, 860)]
print("TOOLBAR_BG_EMPTY_REGIONS:", tb_colors)

# (b) màu nền card empty-state (phải ~ #3A3D42)
es = w2.empty_state
gc = es.geometry().center()
print("EMPTY_CARD_BG:", img.pixelColor(gc.x(), gc.y()).name(),
      "geom:", es.geometry())

# (c) wiring 3 nút CTA emit đúng signal
fired = []
w2.request_capture_region.connect(lambda: fired.append("region"))
w2.request_capture_fullscreen.connect(lambda: fired.append("full"))
w2.request_video.connect(lambda: fired.append("video"))
cta_btns = [b for b in es.findChildren(QPushButton)]
print("CTA_COUNT:", len(cta_btns),
      "icons_nonnull:", [not b.icon().isNull() for b in cta_btns],
      "texts:", [b.text() for b in cta_btns],
      "objnames:", [b.objectName() for b in cta_btns])
for b in cta_btns:
    b.click()
    app.processEvents()
print("CTA_SIGNALS_FIRED:", fired)

# (d) search box có 1 leading action với icon non-null
sb_actions = w.search_box.actions()
print("SEARCH_LEADING_ACTIONS:", len(sb_actions),
      "icon_nonnull:", [not a.icon().isNull() for a in sb_actions])

# (e) nhãn item KHÔNG còn emoji 🎬/🏷
labels = [w.list.item(i).text() for i in range(w.list.count())]
print("ITEM_LABELS_HAVE_EMOJI:",
      any(("🎬" in t or "🏷" in t) for t in labels))

# ---- Đóng cửa sổ (dọn tiến trình) ----
w.close()
w2.close()
app.processEvents()

print("SAVED:")
for n in LOG:
    print("  ", n)
print("DIR:", OUT)
print("TMP:", TMP)
