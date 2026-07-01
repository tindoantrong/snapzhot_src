"""QC harness REC2: eyes-test XOÁ ảnh từ filmstrip 'Ảnh gần đây' trong Editor.

Dựng EditorWindow THẬT (offscreen) + 6 thumbnail + ảnh full khác nhau theo id.
MÔ PHỎNG controller: connect delete_capture_requested → bỏ ảnh khỏi recents +
nếu xoá ảnh đang mở thì nhảy ảnh mới nhất còn lại (giống _on_delete_capture).

GRAB PNG vào .ai-workspace/screens/ để Read nhìn:
- menu right-click "Xoá ảnh" (theme tối)
- hộp confirm QMessageBox (default No, theme tối)
- strip sau khi xoá ảnh KHÔNG đang mở (Yes) / xoá ảnh ĐANG mở → nhảy ảnh / xoá hết → ẩn dock
KHÔNG sửa app/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenu, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter

from app.editor.editor_window import EditorWindow

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
PALETTE = [
    ("#FF6B6B", "anh_do.png"),
    ("#4DABF7", "anh_xanh.png"),
    ("#51CF66", "anh_la.png"),
    ("#FFD43B", "anh_vang.png"),
    ("#CC5DE8", "anh_tim.png"),
    ("#FF922B", "anh_cam.png"),
]


def make_full(idx, hexc):
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
        path = os.path.join(tmp, f"qc_recdel_{i}.png")
        th.save(path, "PNG")
        items.append({"id": i, "thumb": path, "label": name})
    return items


FULLS = {i: make_full(i, hexc) for i, (hexc, _n) in enumerate(PALETTE, start=1)}


def shot(w, name):
    for _ in range(3):
        app.processEvents()
    w.grab().save(os.path.join(OUT, name))
    LOG.append(name)


def selected_id(w):
    it = w.recent_strip.currentItem()
    return None if it is None else it.data(Qt.UserRole)


w = EditorWindow()
recents = make_thumbs()


# Mô phỏng controller _on_delete_capture.
def on_delete(cid):
    global recents
    LOG.append(f"signal:delete_capture_requested({cid})")
    was_current = (cid == w.current_capture_id)
    recents = [it for it in recents if it["id"] != cid]
    w.set_recent_captures(recents)
    if was_current and recents:
        newest = recents[0]["id"]
        w.load_image(FULLS[newest], capture_id=newest)
        w.set_recent_captures(recents)


w.delete_capture_requested.connect(on_delete)

w.load_image(FULLS[2], capture_id=2)
w.set_recent_captures(recents)
w.resize(1100, 720)
w.show()
shot(w, "rec2_01_baseline_id2_open.png")

# ---- CA 5+6: theme menu right-click + hộp confirm (grab widget thật) ----
# Dựng menu y như _on_recent_context_menu (parent = w → kế thừa EDITOR_QSS).
menu = QMenu(w)
menu.addAction("Xoá ảnh")
menu.show()
for _ in range(3):
    app.processEvents()
menu.grab().save(os.path.join(OUT, "rec2_05_context_menu.png"))
LOG.append("rec2_05_context_menu.png")
menu.close()

mb = QMessageBox(QMessageBox.Question, "Xoá ảnh",
                 "Xoá ảnh này khỏi thư viện?",
                 QMessageBox.Yes | QMessageBox.No, w)
mb.setDefaultButton(QMessageBox.No)
mb.show()
for _ in range(3):
    app.processEvents()
mb.grab().save(os.path.join(OUT, "rec2_06_confirm_dialog.png"))
LOG.append("rec2_06_confirm_dialog.png")
default_is_no = (mb.defaultButton() is mb.button(QMessageBox.No))
mb.close()
print("CA6 confirm: defaultButton == No ->", default_is_no)

# ---- CA: confirm No → KHÔNG xoá ----
emitted = []
w.delete_capture_requested.connect(lambda c: emitted.append(c))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
count_before = w.recent_strip.count()
w._request_delete_capture(5)
print("CA confirm No: emitted =", emitted, "| count giữ nguyên =",
      (w.recent_strip.count() == count_before == 6))

# ---- CA3: confirm Yes → xoá ảnh KHÔNG đang mở (id=5) ----
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
w._request_delete_capture(5)
shot(w, "rec2_02_after_delete_id5.png")
ids_now = [w.recent_strip.item(i).data(Qt.UserRole)
           for i in range(w.recent_strip.count())]
print("CA3 delete id5 (Yes): ids =", ids_now,
      "| current giữ id2 =", w.current_capture_id,
      "| selected =", selected_id(w))

# ---- CA4: xoá ảnh ĐANG mở (id=2) → nhảy ảnh mới nhất còn lại ----
w._request_delete_capture(2)
shot(w, "rec2_03_after_delete_current_id2.png")
ids_now = [w.recent_strip.item(i).data(Qt.UserRole)
           for i in range(w.recent_strip.count())]
print("CA4 delete current id2: ids =", ids_now,
      "| editor nhảy current =", w.current_capture_id,
      "| selected =", selected_id(w),
      "| dock visible =", w.recent_dock.isVisible())

# ---- CA5: xoá tới HẾT → strip ẩn gọn ----
for cid in list(ids_now):
    w._request_delete_capture(cid)
shot(w, "rec2_04_after_delete_all_dock_hidden.png")
print("CA5 delete all: count =", w.recent_strip.count(),
      "| dock visible =", w.recent_dock.isVisible())

# ---- CA: phím Delete trên strip → đường xoá chạy (qua confirm) ----
from PySide6.QtCore import QEvent
from PySide6.QtGui import QKeyEvent
recents = make_thumbs()
w.set_recent_captures(recents)
w.load_image(FULLS[3], capture_id=3)   # currentItem = id3
before = w.recent_strip.count()
cur = selected_id(w)
ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
handled = w.eventFilter(w.recent_strip, ev)
after = w.recent_strip.count()
print("CA Delete-key: currentItem =", cur, "| handled(nuốt phím) =", handled,
      "| count", before, "->", after, "(xoá 1 qua confirm Yes)")

print("SAVED:")
for n in LOG:
    print("  ", n)
print("DIR:", OUT)
