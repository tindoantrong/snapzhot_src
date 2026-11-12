"""Khung viền đỏ quanh vùng đang quay (chỉ khi quay một vùng, không phải toàn màn).

Viền vẽ BÊN NGOÀI vùng quay (cách 1px) nên không lọt vào video. Cửa sổ trong
suốt, bỏ qua chuột (click xuyên qua) — chỉ để người dùng biết đang quay chỗ nào.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

_GAP = 1      # khoảng hở giữa vùng quay và viền
_WIDTH = 3    # độ dày viền


class RecordFrame(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._paused = False

    def show_around(self, rect: QRect) -> None:
        """rect: vùng quay theo toạ độ Qt (pixel logic)."""
        m = _GAP + _WIDTH
        self._paused = False
        self.setGeometry(rect.adjusted(-m, -m, m, m))
        self.show()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        color = QColor("#9AA0A6") if self._paused else QColor("#FF3B30")
        pen = QPen(color, _WIDTH)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        half = _WIDTH / 2
        painter.drawRect(self.rect().toRectF().adjusted(half, half, -half, -half))
