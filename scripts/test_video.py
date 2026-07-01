"""Test quay video thật: grab 2s -> MP4 -> thumbnail -> lưu thư viện.

Chạy offscreen. Vì mss cần màn hình thật, dùng vùng nhỏ ở góc (0,0).
"""
import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

import time

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication([])

from app.recording.recorder import VideoRecorder
from app.common.paths import videos_dir
from app.library.library_manager import LibraryManager
from PySide6.QtGui import QImage
import imageio
import numpy as np

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
import os
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
print("=== QUAY VIDEO OK ===")
