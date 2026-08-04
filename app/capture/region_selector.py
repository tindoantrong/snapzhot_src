"""Overlay chọn vùng chụp: cửa sổ phủ toàn màn hình, mờ tối,
người dùng kéo chuột để chọn hình chữ nhật.

Phát signal region_selected(QRect) với toạ độ MÀN HÌNH ẢO khi chọn xong,
hoặc cancelled() khi nhấn Esc / chuột phải.

Chế độ đóng băng (frozen_bg): nếu start() nhận một QImage chụp toàn màn hình,
overlay hiển thị ảnh đó thay vì nền trong suốt. Khi chọn xong, cắt vùng từ ảnh
đóng băng và phát image_captured(QImage) — không chụp lại màn hình thật.
Giải quyết bug: menu xổ ra trên web bị đóng khi overlay lấy focus.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class RegionSelector(QWidget):
    region_selected = Signal(QRect)   # QRect theo toạ độ màn hình ảo (chế độ thường)
    image_captured = Signal(QImage)   # ảnh đã cắt (chế độ đóng băng)
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
        self._frozen_image: QImage | None = None   # ảnh gốc (để cắt)
        self._frozen_pixmap: QPixmap | None = None  # pixmap (để vẽ nhanh)

        # Phủ toàn bộ vùng ảo (gộp mọi màn hình).
        geo = QRect()
        for screen in QGuiApplication.screens():
            geo = geo.united(screen.geometry())
        self._virtual_origin = geo.topLeft()
        self.setGeometry(geo)

    def start(self, frozen_bg: QImage | None = None) -> None:
        self._origin = None
        self._current = None
        self._dragging = False
        if frozen_bg is not None:
            self._frozen_image = frozen_bg
            self._frozen_pixmap = QPixmap.fromImage(frozen_bg)
        else:
            self._frozen_image = None
            self._frozen_pixmap = None
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

        if self._frozen_image is not None:
            # Chế độ đóng băng: cắt vùng từ ảnh đã chụp sẵn.
            # Widget coords → image coords (xử lý DPI: image có thể lớn hơn widget).
            img_w = self._frozen_image.width()
            img_h = self._frozen_image.height()
            wid_w = max(self.width(), 1)
            wid_h = max(self.height(), 1)
            sx = img_w / wid_w
            sy = img_h / wid_h
            cropped = self._frozen_image.copy(
                int(rect.x() * sx), int(rect.y() * sy),
                int(rect.width() * sx), int(rect.height() * sy),
            )
            self._frozen_image = None
            self._frozen_pixmap = None
            self.hide()
            self.image_captured.emit(cropped)
        else:
            # Chế độ thường: phát toạ độ màn hình ảo để chụp live.
            virtual = rect.translated(self._virtual_origin)
            self.hide()
            self.region_selected.emit(virtual)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._finish_cancel()

    def _finish_cancel(self) -> None:
        self._frozen_image = None
        self._frozen_pixmap = None
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
        overlay_color = QColor(0, 0, 0, 70)

        if self._frozen_pixmap is not None:
            # Chế độ đóng băng: vẽ ảnh chụp sẵn làm nền.
            painter.drawPixmap(self.rect(), self._frozen_pixmap)
            if sel.isNull():
                painter.fillRect(self.rect(), overlay_color)
                return
            # Phủ tối 4 dải xung quanh vùng chọn, giữ vùng chọn sáng rõ.
            w, h = self.width(), self.height()
            painter.fillRect(0, 0, w, sel.top(), overlay_color)
            painter.fillRect(0, sel.bottom() + 1, w, h - sel.bottom() - 1, overlay_color)
            painter.fillRect(0, sel.top(), sel.left(), sel.height(), overlay_color)
            painter.fillRect(sel.right() + 1, sel.top(), w - sel.right() - 1, sel.height(), overlay_color)
        else:
            # Chế độ thường: overlay trong suốt, khoét vùng chọn.
            if sel.isNull():
                painter.fillRect(self.rect(), overlay_color)
                return
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
