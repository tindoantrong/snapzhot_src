"""Thanh điều khiển quay video nổi: chấm đỏ nhấp nháy, đồng hồ, nút Tạm dừng / Dừng.

Là widget frameless, luôn trên cùng, đặt ở giữa-trên màn hình chính.
Phát signal pause_toggled(bool) và stopped() cho controller xử lý.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class RecordBar(QWidget):
    pause_toggled = Signal(bool)   # True = đang tạm dừng
    stopped = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._elapsed = 0
        self._paused = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._blink = QTimer(self)
        self._blink.setInterval(600)
        self._blink.timeout.connect(self._toggle_dot)
        self._dot_on = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color:#FF3B30; font-size:18px;")
        layout.addWidget(self._dot)

        self._time_label = QLabel("00:00")
        self._time_label.setStyleSheet("color:white; font-size:14px; font-weight:bold;")
        layout.addWidget(self._time_label)

        self._pause_btn = QPushButton("⏸ Tạm dừng")
        self._pause_btn.clicked.connect(self._on_pause)
        layout.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("⏹ Dừng")
        self._stop_btn.clicked.connect(self._on_stop)
        layout.addWidget(self._stop_btn)

        self.setStyleSheet(
            "QWidget { background:#222; border-radius:8px; }"
            "QPushButton { background:#444; color:white; border:none;"
            " padding:4px 10px; border-radius:4px; }"
            "QPushButton:hover { background:#555; }"
        )

    def start(self) -> None:
        self._elapsed = 0
        self._paused = False
        self._pause_btn.setText("⏸ Tạm dừng")
        self._time_label.setText("00:00")
        self._timer.start()
        self._blink.start()
        self._reposition()
        self.show()
        self.raise_()

    def finish(self) -> None:
        self._timer.stop()
        self._blink.stop()
        self.hide()

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        self.adjustSize()
        x = screen.left() + (screen.width() - self.width()) // 2
        self.move(x, screen.top() + 12)

    def _tick(self) -> None:
        if not self._paused:
            self._elapsed += 1
            m, s = divmod(self._elapsed, 60)
            self._time_label.setText(f"{m:02d}:{s:02d}")

    def _toggle_dot(self) -> None:
        if self._paused:
            self._dot.setStyleSheet("color:#888; font-size:18px;")
            return
        self._dot_on = not self._dot_on
        color = "#FF3B30" if self._dot_on else "#660000"
        self._dot.setStyleSheet(f"color:{color}; font-size:18px;")

    def _on_pause(self) -> None:
        self._paused = not self._paused
        self._pause_btn.setText("▶ Tiếp tục" if self._paused else "⏸ Tạm dừng")
        self.pause_toggled.emit(self._paused)

    def _on_stop(self) -> None:
        self.finish()
        self.stopped.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._on_stop()
            return
        super().keyPressEvent(event)
