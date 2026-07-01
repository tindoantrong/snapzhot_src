"""Overlay chọn CỬA SỔ để chụp: phủ toàn vùng ảo, di chuột tới đâu thì
highlight khung cửa sổ top-level dưới con trỏ; click trái để chọn.

Phát signal window_selected(QRect) với toạ độ MÀN HÌNH ẢO khi chọn xong,
hoặc cancelled() khi nhấn Esc / chuột phải / chọn vào vùng trống.

Phụ thuộc nền tảng: dùng win32gui (pywin32) trên Windows để xác định cửa sổ.
Nếu thiếu pywin32 hoặc không phải Windows, tính năng vô hiệu hoá nhẹ nhàng:
window_capture_available() trả False và overlay sẽ tự huỷ ngay khi start().
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

# Import phụ thuộc nền tảng có fallback: thiếu pywin32 không được làm app crash.
try:
    import win32con
    import win32gui

    _HAS_WIN32 = True
except Exception:  # pragma: no cover - chỉ chạy khi thiếu pywin32
    win32con = None
    win32gui = None
    _HAS_WIN32 = False


def window_capture_available() -> bool:
    """True nếu có thể chụp theo cửa sổ (Windows + pywin32)."""
    return _HAS_WIN32


def window_rect_at_point(x: int, y: int, exclude_hwnd: int = 0) -> QRect | None:
    """Trả về QRect (toạ độ màn hình ảo) của cửa sổ top-level NHÌN THẤY nằm
    trên cùng tại điểm (x, y), bỏ qua cửa sổ exclude_hwnd (overlay của app).

    Trả None nếu không có win32 hoặc không tìm thấy cửa sổ phù hợp.

    Vì overlay của app phủ lên trên cùng nên không thể dùng trực tiếp
    WindowFromPoint (sẽ luôn ra overlay). Thay vào đó duyệt mọi cửa sổ
    top-level theo Z-order (EnumWindows trả từ trên xuống dưới) và lấy cửa
    sổ hợp lệ đầu tiên có khung chứa điểm.
    """
    if not _HAS_WIN32:
        return None

    matches: list[QRect] = []

    def _cb(hwnd, _ctx) -> bool:
        try:
            if hwnd == exclude_hwnd:
                return True
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.IsIconic(hwnd):  # bị thu nhỏ
                return True
            # Bỏ cửa sổ công cụ ẩn / không tiêu đề (background system windows).
            if not win32gui.GetWindowText(hwnd):
                return True
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return True
            rect = QRect(left, top, w, h)
            if rect.contains(x, y):
                matches.append(rect)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        return None

    # EnumWindows trả theo Z-order từ trên xuống -> phần tử đầu là trên cùng.
    return matches[0] if matches else None


class WindowSelector(QWidget):
    window_selected = Signal(QRect)   # QRect theo toạ độ màn hình ảo
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self._hover_rect: QRect | None = None  # toạ độ widget (để vẽ)

        # Phủ toàn bộ vùng ảo (gộp mọi màn hình).
        geo = QRect()
        for screen in QGuiApplication.screens():
            geo = geo.united(screen.geometry())
        self._virtual_origin = geo.topLeft()
        self.setGeometry(geo)

    def start(self) -> None:
        # Thiếu pywin32 -> huỷ nhẹ nhàng, không hiện overlay vô dụng.
        if not _HAS_WIN32:
            self.cancelled.emit()
            return
        self._hover_rect = None
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def _own_hwnd(self) -> int:
        try:
            return int(self.winId())
        except Exception:
            return 0

    def _detect(self, global_x: int, global_y: int) -> QRect | None:
        """Tìm khung cửa sổ dưới con trỏ (toạ độ màn hình ảo)."""
        return window_rect_at_point(global_x, global_y, self._own_hwnd())

    # ----- chuột -----
    def mouseMoveEvent(self, event) -> None:
        gp = event.globalPosition().toPoint()
        rect = self._detect(gp.x(), gp.y())
        # Đổi toạ độ màn hình ảo -> toạ độ widget để vẽ highlight.
        self._hover_rect = rect.translated(-self._virtual_origin) if rect else None
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self._finish_cancel()
            return
        if event.button() == Qt.LeftButton:
            gp = event.globalPosition().toPoint()
            rect = self._detect(gp.x(), gp.y())
            self.hide()
            if rect is not None and rect.width() > 0 and rect.height() > 0:
                self.window_selected.emit(rect)
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._finish_cancel()

    def _finish_cancel(self) -> None:
        self.hide()
        self.cancelled.emit()

    # ----- vẽ overlay -----
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        overlay = QColor(0, 0, 0, 120)  # nền tối mờ
        full = self.rect()
        sel = self._hover_rect

        if sel is None or sel.isNull():
            painter.fillRect(full, overlay)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(full, Qt.AlignCenter,
                             "Di chuột tới cửa sổ cần chụp rồi bấm chọn\n"
                             "(Esc / chuột phải để huỷ)")
            return

        # Tối phần ngoài khung cửa sổ, giữ trong suốt phần khung.
        painter.fillRect(QRect(full.left(), full.top(), full.width(), sel.top()), overlay)
        painter.fillRect(QRect(full.left(), sel.bottom(), full.width(),
                               full.bottom() - sel.bottom()), overlay)
        painter.fillRect(QRect(full.left(), sel.top(), sel.left(), sel.height()), overlay)
        painter.fillRect(QRect(sel.right(), sel.top(), full.right() - sel.right(),
                               sel.height()), overlay)

        painter.setPen(QPen(QColor("#1E90FF"), 3))
        painter.drawRect(sel)

        label = f"{sel.width()} x {sel.height()}"
        painter.setPen(QColor("#FFFFFF"))
        ty = sel.top() - 8 if sel.top() > 20 else sel.bottom() + 18
        painter.drawText(sel.left(), ty, label)
