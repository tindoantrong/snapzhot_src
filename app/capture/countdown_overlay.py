"""Overlay đếm ngược cho chụp hẹn giờ: một vòng tròn mờ với số to ở giữa
màn hình chính. Không nhận chuột (click xuyên qua) để không cản thao tác.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CountdownOverlay(QWidget):
    _SIZE = 220

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._value = 0
        self.resize(self._SIZE, self._SIZE)

    def show_count(self, value: int) -> None:
        """Hiển thị số đếm hiện tại và đưa overlay ra giữa màn hình chính."""
        self._value = value
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            self.move(geo.center().x() - self._SIZE // 2,
                      geo.center().y() - self._SIZE // 2)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.setPen(QPen(QColor("#1E90FF"), 5))
        painter.drawEllipse(self.rect().adjusted(6, 6, -6, -6))

        painter.setPen(QColor("#FFFFFF"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(96)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, str(self._value))
