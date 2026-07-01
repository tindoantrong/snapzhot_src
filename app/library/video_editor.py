"""Chỉnh sửa nhẹ video bằng ffmpeg (của imageio-ffmpeg): cắt đoạn + bỏ tiếng.

MVP: chỉ Trim (cắt đầu/cuối) và Mute. Cắt có RE-ENCODE (libx264) để chính xác
theo frame thay vì nhảy về keyframe gần nhất. Mọi phụ thuộc bọc try/except để
thiếu ffmpeg thì suy giảm nhẹ nhàng (trả False / None) thay vì crash.
"""
from __future__ import annotations

import os
import subprocess


def _ffmpeg_exe() -> str | None:
    """Đường dẫn ffmpeg kèm theo imageio-ffmpeg (None nếu không có)."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _no_window_flags() -> int:
    """Ẩn cửa sổ console trên Windows khi gọi ffmpeg."""
    return 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW


def export_clip(src_path: str, out_path: str, start_ms: int, end_ms: int,
                mute: bool = False) -> bool:
    """Cắt [start_ms, end_ms] của src_path ra out_path; tùy chọn bỏ tiếng.

    - Dùng -ss trước -i (seek nhanh) + -t (độ dài) để tránh nhập nhằng -to.
    - Re-encode libx264 yuv420p để cắt chính xác frame và tương thích rộng.
    - mute=True -> -an (bỏ luồng tiếng); ngược lại mã hoá tiếng sang aac.
    Trả True nếu chạy xong và file ra hợp lệ (tồn tại, > 0 byte).
    """
    ffmpeg = _ffmpeg_exe()
    if ffmpeg is None:
        return False

    start_s = max(0.0, start_ms / 1000.0)
    end_s = max(0.0, end_ms / 1000.0)
    duration_s = end_s - start_s
    if duration_s <= 0:
        return False

    cmd = [
        ffmpeg, "-y",
        "-ss", f"{start_s:.3f}",
        "-i", src_path,
        "-t", f"{duration_s:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
    ]
    cmd += ["-an"] if mute else ["-c:a", "aac"]
    cmd += [out_path]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_no_window_flags(),
        )
    except Exception:
        return False

    return (proc.returncode == 0
            and os.path.exists(out_path)
            and os.path.getsize(out_path) > 0)


def clip_duration_seconds(path: str) -> float | None:
    """Độ dài (giây) của video, đọc qua imageio. None nếu không đọc được."""
    try:
        import imageio

        reader = imageio.get_reader(path)
        meta = reader.get_meta_data()
        reader.close()
    except Exception:
        return None

    dur = meta.get("duration")
    if dur:
        return float(dur)
    fps, n = meta.get("fps"), meta.get("nframes")
    if fps and n and n != float("inf"):
        return float(n) / float(fps)
    return None
