"""Test REC2: xoá ảnh từ dải 'Ảnh gần đây' trong Editor.

(A) editor_window: _request_delete_capture gỡ thẻ NGAY rồi mới phát signal
    (không hỏi xác nhận, không chờ I/O); restore_recent_item trả thẻ về chỗ cũ;
    phím Delete trên recent_strip → đường xoá chạy ngay.
(B) app_controller._on_delete_capture với library giả: I/O file chạy ở luồng
    nền, xoá bản ghi DB chỉ sau khi file xoá xong; xoá ảnh đang mở + còn ảnh →
    load ảnh mới nhất còn lại; xoá hết → không crash.
(C) unlink thất bại → KHÔNG xoá bản ghi + thẻ được trả về dải + báo toast.
"""
import os
import sys
import types

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QEvent, QThreadPool
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtWidgets import QApplication

# Mock `keyboard` trước khi import AppController (như test_escape).
fake_kb = types.ModuleType("keyboard")
fake_kb.add_hotkey = lambda *a, **k: ("h", 0)
fake_kb.remove_hotkey = lambda *a, **k: None
sys.modules["keyboard"] = fake_kb

app = QApplication([])

from app.editor.editor_window import EditorWindow
from app.app_controller import AppController

img = QImage(120, 80, QImage.Format_RGB32)
img.fill(QColor("#3366cc"))


def items():
    return [
        {"id": 1, "thumb": "/no/1.png", "label": "a1.png"},
        {"id": 2, "thumb": "/no/2.png", "label": "a2.png"},
        {"id": 3, "thumb": "/no/3.png", "label": "a3.png"},
    ]


def settle() -> None:
    """Chờ task nền xong rồi bơm event queue để signal về tới luồng GUI."""
    QThreadPool.globalInstance().waitForDone(5000)
    for _ in range(6):
        app.processEvents()


# ===== (A) editor gỡ thẻ ngay (không confirm, không chờ I/O) =====
def test_editor() -> None:
    w = EditorWindow()
    w.set_recent_captures(items())
    emitted = []
    w.delete_capture_requested.connect(lambda cid: emitted.append(cid))

    # _request_delete_capture phát thẳng tín hiệu, không hỏi xác nhận
    w._request_delete_capture(2)
    assert emitted == [2], emitted
    # ... và thẻ biến mất khỏi dải NGAY, không đợi controller
    ids = [w.recent_strip.item(i).data(Qt.UserRole)
           for i in range(w.recent_strip.count())]
    assert ids == [1, 3], ids

    # Xoá hỏng → trả thẻ về ĐÚNG vị trí cũ (giữa 1 và 3)
    assert w.restore_recent_item(2) is True
    ids = [w.recent_strip.item(i).data(Qt.UserRole)
           for i in range(w.recent_strip.count())]
    assert ids == [1, 2, 3], ids
    # Trả rồi thì hết đường trả tiếp
    assert w.restore_recent_item(2) is False
    emitted.clear()
    w._request_delete_capture(2)
    assert emitted == [2], emitted

    # Phím Delete trên strip (currentItem id=3) → đường xoá chạy ngay → emit 3
    w.load_image(img, capture_id=3)  # highlight id=3 thành currentItem
    assert w.recent_strip.currentItem().data(Qt.UserRole) == 3
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
    handled = w.eventFilter(w.recent_strip, ev)
    assert handled is True, "Delete trên strip phải được nuốt"
    assert emitted == [2, 3], emitted
    print("OK: editor xoá ngay không confirm + phím Delete")


# ===== (B) controller _on_delete_capture =====
class FakeCap:
    def __init__(self, cid, is_video=False):
        self.id = cid
        self.is_video = is_video
        self.path = "/no/path.png"
        self.thumbnail_path = f"/no/thumb_{cid}.png"
        self.filename = f"cap_{cid}.png"


class FakeLibrary:
    def __init__(self, caps):
        self._caps = list(caps)  # giả định mới→cũ (DESC)
        self.deleted = []

    def list_captures(self, search=""):
        return list(self._caps)

    def delete(self, cid):
        self.deleted.append(cid)
        self._caps = [c for c in self._caps if c.id != cid]

    def delete_record(self, cid):
        self.deleted.append(cid)
        self._caps = [c for c in self._caps if c.id != cid]

    def get(self, cid):
        for c in self._caps:
            if c.id == cid:
                return c
        return None


def test_controller() -> None:
    c = AppController()
    c.library_window.refresh = lambda: None
    c.tray.showMessage = lambda *a, **k: None
    # Theo dõi ảnh được mở lại.
    opened = []
    orig_open = c._open_capture_in_editor
    c._open_capture_in_editor = lambda cid: opened.append(cid)

    # caps mới→cũ: id 5,4,3
    c.library = FakeLibrary([FakeCap(5), FakeCap(4), FakeCap(3)])

    # 1. Xoá ảnh KHÔNG đang mở (current=5, xoá 3) → delete đúng, KHÔNG mở lại
    c.editor._current_capture_id = 5
    c._on_delete_capture(3)
    # Bản ghi CHƯA xoá ngay: còn chờ luồng nền xoá file xong.
    assert c.library.deleted == [], c.library.deleted
    assert 3 in c._pending_deletes
    settle()
    assert c.library.deleted == [3], c.library.deleted
    assert c._pending_deletes == {}, c._pending_deletes
    assert opened == [], opened

    # 2. Xoá ảnh ĐANG mở (current=5) + còn ảnh → mở ảnh mới nhất còn lại (4)
    c._on_delete_capture(5)
    settle()
    assert c.library.deleted == [3, 5], c.library.deleted
    assert opened == [4], opened  # còn [4] sau khi xoá 5

    # 3. Xoá nốt ảnh cuối đang mở → hết ảnh → KHÔNG crash, KHÔNG mở lại
    c.editor._current_capture_id = 4
    opened.clear()
    c._on_delete_capture(4)
    settle()
    assert c.library.deleted == [3, 5, 4], c.library.deleted
    assert opened == [], opened
    assert c.library.list_captures() == []

    # 4. Bắn 2 lần liên tiếp cùng id → chỉ chạy 1 lần (guard _pending_deletes)
    c.library = FakeLibrary([FakeCap(9)])
    c.editor._current_capture_id = None
    c._on_delete_capture(9)
    c._on_delete_capture(9)
    settle()
    assert c.library.deleted == [9], c.library.deleted
    print("OK: controller _on_delete_capture (nền / đang-mở / hết-ảnh / bấm 2 lần)")


# ===== (C) unlink hỏng → không xoá bản ghi, trả thẻ về, báo toast =====
def test_delete_failure() -> None:
    import tempfile

    c = AppController()
    c.tray.showMessage = lambda *a, **k: None
    toasts = []
    c.editor.show_toast = lambda t: toasts.append(t)

    # path trỏ vào một THƯ MỤC → Path.unlink() ném OSError (mô phỏng file bị khoá)
    locked_dir = tempfile.mkdtemp(prefix="snag_lock_")
    cap = FakeCap(7)
    cap.path = locked_dir
    cap.thumbnail_path = locked_dir
    c.library = FakeLibrary([cap])

    c.editor.set_recent_captures(items() + [{"id": 7, "thumb": "/no/7.png",
                                             "label": "a7.png"}])
    c.editor._request_delete_capture(7)
    assert 7 not in [c.editor.recent_strip.item(i).data(Qt.UserRole)
                     for i in range(c.editor.recent_strip.count())]
    settle()

    assert c.library.deleted == [], "unlink hỏng thì KHÔNG được xoá bản ghi"
    ids = [c.editor.recent_strip.item(i).data(Qt.UserRole)
           for i in range(c.editor.recent_strip.count())]
    assert ids == [1, 2, 3, 7], ids  # thẻ đã được trả về đúng chỗ
    assert toasts and "Không xoá được" in toasts[0], toasts
    os.rmdir(locked_dir)
    print("OK: unlink hỏng → giữ bản ghi + trả thẻ + toast (không im lặng)")


def main() -> int:
    test_editor()
    test_controller()
    test_delete_failure()
    print("=== RECENT DELETE OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
