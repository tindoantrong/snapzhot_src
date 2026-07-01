"""Thu âm micro ra file WAV tạm, để ghép (mux) với video thành MP4 có tiếng.

Dùng sounddevice (PortAudio) + soundfile. Mọi import bọc try/except để khi
thiếu thư viện / PortAudio / thiết bị input thì tính năng suy giảm nhẹ nhàng:
audio_available() trả False và luồng quay video-only vẫn chạy y nguyên.

Hàm mux_audio_video() ghép audio+video bằng ffmpeg của imageio-ffmpeg.
"""
from __future__ import annotations

import os
import subprocess

# Import phụ thuộc nền tảng có fallback.
try:
    import sounddevice as sd
    import soundfile as sf

    _HAS_AUDIO_LIBS = True
except Exception:  # pragma: no cover - chỉ chạy khi thiếu thư viện
    sd = None
    sf = None
    _HAS_AUDIO_LIBS = False


def audio_available() -> bool:
    """True nếu có thể thu âm: có thư viện + PortAudio + ít nhất 1 thiết bị input."""
    if not _HAS_AUDIO_LIBS:
        return False
    try:
        devices = sd.query_devices()
        return any(d["max_input_channels"] > 0 for d in devices)
    except Exception:
        return False


class AudioRecorder:
    """Thu mic ra WAV. Callback của InputStream ghi liên tục vào file.

    Hỗ trợ pause (bỏ ghi block để đồng bộ với video khi tạm dừng) và stop.
    """

    def __init__(self, output_path: str,
                 samplerate: int | None = None, channels: int = 1) -> None:
        self._output_path = output_path
        self._samplerate = samplerate
        self._channels = channels
        self._paused = False
        self._stream = None
        self._file = None
        self._frames_written = 0

    def start(self) -> None:
        if not _HAS_AUDIO_LIBS:
            raise RuntimeError("Thiếu sounddevice/soundfile")
        # Lấy samplerate mặc định của thiết bị input nếu chưa chỉ định.
        if self._samplerate is None:
            info = sd.query_devices(kind="input")
            self._samplerate = int(info["default_samplerate"])

        self._file = sf.SoundFile(
            self._output_path, mode="w",
            samplerate=self._samplerate, channels=self._channels,
            subtype="PCM_16",
        )

        def _callback(indata, frames, time_info, status) -> None:
            # Khi pause thì bỏ ghi block hiện tại (đồng bộ với video pause).
            if self._paused or self._file is None:
                return
            self._file.write(indata.copy())
            self._frames_written += frames

        self._stream = sd.InputStream(
            samplerate=self._samplerate,
            channels=self._channels,
            callback=_callback,
        )
        self._stream.start()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        if self._file is not None:
            try:
                self._file.close()
            finally:
                self._file = None

    @property
    def frames_written(self) -> int:
        return self._frames_written

    @property
    def has_audio(self) -> bool:
        return self._frames_written > 0


def mux_audio_video(video_path: str, audio_path: str, out_path: str) -> bool:
    """Ghép luồng video + audio thành out_path bằng ffmpeg (copy video, aac audio).

    Trả True nếu thành công và file ra hợp lệ. Không re-encode video (-c:v copy)
    nên nhanh; -shortest cắt theo luồng ngắn hơn để giảm lệch.
    """
    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return False

    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        out_path,
    ]
    # Ẩn cửa sổ console trên Windows.
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x08000000  # CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:
        return False

    return (proc.returncode == 0
            and os.path.exists(out_path)
            and os.path.getsize(out_path) > 0)
