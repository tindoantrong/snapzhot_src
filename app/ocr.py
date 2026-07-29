"""OCR bằng Claude CLI: gửi ảnh cho claude để trích xuất văn bản.

Yêu cầu: máy đã cài `claude` CLI và đã đăng nhập.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage

_log = logging.getLogger(__name__)


def claude_cli_available() -> bool:
    """Kiểm tra `claude` CLI có sẵn trên PATH không."""
    return shutil.which("claude") is not None


def _ocr_with_claude(image_path: str) -> str:
    """Gọi claude CLI để OCR ảnh, trả về text trích xuất được.

    Raises subprocess.CalledProcessError hoặc FileNotFoundError nếu lỗi.
    """
    prompt = (
        "Extract ALL text from this image. "
        "Return ONLY the extracted text, no explanations, no markdown formatting. "
        "If there is no text, return an empty string."
    )
    with open(image_path, "rb") as f:
        image_data = f.read()
    result = subprocess.run(
        ["claude", "-p", prompt],
        input=image_data,
        capture_output=True,
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"claude exited with code {result.returncode}")
    return result.stdout.decode("utf-8").strip()


def ocr_image(image: QImage) -> str:
    """Lưu QImage ra file tạm, gọi Claude OCR, trả về text."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        if not image.save(tmp_path, "PNG"):
            raise RuntimeError("Không thể lưu ảnh tạm để OCR.")
        return _ocr_with_claude(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


class OcrWorker(QObject):
    """Chạy OCR ở luồng nền, phát kết quả về luồng GUI."""

    finished = Signal(str)   # text trích xuất được
    error = Signal(str)      # thông điệp lỗi

    def __init__(self, image: QImage) -> None:
        super().__init__()
        self._image = image

    @Slot()
    def run(self) -> None:
        try:
            text = ocr_image(self._image)
            self.finished.emit(text)
        except Exception as exc:
            _log.warning("OCR failed: %s", exc)
            self.error.emit(str(exc) or "Lỗi không xác định khi OCR.")
