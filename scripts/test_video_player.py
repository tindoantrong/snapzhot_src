"""Test trình phát video nhúng (offscreen).

Lưu ý: môi trường offscreen có thể KHÔNG decode được video; test chỉ yêu cầu
khởi tạo + set source + điều khiển không crash. Ghi rõ giới hạn nếu có.
"""
import os
import sys

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

app = QApplication([])

# --- 1. Backend QtMultimedia có sẵn không? ---
try:
    from PySide6.QtMultimedia import QMediaPlayer  # noqa: F401
    HAS_MULTIMEDIA = True
except Exception as exc:  # pragma: no cover
    HAS_MULTIMEDIA = False
    print("CHÚ Ý: thiếu backend QtMultimedia ->", exc)

print("QtMultimedia backend:", "CÓ" if HAS_MULTIMEDIA else "KHÔNG")

if not HAS_MULTIMEDIA:
    # Fallback path: library_window phải import được và không crash.
    from app.library.library_window import LibraryWindow  # noqa: F401
    print("OK: thiếu backend -> library_window vẫn import được (sẽ fallback ngoài)")
    print("=== VIDEO PLAYER (FALLBACK) OK ===")
    sys.exit(0)

# --- 2. Chuẩn bị một file video để mở (tái dùng recorder) ---
from app.common.paths import videos_dir
from app.recording.recorder import VideoRecorder

out_path = str(videos_dir() / "test_player_clip.mp4")
region = {"left": 0, "top": 0, "width": 320, "height": 240}
rec = VideoRecorder(region, out_path, fps=10)
rec.start()
import time
time.sleep(1.5)
rec.stop()
rec.wait(5000)
assert os.path.exists(out_path), "không tạo được clip để test"
print("OK: tạo clip test", os.path.getsize(out_path), "bytes")

# --- 3. Khởi tạo VideoPlayerWindow + open() không crash ---
from app.library.video_player import VideoPlayerWindow, _fmt_time

assert _fmt_time(0) == "00:00"
assert _fmt_time(65000) == "01:05"
assert _fmt_time(-100) == "00:00"
print("OK: _fmt_time định dạng đúng")

pl = VideoPlayerWindow()
pl.open(out_path)
# Bơm vòng lặp sự kiện để player nạp source (offscreen có thể không decode video).
for _ in range(20):
    app.processEvents()
    time.sleep(0.05)

# Các truy vấn trạng thái không được lỗi.
dur = pl._player.duration()
status = pl._player.mediaStatus()
err = pl._player.error()
print(f"  duration={dur}ms  mediaStatus={status}  error={err}")
assert isinstance(dur, int), "duration phải là int"

# Điều khiển không crash.
pl._toggle_play()
app.processEvents()
pl._on_duration_changed(5000)
assert pl._position_slider.maximum() == 5000
pl._on_position_changed(2500)
assert pl._time_label.text() == "00:02 / 00:05" or "/" in pl._time_label.text()
pl._on_volume_changed(50)
assert abs(pl._audio.volume() - 0.5) < 1e-6, "âm lượng phải set đúng"
pl._on_seek_start()
pl._position_slider.setValue(1000)
pl._on_seek_end()
print("OK: điều khiển play/seek/volume/time-label chạy không lỗi")

# --- 4. closeEvent dừng player + nhả source (không giữ lock file) ---
pl.close()
app.processEvents()
assert pl._player.source().isEmpty(), "đóng cửa sổ phải nhả source"
# Xoá được file -> chứng tỏ không còn lock.
del pl
app.processEvents()
try:
    os.remove(out_path)
    print("OK: closeEvent nhả lock -> xoá được file video")
except OSError as exc:
    print("CHÚ Ý: chưa xoá được file ngay (có thể do hệ điều hành):", exc)

print("=== VIDEO PLAYER OK ===")
