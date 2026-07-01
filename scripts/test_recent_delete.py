"""Test REC2: xoá ảnh từ dải 'Ảnh gần đây' trong Editor.

(A) editor_window: confirm Yes→emit delete_capture_requested, No→không; phím Delete
    trên recent_strip → đường xoá chạy (qua confirm).
(B) app_controller._on_delete_capture với library giả: delete đúng id + refresh;
    xoá ảnh đang mở + còn ảnh → load ảnh mới nhất còn lại; xoá hết → không crash.
"""
import os
import sys
import types

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtWidgets import QApplication, QMessageBox

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


# ===== (A) editor confirm + emit =====
def test_editor() -> None:
    w = EditorWindow()
    w.set_recent_captures(items())
    emitted = []
    w.delete_capture_requested.connect(lambda cid: emitted.append(cid))

    # confirm No → KHÔNG emit
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
    w._request_delete_capture(2)
    assert emitted == [], emitted

    # confirm Yes → emit đúng id
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    w._request_delete_capture(2)
    assert emitted == [2], emitted

    # Phím Delete trên strip (currentItem id=3) → đường xoá chạy → emit 3
    w.load_image(img, capture_id=3)  # highlight id=3 thành currentItem
    assert w.recent_strip.currentItem().data(Qt.UserRole) == 3
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
    handled = w.eventFilter(w.recent_strip, ev)
    assert handled is True, "Delete trên strip phải được nuốt"
    assert emitted == [2, 3], emitted
    print("OK: editor confirm No/Yes + phím Delete")


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
    assert c.library.deleted == [3], c.library.deleted
    assert opened == [], opened

    # 2. Xoá ảnh ĐANG mở (current=5) + còn ảnh → mở ảnh mới nhất còn lại (4)
    c._on_delete_capture(5)
    assert c.library.deleted == [3, 5], c.library.deleted
    assert opened == [4], opened  # còn [4] sau khi xoá 5

    # 3. Xoá nốt ảnh cuối đang mở → hết ảnh → KHÔNG crash, KHÔNG mở lại
    c.editor._current_capture_id = 4
    opened.clear()
    c._on_delete_capture(4)
    assert c.library.deleted == [3, 5, 4], c.library.deleted
    assert opened == [], opened
    assert c.library.list_captures() == []
    print("OK: controller _on_delete_capture (thường / đang-mở / hết-ảnh)")


def main() -> int:
    test_editor()
    test_controller()
    print("=== RECENT DELETE OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
