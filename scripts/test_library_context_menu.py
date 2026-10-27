"""QC — menu chuột phải ở Thư viện (offscreen).

1. Ảnh: menu có "Copy ảnh vào clipboard" + "Mở thư mục chứa file";
   bấm Copy → clipboard nhận đúng ảnh.
2. Video: chỉ có "Mở thư mục chứa file" (không copy được video).
3. "Mở thư mục chứa file" gọi explorer /select,"<path>" (path có dấu phẩy).
"""
import os
import subprocess
import tempfile

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QListWidgetItem, QMenu

app = QApplication([])

from app.library import library_window as lw
from app.library.library_manager import Capture

tmpdir = tempfile.mkdtemp()
img_path = os.path.join(tmpdir, "anh, test.png")
img = QImage(40, 30, QImage.Format_RGB32)
img.fill(QColor("#FF3B30"))
img.save(img_path)
vid_path = os.path.join(tmpdir, "clip.mp4")
open(vid_path, "wb").close()

caps = {
    1: Capture(1, "anh, test.png", img_path, "2026-01-01T00:00:00", 40, 30, ""),
    2: Capture(2, "clip.mp4", vid_path, "2026-01-01T00:00:00", 0, 0, "",
               media_type="video", duration=1.0),
}


class FakeLib:
    def get(self, cid):
        return caps.get(cid)

    def list_captures(self, search=""):
        return []


w = lw.LibraryWindow(FakeLib())
w.list.clear()
for cid in caps:
    it = QListWidgetItem(str(cid))
    it.setData(Qt.UserRole, cid)
    w.list.addItem(it)

seen: list[list[str]] = []


class _NoPopupMenu(QMenu):
    """Không mở popup thật (exec chặn vòng lặp) — chỉ ghi lại các mục."""

    def exec(self, *a, **k):
        seen.append([act.text() for act in self.actions()])
        self._acts = {act.text(): act for act in self.actions()}
        w._last_menu = self
        return None


lw.QMenu = _NoPopupMenu


def right_click(row):
    item = w.list.item(row)
    w._show_item_menu(w.list.visualItemRect(item).center())


# 1. Ảnh
w.show()
app.processEvents()
right_click(0)
assert seen[-1] == ["Copy ảnh vào clipboard", "Mở thư mục chứa file"], seen[-1]
QApplication.clipboard().clear()
w._last_menu._acts["Copy ảnh vào clipboard"].trigger()
got = QApplication.clipboard().image()
assert not got.isNull() and got.size() == img.size(), "clipboard phải có ảnh"
assert QColor(got.pixel(5, 5)) == QColor("#FF3B30")
print("OK 1: ảnh -> có Copy ảnh, clipboard nhận đúng ảnh")

# 2. Video
right_click(1)
assert seen[-1] == ["Mở thư mục chứa file"], seen[-1]
print("OK 2: video -> chỉ có Mở thư mục chứa file")

# 3. Explorer
calls = []
subprocess.Popen = lambda *a, **k: calls.append(a[0])
right_click(0)
w._last_menu._acts["Mở thư mục chứa file"].trigger()
assert calls == [f'explorer /select,"{os.path.normpath(img_path)}"'], calls
print("OK 3: mở Explorer chọn sẵn file")
print("=== LIBRARY CONTEXT MENU OK ===")
