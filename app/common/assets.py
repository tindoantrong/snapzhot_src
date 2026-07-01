"""Tải icon/asset của app, hoạt động cả khi chạy script lẫn đóng gói EXE."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS                      # thư mục PyInstaller giải nén
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def asset_path(name: str) -> str:
    return os.path.join(_base_dir(), "assets", name)


# Các size PNG rời trong assets/icons/ để QIcon chọn đúng độ phân giải.
_ICON_SIZES = [16, 24, 32, 48, 64, 128, 256, 512]


def app_icon() -> QIcon:
    """QIcon đa độ phân giải: nạp từng size rời nếu có, fallback icon.png 256."""
    icon = QIcon()
    added = False

    # Ưu tiên các bản size rời -> Qt chọn ảnh sắc nét nhất theo từng ngữ cảnh.
    for s in _ICON_SIZES:
        p = os.path.join(_base_dir(), "assets", "icons", f"icon_{s}.png")
        if os.path.exists(p):
            icon.addFile(p)
            added = True

    # Bổ sung bản 256 mặc định (tương thích ngược, cũng làm nguồn scale).
    p256 = asset_path("icon.png")
    if os.path.exists(p256):
        icon.addFile(p256)
        added = True

    return icon if added else _drawn_fallback()


def _drawn_fallback() -> QIcon:
    """Icon dự phòng (chấm tròn đỏ) nếu không tìm thấy file asset."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#FF3B30"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(8, 8, 48, 48)
    p.end()
    return QIcon(pix)
