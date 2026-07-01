"""Quay video màn hình: chạy trên QThread, grab frame bằng mss, ghi MP4 (H.264).

- Grab vùng/toàn màn theo FPS mục tiêu, đẩy frame qua imageio + ffmpeg.
- Hỗ trợ tạm dừng (pause) / tiếp tục (resume) / dừng (stop).
- Phát signal khi xong (đường dẫn file, thời lượng, số frame).

mss cho frame BGRA; ta chuyển sang RGB (numpy) cho imageio.
"""
from __future__ import annotations

import time

import imageio
import mss
import numpy as np
from PySide6.QtCore import QThread, Signal


class VideoRecorder(QThread):
    finished_recording = Signal(str, float, int)   # path, duration_sec, frame_count
    error = Signal(str)

    def __init__(self, region: dict, output_path: str, fps: int = 15) -> None:
        super().__init__()
        self._region = region            # {left, top, width, height}
        self._output_path = output_path
        self._fps = max(1, int(fps))
        self._running = True
        self._paused = False

    # ---------- điều khiển ----------
    def stop(self) -> None:
        self._running = False

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ---------- vòng quay ----------
    def run(self) -> None:
        frame_interval = 1.0 / self._fps
        frame_count = 0
        start = time.perf_counter()
        active_seconds = 0.0  # thời gian thực sự quay (không tính lúc pause)

        # H.264 yêu cầu kích thước chia hết cho 2; macro_block_size lo phần đệm.
        try:
            writer = imageio.get_writer(
                self._output_path,
                fps=self._fps,
                codec="libx264",
                quality=8,
                macro_block_size=16,
                ffmpeg_log_level="error",
            )
        except Exception as exc:  # ffmpeg/codec lỗi
            self.error.emit(f"Không mở được bộ ghi video: {exc}")
            return

        try:
            with mss.mss() as sct:
                next_t = time.perf_counter()
                while self._running:
                    if self._paused:
                        time.sleep(0.05)
                        next_t = time.perf_counter()
                        continue

                    shot = sct.grab(self._region)
                    frame = np.asarray(shot)          # (h, w, 4) BGRA
                    rgb = frame[:, :, [2, 1, 0]]       # BGRA -> RGB
                    writer.append_data(rgb)
                    frame_count += 1
                    active_seconds += frame_interval

                    # Giữ nhịp FPS: ngủ tới mốc frame kế tiếp.
                    next_t += frame_interval
                    delay = next_t - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                    else:
                        next_t = time.perf_counter()
        except Exception as exc:
            self.error.emit(f"Lỗi khi quay: {exc}")
        finally:
            writer.close()

        duration = time.perf_counter() - start
        self.finished_recording.emit(self._output_path, duration, frame_count)
