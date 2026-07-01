"""Test thu âm + ghép (mux) audio/video + fallback video-only (headless)."""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# --- 1. Báo môi trường audio ---
from app.recording.audio_recorder import audio_available, mux_audio_video

print("audio_available():", audio_available())
try:
    import sounddevice as sd
    n_in = sum(1 for d in sd.query_devices() if d["max_input_channels"] > 0)
    print("  sounddevice: CÓ, thiết bị input:", n_in)
except Exception as exc:
    print("  sounddevice: KHÔNG (", exc, ")")
try:
    import soundfile  # noqa: F401
    print("  soundfile: CÓ")
except Exception as exc:
    print("  soundfile: KHÔNG (", exc, ")")

import imageio_ffmpeg
print("  ffmpeg:", os.path.basename(imageio_ffmpeg.get_ffmpeg_exe()))

# --- helpers tạo video & wav ngắn ---
import tempfile

import imageio
import numpy as np

tmpdir = tempfile.mkdtemp(prefix="snagtin_audio_test_")


def make_video(path, seconds=1.0, fps=10, size=(240, 320)):
    w = imageio.get_writer(path, fps=fps, codec="libx264", quality=8,
                           macro_block_size=16, ffmpeg_log_level="error")
    n = int(seconds * fps)
    for i in range(n):
        frame = np.full((size[0], size[1], 3), (i * 5) % 255, dtype=np.uint8)
        w.append_data(frame)
    w.close()


def make_wav(path, seconds=1.0, samplerate=44100):
    import soundfile as sf
    t = np.linspace(0, seconds, int(seconds * samplerate), endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, tone, samplerate, subtype="PCM_16")


def has_audio_stream(path):
    """Đọc metadata bằng ffmpeg -> có dòng 'Audio:' nghĩa là có stream audio."""
    import subprocess
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    creationflags = 0x08000000 if os.name == "nt" else 0
    proc = subprocess.run([ffmpeg, "-i", path], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, creationflags=creationflags)
    return b"Audio:" in proc.stdout


# --- 2. Test mux: video + wav -> file cuối có stream audio, tạm bị xoá ---
video_tmp = os.path.join(tmpdir, "clip_video.mp4")
audio_tmp = os.path.join(tmpdir, "clip_audio.wav")
final_out = os.path.join(tmpdir, "clip_final.mp4")
make_video(video_tmp, seconds=1.0)
make_wav(audio_tmp, seconds=1.0)
assert os.path.getsize(video_tmp) > 0 and os.path.getsize(audio_tmp) > 0

ok = mux_audio_video(video_tmp, audio_tmp, final_out)
assert ok, "mux phải thành công"
assert os.path.exists(final_out) and os.path.getsize(final_out) > 0, "file cuối phải tồn tại"
assert has_audio_stream(final_out), "file cuối phải có stream audio"
# Mô phỏng dọn dẹp như controller sau mux thành công.
os.remove(video_tmp)
os.remove(audio_tmp)
assert not os.path.exists(video_tmp) and not os.path.exists(audio_tmp)
print("OK: mux ra MP4 có audio + dọn file tạm")

# --- 3. Fallback: WAV rỗng -> mux thất bại -> giữ video-only ---
video_tmp2 = os.path.join(tmpdir, "clip2_video.mp4")
audio_empty = os.path.join(tmpdir, "clip2_audio.wav")
final_out2 = os.path.join(tmpdir, "clip2_final.mp4")
make_video(video_tmp2, seconds=0.8)
open(audio_empty, "wb").close()  # WAV rỗng 0 byte

ok2 = mux_audio_video(video_tmp2, audio_empty, final_out2)
assert not ok2, "mux với WAV rỗng phải thất bại"
# Controller sẽ fallback: đổi tên video tmp thành file cuối.
if os.path.exists(final_out2):
    os.remove(final_out2)
os.replace(video_tmp2, final_out2)
assert os.path.exists(final_out2) and os.path.getsize(final_out2) > 0
assert not has_audio_stream(final_out2), "video-only không được có audio"
print("OK: fallback WAV rỗng -> video-only hợp lệ, không mất bản ghi")

# --- 4. AudioRecorder fallback API khi không khả dụng ---
if not audio_available():
    from app.recording.audio_recorder import AudioRecorder
    rec = AudioRecorder(os.path.join(tmpdir, "x.wav"))
    try:
        rec.start()
        raised = False
    except Exception:
        raised = True
    assert raised, "thiếu audio: start() phải raise để controller fallback"
    print("OK: thiếu thiết bị -> AudioRecorder.start() raise (controller sẽ video-only)")
else:
    print("OK: môi trường CÓ audio - bỏ qua test nhánh thiếu thiết bị")

# dọn thư mục tạm
import shutil
shutil.rmtree(tmpdir, ignore_errors=True)
print("=== AUDIO RECORDING + MUX OK ===")
