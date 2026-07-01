"""Test chỉnh sửa nhẹ video: cắt đoạn (trim) + bỏ tiếng (mute) qua ffmpeg.

Trọng tâm: export_clip() cắt ra đúng độ dài yêu cầu. Cần ffmpeg của
imageio-ffmpeg; nếu thiếu thì bỏ qua nhẹ nhàng (không tính là lỗi).
"""
import os
import sys
import time

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

app = QApplication([])

from app.common.paths import videos_dir
from app.library.video_editor import (
    _ffmpeg_exe,
    clip_duration_seconds,
    export_clip,
)

if _ffmpeg_exe() is None:
    print("CHÚ Ý: không có ffmpeg (imageio-ffmpeg) -> bỏ qua test cắt video")
    print("=== VIDEO EDIT (SKIP) OK ===")
    sys.exit(0)

# --- 1. Tạo clip nguồn ~2.5s bằng recorder sẵn có ---
from app.recording.recorder import VideoRecorder

src = str(videos_dir() / "test_edit_src.mp4")
region = {"left": 0, "top": 0, "width": 320, "height": 240}
rec = VideoRecorder(region, src, fps=10)
rec.start()
time.sleep(2.5)
rec.stop()
rec.wait(5000)
assert os.path.exists(src) and os.path.getsize(src) > 0, "không tạo được clip nguồn"

src_dur = clip_duration_seconds(src)
print(f"OK: tạo clip nguồn ~{src_dur:.2f}s ({os.path.getsize(src)} bytes)")
assert src_dur is not None and src_dur > 1.5, "clip nguồn phải đủ dài để cắt"

# --- 2. Cắt đoạn [0.5s, 1.5s] -> kỳ vọng ~1.0s ---
out = str(videos_dir() / "test_edit_clip.mp4")
assert export_clip(src, out, 500, 1500, mute=False), "export_clip phải thành công"
dur = clip_duration_seconds(out)
print(f"OK: cắt [0.5s,1.5s] -> đoạn dài {dur:.2f}s")
assert dur is not None, "phải đọc được độ dài đoạn xuất"
assert abs(dur - 1.0) < 0.4, f"độ dài đoạn cắt phải ~1.0s, nhận {dur:.2f}s"

# --- 3. Cắt kèm bỏ tiếng vẫn ra file hợp lệ với độ dài đúng ---
out_mute = str(videos_dir() / "test_edit_clip_mute.mp4")
assert export_clip(src, out_mute, 1000, 2000, mute=True), "export_clip mute phải OK"
dur_m = clip_duration_seconds(out_mute)
print(f"OK: cắt [1.0s,2.0s] + bỏ tiếng -> đoạn dài {dur_m:.2f}s")
assert dur_m is not None and abs(dur_m - 1.0) < 0.4, \
    f"đoạn mute phải ~1.0s, nhận {dur_m}"

# --- 4. Khoảng không hợp lệ (cuối <= đầu) -> trả False, không tạo rác ---
bad = str(videos_dir() / "test_edit_bad.mp4")
if os.path.exists(bad):
    os.remove(bad)
assert not export_clip(src, bad, 1500, 1500, mute=False), \
    "đoạn rỗng phải trả False"
assert not export_clip(src, bad, 2000, 1000, mute=False), \
    "đoạn ngược (cuối<đầu) phải trả False"
print("OK: khoảng cắt không hợp lệ trả False, không xuất file")

# --- 5. Dọn file tạm ---
for p in (src, out, out_mute, bad):
    try:
        if os.path.exists(p):
            os.remove(p)
    except OSError:
        pass

print("=== VIDEO EDIT OK ===")
