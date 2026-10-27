"""QC REGION-STUCK — chụp vùng bị mờ màn hình, không chụp được (offscreen).

Nguyên nhân: lib keyboard bắn callback trên mọi KEY_DOWN (kể cả auto-repeat) →
capture_region chạy lại khi overlay đang hiện → ảnh đóng băng dính chính overlay
(mờ chồng mờ) + vùng đang kéo bị reset. Kiểm tra:
1. Gọi capture_region dồn dập khi overlay hiện → chỉ đóng băng 1 lần.
2. Đang chờ ẩn cửa sổ app (pending) → bỏ qua lần gọi chồng.
3. Overlay hiện → đăng ký Esc toàn cục; Esc toàn cục hủy overlay + gỡ hotkey.
4. Esc vừa hủy overlay khi đang quay → KHÔNG dừng luôn video.
5. Không còn hotkey quay video (Ctrl+Shift+R) toàn cục.
"""
import os
import sys
import types

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


class _FakeKeyboard(types.ModuleType):
    KEY_DOWN = "down"

    def __init__(self):
        super().__init__("keyboard")
        self.added = []
        self.removed = []
        self._next = 0

    def add_hotkey(self, key, callback, *a, **k):
        self._next += 1
        h = ("handle", self._next)
        self.added.append((key, callback, h))
        return h

    def remove_hotkey(self, handle):
        self.removed.append(handle)

    def hook_key(self, key, cb, suppress=False):
        return lambda: None

    def remove_all_hotkeys(self):
        pass


fake_kb = _FakeKeyboard()
sys.modules["keyboard"] = fake_kb

app = QApplication([])

from app import app_controller as ac
from app.app_controller import AppController

shots: list = []


def _fake_fullscreen():
    shots.append(1)
    img = QImage(200, 100, QImage.Format_RGB32)
    img.fill(0)
    return img


ac.capture_manager.capture_fullscreen = _fake_fullscreen

c = AppController()
c.library_window.hide()
c.editor.hide()

# 1. Bấm dồn khi overlay đang hiện
c.capture_region()
assert c.region_selector.isVisible(), "overlay phải hiện"
for _ in range(10):
    c.capture_region()
assert len(shots) == 1, f"chỉ được đóng băng 1 lần, thực tế {len(shots)}"
print("OK 1: auto-repeat khi overlay hiện -> bỏ qua, không đóng băng lại")

# 3. Esc toàn cục
assert c._esc_handle is not None, "overlay hiện phải đăng ký Esc toàn cục"
c._on_escape()
assert not c.region_selector.isVisible(), "Esc toàn cục phải hủy overlay"
assert c._esc_handle is None, "đóng overlay phải gỡ Esc"
print("OK 3: Esc toàn cục hủy overlay + gỡ hotkey")

# 2. Pending
shots.clear()
c._region_closed_at = 0.0
c.library_window.show()
c.capture_region()
assert c._region_pending and not c.region_selector.isVisible()
c.capture_region()
c._start_frozen_region()
assert len(shots) == 1 and c.region_selector.isVisible()
c.region_selector.cancel()
print("OK 2: đang chờ ẩn cửa sổ -> lần gọi chồng bị bỏ qua")


# 4. Esc vừa hủy overlay khi đang quay
class FakeRecorder:
    stopped = False

    def stop(self):
        self.stopped = True


rec = FakeRecorder()
c._recorder = rec
c._recording = True
c._start_frozen_region()
c.region_selector.cancel()          # như keyPressEvent Esc của overlay
c._on_escape()                       # Esc toàn cục cùng phím tới sau
assert not rec.stopped, "Esc hủy overlay không được dừng video"
assert c._esc_handle is not None, "đang quay -> Esc toàn cục phải còn"
c._recording = False
print("OK 4: Esc hủy overlay khi đang quay -> video vẫn chạy")

# 5. Không còn hotkey quay video
fake_kb.added.clear()
c.install_global_hotkeys()
keys = [k for k, *_ in fake_kb.added]
assert not any("shift+r" in k for k in keys), keys
assert not hasattr(c, "request_video_toggle")
print("OK 5: không còn hotkey quay video toàn cục")

print("=== REGION REPEAT GUARD OK ===")
