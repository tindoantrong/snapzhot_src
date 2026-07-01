"""QC ESC2 — kiểm thử Esc hủy countdown / dừng recording (offscreen, không cần hook thật).

Mock module `keyboard` để `_register_escape`/`_unregister_escape` chạy được mà không
phụ thuộc lib/quyền admin. Phần bắt Esc TOÀN CỤC THẬT (user ở app khác) chỉ verify
được ở phiên tương tác thật — xem checklist trong report, KHÔNG giả lập low-level hook.
"""
import os
import sys
import types

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


# --- Mock `keyboard`: ghi nhận add/remove hotkey, trả handle giả ---
class _FakeKeyboard(types.ModuleType):
    def __init__(self):
        super().__init__("keyboard")
        self.added = []      # list (key, callback)
        self.removed = []    # list handle đã gỡ
        self._next = 0

    def add_hotkey(self, key, callback, *a, **k):
        self._next += 1
        h = ("esc-handle", self._next)
        self.added.append((key, callback, h))
        return h

    def remove_hotkey(self, handle):
        self.removed.append(handle)


fake_kb = _FakeKeyboard()
sys.modules["keyboard"] = fake_kb

app = QApplication([])

from app.app_controller import AppController
from app.recording.record_bar import RecordBar


# Recorder giả: chỉ cần .stop() để stop_recording chạy được.
class FakeRecorder:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


def fresh_controller():
    c = AppController()
    # Chặn side-effect ghi DB/mở editor/tray để test sạch.
    c._do_fullscreen_capture = lambda: captured.append("shot")
    c.library.add_video = lambda *a, **k: None
    c.library_window.refresh = lambda: None
    c.tray.showMessage = lambda *a, **k: None
    return c


captured: list = []


# ===== 1. Countdown cancel =====
captured.clear()
c = fresh_controller()
c.capture_fullscreen_delayed(3)
assert c._delay_timer.isActive(), "đếm ngược phải đang chạy"
assert c.countdown_overlay.isVisible(), "overlay đếm ngược phải hiện"
assert c._esc_handle is not None, "phải đăng ký Esc khi bắt đầu countdown"
n_added = len(fake_kb.added)
assert n_added >= 1 and fake_kb.added[-1][0] == "esc", "hotkey đăng ký phải là 'esc'"

c._on_escape()
assert not c._delay_timer.isActive(), "Esc phải dừng timer đếm ngược"
assert not c.countdown_overlay.isVisible(), "Esc phải ẩn overlay"
assert c._esc_handle is None, "Esc phải gỡ hotkey (không rò)"
assert len(fake_kb.removed) >= 1, "phải gọi remove_hotkey khi hủy"
assert captured == [], "hủy countdown thì KHÔNG được chụp"
print("OK 1: Esc khi đếm ngược -> hủy, không chụp, gỡ hotkey")


# ===== 2. Recording stop + tính loại trừ countdown/recording =====
c = fresh_controller()
fake = FakeRecorder()
c._recorder = fake
c._recording = True
c._register_escape()
assert c._esc_handle is not None
bar_hidden_before = c.record_bar.isVisible()

c._on_escape()
assert fake.stopped, "Esc khi đang quay phải gọi recorder.stop()"
assert not c.record_bar.isVisible(), "stop_recording phải ẩn record_bar (finish)"
assert c._esc_handle is None, "stop_recording phải gỡ hotkey"
print("OK 2: Esc khi đang quay -> stop_recording (recorder.stop + bar ẩn + gỡ hotkey)")

# Loại trừ: countdown active thì Esc CHỈ hủy countdown, KHÔNG đụng recording.
c = fresh_controller()
fake2 = FakeRecorder()
c._recorder = fake2
c._recording = True            # giả như vừa quay
c.capture_fullscreen_delayed(3)  # nhưng countdown đang chạy -> ưu tiên
c._on_escape()
assert not c._delay_timer.isActive(), "countdown phải bị hủy"
assert not fake2.stopped, "countdown active -> KHÔNG được dừng recording"
print("OK 2b: countdown active -> Esc chỉ hủy countdown, không đụng recording")


# ===== 3. RecordBar Esc local =====
bar = RecordBar()
stopped_flags = []
bar.stopped.connect(lambda: stopped_flags.append(True))
bar.start()
assert bar.isVisible(), "bar phải hiện sau start()"
assert bar._timer.isActive(), "đồng hồ phải chạy"
ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
bar.keyPressEvent(ev)
assert stopped_flags == [True], "Esc trên RecordBar phải phát stopped"
assert not bar.isVisible(), "Esc phải ẩn bar (finish)"
assert not bar._timer.isActive(), "Esc phải dừng đồng hồ (finish)"
print("OK 3: RecordBar Esc local -> stopped + finish (ẩn + dừng timer)")


# ===== 4. Lifecycle: mọi điểm kết thúc đều gỡ hotkey =====
# 4a. stop_recording đã cover ở mục 2. Kiểm _on_recording_finished + _on_recording_error.
c = fresh_controller()
c._recording = True
c._register_escape()
assert c._esc_handle is not None
c._on_recording_finished("nonexistent.mp4", 1.0, 10)
assert c._esc_handle is None, "_on_recording_finished phải gỡ hotkey"
assert not c._recording, "_on_recording_finished phải tắt cờ recording"
print("OK 4a: _on_recording_finished -> gỡ hotkey")

c = fresh_controller()
c._recording = True
c._register_escape()
assert c._esc_handle is not None
c._on_recording_error("loi gia lap")
assert c._esc_handle is None, "_on_recording_error phải gỡ hotkey"
assert not c._recording, "_on_recording_error phải tắt cờ recording"
print("OK 4b: _on_recording_error -> gỡ hotkey")

# 4c. Gọi _unregister_escape khi không có handle phải êm (idempotent).
c = fresh_controller()
assert c._esc_handle is None
c._unregister_escape()  # không nên ném lỗi
print("OK 4c: _unregister_escape khi rỗng -> no-op an toàn")


# ===== 5. reload_global_hotkeys khi đang quay -> đăng ký lại Esc (BUG2) =====
# remove_all_hotkeys() xoá CẢ Esc → nếu không đăng ký lại, Esc dừng-quay chết câm.
c = fresh_controller()
c._recording = True
c._register_escape()
old_handle = c._esc_handle
assert old_handle is not None, "phải có Esc handle trước reload"
n_esc_before = sum(1 for k in fake_kb.added if k[0] == "esc")

c.reload_global_hotkeys()
assert c._esc_handle is not None, "đang quay -> phải đăng ký lại Esc sau reload"
assert c._esc_handle != old_handle, "handle Esc phải là handle MỚI (không stale)"
n_esc_after = sum(1 for k in fake_kb.added if k[0] == "esc")
assert n_esc_after == n_esc_before + 1, "phải gọi add_hotkey('esc') lại đúng 1 lần"
print("OK 5: reload_global_hotkeys khi đang quay -> Esc đăng ký lại (handle mới)")

# 5b. reload khi KHÔNG có tiến trình -> không đăng ký Esc (tránh rò hotkey thừa).
c = fresh_controller()
assert c._esc_handle is None and not c._recording and not c._delay_timer.isActive()
n_esc_before = sum(1 for k in fake_kb.added if k[0] == "esc")
c.reload_global_hotkeys()
assert c._esc_handle is None, "không tiến trình -> KHÔNG đăng ký Esc"
n_esc_after = sum(1 for k in fake_kb.added if k[0] == "esc")
assert n_esc_after == n_esc_before, "không tiến trình -> không add Esc thừa"
print("OK 5b: reload khi rảnh -> không đăng ký Esc thừa")


print("=== ESCAPE (countdown cancel / recording stop) OK ===")
