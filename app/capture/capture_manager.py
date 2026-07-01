"""Chụp màn hình bằng mss và trả về QImage.

Hỗ trợ:
- capture_fullscreen(): chụp toàn bộ vùng ảo (mọi màn hình ghép lại).
- capture_region(x, y, w, h): chụp một vùng theo toạ độ màn hình ảo.

mss cho ảnh BGRA; ta chuyển sang QImage Format_RGB32.
"""
from __future__ import annotations

import mss
from PySide6.QtGui import QImage


def _grab_to_qimage(monitor: dict) -> QImage:
    with mss.MSS() as sct:
        shot = sct.grab(monitor)
    # mss trả raw BGRA. QImage Format_ARGB32 trên little-endian đọc đúng thứ tự BGRA.
    img = QImage(
        bytes(shot.bgra),
        shot.width,
        shot.height,
        shot.width * 4,
        QImage.Format_ARGB32,
    )
    # copy() để tách khỏi buffer của mss (buffer bị giải phóng sau khối with).
    return img.convertToFormat(QImage.Format_RGB32).copy()


def virtual_screen_geometry() -> dict:
    """Trả về dict {left, top, width, height} của toàn bộ vùng ảo (monitor[0])."""
    with mss.MSS() as sct:
        m = sct.monitors[0]
        return {"left": m["left"], "top": m["top"],
                "width": m["width"], "height": m["height"]}


def capture_fullscreen() -> QImage:
    """Chụp toàn bộ tất cả màn hình."""
    return _grab_to_qimage(virtual_screen_geometry())


def capture_region(x: int, y: int, w: int, h: int) -> QImage:
    """Chụp một vùng hình chữ nhật theo toạ độ màn hình ảo."""
    if w <= 0 or h <= 0:
        raise ValueError("Kích thước vùng chụp không hợp lệ")
    return _grab_to_qimage({"left": x, "top": y, "width": w, "height": h})
