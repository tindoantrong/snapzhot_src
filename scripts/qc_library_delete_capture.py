"""QC harness DEL2: eyes-test + assert hành vi XOÁ của LibraryWindow offscreen.

KHÔNG đụng DB thật: FakeLibrary duck-typed, stateful (delete xoá khỏi list +
ghi log), có search filter. Monkeypatch QMessageBox.question để (a) bắt nội dung
hộp thoại xác nhận, (b) điều khiển Yes/No. Mô phỏng phím Delete ở list và ở
search_box để kiểm an toàn. Ảnh lưu .ai-workspace/screens/.
"""
import os
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QImage, QKeyEvent, QLinearGradient, QPainter,
)

from app.library.library_window import LibraryWindow

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="qc_del_"))

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

FAILS = []


def check(cond, label):
    print(("OK   " if cond else "FAIL ") + label)
    if not cond:
        FAILS.append(label)


def make_thumb(path: Path, c1: str, c2: str, label: str) -> None:
    img = QImage(220, 140, QImage.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 220, 140)
    g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    p.fillRect(img.rect(), g)
    p.setPen(QColor("white"))
    p.setFont(QFont(_fam or "Arial", 14, QFont.Bold))
    p.drawText(img.rect(), Qt.AlignCenter, label)
    p.end()
    img.save(str(path), "PNG")


class FakeCapture:
    def __init__(self, cid, label, ts, tags, c1="#1E90FF", c2="#0A3D62"):
        self.id = cid
        self.filename = f"{label}.png"
        self.path = str(TMP / f"{label}.png")
        self.created_at = ts
        self.tags = tags
        self.is_video = False
        self.duration = 0.0
        thumb = TMP / f"{cid}.png"
        make_thumb(thumb, c1, c2, label)
        self.thumbnail_path = thumb

    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class FakeLibrary:
    def __init__(self):
        self._caps = [
            FakeCapture(1, "Trang dang nhap", "2026-06-25T09:14", "ui, login"),
            FakeCapture(2, "Bao loi 500", "2026-06-25T08:02", "bug", "#E74C3C", "#641E16"),
            FakeCapture(3, "Dashboard", "2026-06-24T17:40", "report, ui", "#2ECC71", "#145A32"),
            FakeCapture(4, "Hoa don PDF", "2026-06-24T11:20", "", "#9B59B6", "#4A235A"),
            FakeCapture(5, "Man hinh ui khac", "2026-06-24T10:00", "ui", "#F39C12", "#7E5109"),
        ]
        self.deleted = []
        self.tagged = []

    def list_captures(self, search=""):
        s = (search or "").lower().strip()
        if not s:
            return list(self._caps)
        return [c for c in self._caps
                if s in c.filename.lower() or s in c.tags.lower()]

    def get(self, cid):
        return next((c for c in self._caps if c.id == cid), None)

    def delete(self, cid):
        self.deleted.append(cid)
        self._caps = [c for c in self._caps if c.id != cid]

    def set_tags(self, cid, text):
        self.tagged.append((cid, text))


# ---- Monkeypatch hộp thoại: bắt message + điều khiển trả lời ----
DLG = {"msgs": [], "answer": QMessageBox.Yes}
_orig_q = QMessageBox.question


def fake_question(parent, title, text, *args, **kw):
    DLG["msgs"].append((title, text))
    return DLG["answer"]


QMessageBox.question = staticmethod(fake_question)


def shot(w, name):
    app.processEvents()
    w.grab().save(os.path.join(OUT, name))


def select_ids(w, ids):
    w.list.clearSelection()
    for i in range(w.list.count()):
        if w.list.item(i).data(Qt.UserRole) in ids:
            w.list.item(i).setSelected(True)


print("=== DEL2 QC — hành vi XOÁ Thư viện ===")

# ============ 1) Chọn nhiều → Xoá (message số lượng + đúng N biến mất) ============
lib = FakeLibrary()
w = LibraryWindow(lib)
w.resize(900, 640); w.show()
for _ in range(4):
    app.processEvents()
check(w.list.count() == 5, "khởi tạo 5 mục")
select_ids(w, {2, 4})
shot(w, "del_01_multi_selected.png")
check(set(w._selected_ids()) == {2, 4}, "chọn nhiều {2,4}")

DLG["msgs"].clear(); DLG["answer"] = QMessageBox.Yes
w._delete_selected()
app.processEvents()
last_msg = DLG["msgs"][-1][1] if DLG["msgs"] else ""
check("2 mục đã chọn" in last_msg, f'message số lượng "Xoá 2 mục đã chọn?" (got: {last_msg!r})')
check(lib.deleted == [2, 4], f"xoá đúng {{2,4}}: {lib.deleted}")
remaining = [w.list.item(i).data(Qt.UserRole) for i in range(w.list.count())]
check(remaining == [1, 3, 5], f"còn lại nguyên {{1,3,5}}: {remaining}")
check("3 ảnh" in w.count_label.text(), f"refresh count cập nhật: {w.count_label.text()!r}")
shot(w, "del_02_after_multi_delete.png")

# message 1 mục (số ít) khác message nhiều mục
select_ids(w, {1})
DLG["msgs"].clear()
w._delete_selected()
one_msg = DLG["msgs"][-1][1]
check("mục này" in one_msg and "đã chọn" not in one_msg,
      f'message số ít "Xoá mục này?" (got: {one_msg!r})')

# ============ 2) Phím Delete ============
lib2 = FakeLibrary()
w2 = LibraryWindow(lib2)
w2.resize(900, 640); w2.show()
for _ in range(3):
    app.processEvents()

# 2a: chọn mục → Delete (list focus) → cùng luồng xoá có xác nhận
select_ids(w2, {3})
w2.list.setFocus()
DLG["msgs"].clear(); DLG["answer"] = QMessageBox.Yes
ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
w2.keyPressEvent(ev)
app.processEvents()
check(lib2.deleted == [3], f"Delete key xoá mục đang chọn: {lib2.deleted}")
check(len(DLG["msgs"]) == 1, "Delete key VẪN qua hộp thoại xác nhận")

# 2b: Delete khi focus ở search_box → chỉ sửa text, KHÔNG xoá ảnh
deleted_before = list(lib2.deleted)
w2.search_box.setFocus()
w2.search_box.setText("abc")
w2.search_box.setCursorPosition(0)
app.processEvents()
key_del = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
app.sendEvent(w2.search_box, key_del)
app.processEvents()
check(lib2.deleted == deleted_before,
      f"Delete trong search_box KHÔNG xoá ảnh: {lib2.deleted}")
check(w2.search_box.text() == "bc",
      f"Delete trong search_box chỉ sửa text 'abc'->'bc': {w2.search_box.text()!r}")
w2.search_box.clear()
app.processEvents()

# ============ 3) Xoá tất cả ============
# 3a: không filter → xoá toàn bộ → empty-state hiện
lib3 = FakeLibrary()
w3 = LibraryWindow(lib3)
w3.resize(900, 640); w3.show()
for _ in range(3):
    app.processEvents()
DLG["msgs"].clear(); DLG["answer"] = QMessageBox.Yes
w3._delete_all()
app.processEvents()
all_msg = DLG["msgs"][-1][1]
check("toàn bộ 5 mục" in all_msg, f'message "Xoá toàn bộ 5 mục đang hiển thị?" (got: {all_msg!r})')
check(w3.list.count() == 0, f"list rỗng sau Xoá tất cả: {w3.list.count()}")
check(w3.empty_state.isVisible() and not w3.list.isVisible(), "empty-state hiện, list ẩn")
shot(w3, "del_03_empty_after_delete_all.png")

# 3b: có filter active → chỉ xoá phần đang hiển thị
lib4 = FakeLibrary()
w4 = LibraryWindow(lib4)
w4.resize(900, 640); w4.show()
w4.search_box.setText("ui")  # khớp id 1,3,5 (tags/filename chứa 'ui')
for _ in range(3):
    app.processEvents()
shown = [w4.list.item(i).data(Qt.UserRole) for i in range(w4.list.count())]
check(set(shown) == {1, 3, 5}, f"filter 'ui' hiển thị {{1,3,5}}: {shown}")
shot(w4, "del_04_filtered_before_delete_all.png")
DLG["msgs"].clear(); DLG["answer"] = QMessageBox.Yes
w4._delete_all()
app.processEvents()
filt_msg = DLG["msgs"][-1][1]
check(f"toàn bộ {len(shown)} mục" in filt_msg,
      f'message khớp số filter ({len(shown)}): {filt_msg!r}')
check(lib4.deleted == shown, f"chỉ xoá phần hiển thị {shown}: {lib4.deleted}")
# Bỏ filter → các mục bị ẩn (2,4) vẫn còn
w4.search_box.clear()
app.processEvents()
left = sorted(w4.list.item(i).data(Qt.UserRole) for i in range(w4.list.count()))
check(left == [2, 4], f"mục bị filter ẩn KHÔNG bị xoá, còn {{2,4}}: {left}")

# ============ 4) An toàn ============
# 4a: default No (Enter/Esc = No) → không xoá
lib5 = FakeLibrary()
w5 = LibraryWindow(lib5)
w5.resize(900, 640); w5.show()
for _ in range(3):
    app.processEvents()
select_ids(w5, {1, 2})
DLG["answer"] = QMessageBox.No
w5._delete_selected()
w5._delete_all()
check(lib5.deleted == [], f"trả lời No → KHÔNG xoá gì: {lib5.deleted}")
check(w5.list.count() == 5, f"list nguyên 5 mục sau No: {w5.list.count()}")

# 4b: no-op khi không chọn / list rỗng
lib5.deleted.clear()
w5.list.clearSelection()
DLG["msgs"].clear(); DLG["answer"] = QMessageBox.Yes
w5._delete_selected()  # không chọn gì
check(lib5.deleted == [] and len(DLG["msgs"]) == 0,
      "no-op + KHÔNG mở hộp thoại khi không chọn")
# Delete key khi không chọn cũng no-op (guard selectedItems)
ev2 = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
w5.keyPressEvent(ev2)
check(len(DLG["msgs"]) == 0, "Delete key khi không chọn → no-op")
# list rỗng → _delete_all no-op
w6 = LibraryWindow(FakeLibrary())
for cid in [1, 2, 3, 4, 5]:
    w6.library.delete(cid)
w6.refresh()
DLG["msgs"].clear()
w6._delete_all()
check(len(DLG["msgs"]) == 0, "_delete_all no-op + KHÔNG hộp thoại khi list rỗng")

# ============ 5) Regression: open / edit_tags / _selected_id ============
lib7 = FakeLibrary()
w7 = LibraryWindow(lib7)
w7.resize(900, 640); w7.show()
for _ in range(3):
    app.processEvents()
# _selected_id trả mục ĐẦU đang chọn (cho open/edit) dù chọn nhiều
select_ids(w7, {3, 5})
check(w7._selected_id() in (3, 5), f"_selected_id trả 1 mục khi chọn nhiều: {w7._selected_id()}")
# open_in_editor emit với mục ảnh đang chọn
opened = []
w7.open_in_editor.connect(lambda cid: opened.append(cid))
select_ids(w7, {2})
w7._open_selected()
check(opened == [2], f"_open_selected emit open_in_editor(2): {opened}")
# edit_tags chạy với mục đầu chọn (monkeypatch QInputDialog)
from PySide6.QtWidgets import QInputDialog
_orig_in = QInputDialog.getText
QInputDialog.getText = staticmethod(lambda *a, **k: ("ui, edited", True))
select_ids(w7, {1})
w7._edit_tags()
check(lib7.tagged == [(1, "ui, edited")], f"_edit_tags set_tags mục đầu: {lib7.tagged}")
QInputDialog.getText = staticmethod(_orig_in)

# Dọn
QMessageBox.question = staticmethod(_orig_q)
for win in (w, w2, w3, w4, w5, w6, w7):
    win.close()
app.processEvents()

print("DIR:", OUT)
if FAILS:
    print(f"\n=== DEL2 FAIL: {len(FAILS)} ===")
    for f in FAILS:
        print("  -", f)
    raise SystemExit(1)
print("\n=== DEL2 QC OK (all checks pass) ===")
