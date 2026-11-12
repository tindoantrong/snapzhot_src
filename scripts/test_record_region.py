"""QC — quay video: chọn vùng trước khi quay + vẽ con trỏ chuột (offscreen).

1. Bấm Quay video → hiện overlay chọn vùng (KHÔNG quay ngay), đăng ký Esc.
2. Kéo chọn vùng → quay đúng vùng pixel vật lý; khung đỏ hiện quanh vùng.
3. Enter → quay toàn màn hình (vùng ảo của mss), không có khung đỏ.
4. Esc toàn cục khi đang chọn vùng → hủy, không quay.
5. Bấm dồn khi đang chọn vùng → bỏ qua.
6. Đổi toạ độ logic → vật lý theo DPI (gốc màn hình giữ nguyên) + kẹp mép.
7. CursorOverlay: vẽ vòng click lên frame, frame ngoài vùng thì không đụng.
"""
import os
import sys
import time
import types

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakeKeyboard(types.ModuleType):
    KEY_DOWN = "down"

    def __init__(self):
        super().__init__("keyboard")
        self._n = 0

    def add_hotkey(self, *a, **k):
        self._n += 1
        return ("h", self._n)

    def remove_hotkey(self, h):
        pass

    def hook_key(self, *a, **k):
        return lambda: None

    def remove_all_hotkeys(self):
        pass


sys.modules["keyboard"] = _FakeKeyboard()

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

app = QApplication([])

from app import app_controller as ac
from app.app_controller import AppController
from app.recording import cursor_overlay

started: list[tuple[dict, QRect | None]] = []

c = AppController()
c._record_audio_enabled = False
c.tray.showMessage = lambda *a, **k: None
c._begin_recording = lambda region, frame_rect=None: started.append((region, frame_rect))
ac.capture_manager.virtual_screen_geometry = lambda: {
    "left": 0, "top": 0, "width": 1920, "height": 1080}
c.library_window.hide()
c.editor.hide()


def flush_timers(ms=400):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


# 1
c.toggle_video_recording()
flush_timers()
sel = c.record_region_selector
assert sel.isVisible(), "phải hiện overlay chọn vùng quay"
assert started == [], "chưa được quay khi chưa chọn vùng"
assert c._esc_handle is not None
print("OK 1: bấm Quay video -> chọn vùng trước, chưa quay")

# 5
c.toggle_video_recording()
assert started == [] and sel.isVisible()
print("OK 5: bấm dồn khi đang chọn vùng -> bỏ qua")

# 2
sel.hide()
sel.region_selected.emit(QRect(100, 50, 400, 300))
flush_timers(300)
assert len(started) == 1, started
region, frame_rect = started[-1]
dpr = app.primaryScreen().devicePixelRatio()
assert region == {"left": round(100 * dpr), "top": round(50 * dpr),
                  "width": round(400 * dpr), "height": round(300 * dpr)}, region
assert frame_rect == QRect(100, 50, 400, 300)
assert c._esc_handle is None, "đóng overlay -> gỡ Esc (chưa quay thật trong test)"
print("OK 2: kéo vùng -> quay đúng vùng", region)

# 3
c.toggle_video_recording()
flush_timers()
sel.keyPressEvent(types.SimpleNamespace(key=lambda: ac.Qt.Key_Return))
assert started[-1] == ({"left": 0, "top": 0, "width": 1920, "height": 1080}, None)
print("OK 3: Enter -> quay toàn màn hình")

# 4
n = len(started)
c.toggle_video_recording()
flush_timers()
assert sel.isVisible()
c._on_escape()
flush_timers(200)
assert not sel.isVisible() and len(started) == n
print("OK 4: Esc khi chọn vùng -> hủy, không quay")

# 6
r = AppController._logical_to_physical_region(QRect(-50, 1000, 400, 300))
assert r["left"] == 0 and r["top"] >= 0
assert r["top"] + r["height"] <= 1080 and r["left"] + r["width"] <= 1920
print("OK 6: vùng tràn mép -> kẹp vào màn hình", r)

# 7
if cursor_overlay._IS_WIN:
    ov = cursor_overlay.CursorOverlay()
    assert ov.enabled
    ov._last_click_t = time.perf_counter()
    import ctypes
    from ctypes import wintypes
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    frame = np.zeros((120, 120, 4), np.uint8)
    ov.draw(frame, pt.x - 60, pt.y - 60)
    assert frame[:, :, :3].any(), "phải vẽ vòng click/con trỏ lên frame"
    far = np.zeros((50, 50, 4), np.uint8)
    ov.draw(far, pt.x + 5000, pt.y + 5000)
    assert not far.any(), "chuột ngoài vùng -> không vẽ gì"
    ov.close()
    print("OK 7: CursorOverlay vẽ vòng click + con trỏ")
print("=== RECORD REGION + CURSOR OK ===")
