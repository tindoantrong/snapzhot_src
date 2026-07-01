"""Test quay video thật: grab 2s -> MP4 -> thumbnail -> lưu thư viện.

Chạy offscreen. Vì mss cần màn hình thật, dùng vùng nhỏ ở góc (0,0).
"""
import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

import os
import time
import unittest.mock as mock

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication([])

from app.recording.recorder import VideoRecorder
from app.common.paths import videos_dir
from app.library.library_manager import LibraryManager
from PySide6.QtGui import QImage
import imageio
import numpy as np

# ---------- test 1: quay bình thường ----------

out = str(videos_dir() / "test_clip.mp4")
region = {"left": 0, "top": 0, "width": 320, "height": 240}

rec = VideoRecorder(region, out, fps=10)

result = {}
def on_done(path, dur, frames):
    result["path"] = path
    result["dur"] = dur
    result["frames"] = frames
def on_err(msg):
    result["error"] = msg

rec.finished_recording.connect(on_done)
rec.error.connect(on_err)
rec.start()

# Quay ~2 giây rồi dừng.
time.sleep(2)
rec.stop()

# Chờ luồng phát signal finished (xử lý event loop).
loop = QEventLoop()
rec.finished_recording.connect(lambda *a: loop.quit())
rec.error.connect(lambda *a: loop.quit())
QTimer.singleShot(8000, loop.quit)
if not result:
    loop.exec()
rec.wait(3000)

assert "error" not in result, f"Lỗi recorder: {result.get('error')}"
assert "path" in result, "Recorder không phát finished"
assert os.path.exists(out), "File MP4 không tồn tại"
size = os.path.getsize(out)
assert size > 0, "File MP4 rỗng"
print(f"OK: quay {result['frames']} frame, {result['dur']:.1f}s, file {size} bytes")

# Đọc frame đầu làm thumbnail (giống controller)
reader = imageio.get_reader(out)
frame = np.ascontiguousarray(reader.get_data(0))
reader.close()
h, w = frame.shape[0], frame.shape[1]
qimg = QImage(frame.tobytes(), w, h, 3 * w, QImage.Format_RGB888).copy()
assert not qimg.isNull()
print(f"OK: thumbnail từ frame đầu {w}x{h}")

# Lưu vào thư viện như video
lib = LibraryManager()
cap = lib.add_video(out, result["dur"], qimg, w, h, tags="video, test")
assert cap.is_video, "phải là media_type video"
assert cap.thumbnail_path.exists(), "thumbnail video phải được tạo"
got = lib.get(cap.id)
assert got.is_video and got.duration > 0, "đọc lại phải là video có duration"
print(f"OK: lưu video vào thư viện id={cap.id}, duration={got.duration:.1f}s")
lib.delete(cap.id)
lib.close()

# ---------- test 2: lỗi grab -> chỉ error emit, KHÔNG phát finished_recording ----------

out_err = str(videos_dir() / "test_clip_err.mp4")
rec2 = VideoRecorder({"left": 0, "top": 0, "width": 320, "height": 240}, out_err, fps=10)

sig_error = []
sig_finished = []
rec2.error.connect(lambda msg: sig_error.append(msg))
rec2.finished_recording.connect(lambda p, d, f: sig_finished.append((p, d, f)))

# Patch mss.MSS.grab (hoặc mss.mss().grab) để throw sau frame đầu
import mss as _mss_mod
_orig_mss = _mss_mod.mss

class _BrokenMSS:
    """Context manager giả: grab lần đầu bình thường, lần sau throw."""
    def __init__(self):
        self._real = _orig_mss()
        self._calls = 0
    def __enter__(self):
        return self
    def __exit__(self, *a):
        self._real.__exit__(*a)
    def grab(self, region):
        self._calls += 1
        if self._calls > 1:
            raise RuntimeError("mss.grab injected error")
        return self._real.grab(region)

with mock.patch.object(_mss_mod, "mss", _BrokenMSS):
    rec2.start()
    loop2 = QEventLoop()
    rec2.error.connect(lambda *a: loop2.quit())
    rec2.finished_recording.connect(lambda *a: loop2.quit())
    QTimer.singleShot(8000, loop2.quit)
    loop2.exec()
    rec2.wait(3000)

assert len(sig_error) == 1, f"Phải đúng 1 error signal, nhận: {sig_error}"
assert len(sig_finished) == 0, \
    f"finished_recording KHÔNG được emit khi lỗi, nhưng nhận: {sig_finished}"
# Dọn file (có thể tồn tại hoặc không)
if os.path.exists(out_err):
    os.remove(out_err)
print("OK: lỗi grab -> chỉ error emit, finished_recording KHÔNG emit (BUG 1 fixed)")

# ---------- test 3: pause -> duration = active_seconds, KHÔNG phải wall-clock ----------

out_pause = str(videos_dir() / "test_clip_pause.mp4")
fps_test = 10
rec3 = VideoRecorder({"left": 0, "top": 0, "width": 320, "height": 240},
                     out_pause, fps=fps_test)

sig3 = {}
rec3.finished_recording.connect(lambda p, d, f: sig3.update({"dur": d, "frames": f}))
rec3.error.connect(lambda msg: sig3.update({"error": msg}))

rec3.start()
time.sleep(0.5)          # quay 0.5s thực
rec3.set_paused(True)
time.sleep(1.0)          # pause 1s (wall-clock tăng nhưng không ghi)
rec3.set_paused(False)
time.sleep(0.5)          # quay thêm 0.5s thực
rec3.stop()

loop3 = QEventLoop()
rec3.finished_recording.connect(lambda *a: loop3.quit())
rec3.error.connect(lambda *a: loop3.quit())
QTimer.singleShot(8000, loop3.quit)
if not sig3:
    loop3.exec()
rec3.wait(3000)

assert "error" not in sig3, f"Lỗi recorder pause: {sig3.get('error')}"
# active_seconds = frame_count * (1/fps) ≈ 1.0s (0.5 + 0.5)
# wall-clock ≈ 2.0s (0.5 + 1.0 + 0.5); duration phải KHÔNG bằng wall-clock
expected_active = sig3["frames"] / fps_test          # chính xác từ frame_count
assert abs(sig3["dur"] - expected_active) < 0.01, \
    f"duration {sig3['dur']:.3f}s phải = active_seconds ({expected_active:.3f}s)"
assert sig3["dur"] < 1.5, \
    f"duration {sig3['dur']:.3f}s phải nhỏ hơn tổng wall-clock (~2s) (BUG 2 check)"
if os.path.exists(out_pause):
    os.remove(out_pause)
print(f"OK: pause 1s -> duration emit = {sig3['dur']:.2f}s (active only, không wall-clock) (BUG 2 fixed)")

print("=== QUAY VIDEO OK ===")
