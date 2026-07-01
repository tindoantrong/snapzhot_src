"""Overlay chọn vùng chụp: cửa sổ phủ toàn màn hình, mờ tối,
người dùng kéo chuột để chọn hình chữ nhật.

Phát signal region_selected(QRect) với toạ độ MÀN HÌNH ẢO khi chọn xong,
hoặc cancelled() khi nhấn Esc / chuột phải.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class RegionSelector(QWidget):
    region_selected = Signal(QRect)   # QRect theo toạ độ màn hình ảo
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setCursor(Qt.CrossCursor)
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self._dragging = False

        # Phủ toàn bộ vùng ảo (gộp mọi màn hình).
        geo = QRect()
        for screen in QGuiApplication.screens():
            geo = geo.united(screen.geometry())
        self._virtual_origin = geo.topLeft()
        self.setGeometry(geo)

    def start(self) -> None:
        self._origin = None
        self._current = None
        self._dragging = False
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    # ----- chuột -----
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self._finish_cancel()
            return
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or not self._dragging:
            return
        self._dragging = False
        rect = self._selection_rect()
        if rect.width() < 3 or rect.height() < 3:
            self._finish_cancel()
            return
        # Đổi toạ độ widget -> toạ độ màn hình ảo.
        virtual = rect.translated(self._virtual_origin)
        self.hide()
        self.region_selected.emit(virtual)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._finish_cancel()

    def _finish_cancel(self) -> None:
        self.hide()
        self.cancelled.emit()

    def _selection_rect(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    # ----- vẽ overlay -----
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        sel = self._selection_rect()

        # Phủ một lớp tối mờ lên TOÀN overlay. Bắt buộc: cửa sổ layered trong
        # suốt hoàn toàn trên Windows sẽ bị "click-through" (chuột xuyên xuống
        # cửa sổ dưới) -> overlay như không hiện và không kéo chọn được.
        overlay_color = QColor(0, 0, 0, 70)

        if sel.isNull():
            # Chưa kéo: phủ tối toàn bộ để overlay hữu hình và nhận được chuột.
            painter.fillRect(self.rect(), overlay_color)
            return

        # Phủ tối toàn overlay rồi khoét trong suốt đúng vùng chọn (sáng rõ).
        painter.fillRect(self.rect(), overlay_color)
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(sel, Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # Viền gạch gạch quanh vùng chọn.
        pen = QPen(QColor("#1E90FF"), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(sel)

        # Hiển thị kích thước.
        label = f"{sel.width()} x {sel.height()}"
        painter.setPen(QColor("#1E90FF"))
        ty = sel.top() - 8 if sel.top() > 20 else sel.bottom() + 18
        painter.drawText(sel.left(), ty, label)
