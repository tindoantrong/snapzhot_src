"""Overlay chọn CỬA SỔ để chụp: phủ toàn vùng ảo, di chuột tới đâu thì
highlight khung cửa sổ top-level dưới con trỏ; click trái để chọn.

Phát signal window_selected(QRect) với toạ độ MÀN HÌNH ẢO khi chọn xong,
hoặc cancelled() khi nhấn Esc / chuột phải / chọn vào vùng trống.

Ngoài overlay, module còn cung cấp active_window_target() — tìm cửa sổ ĐANG
ACTIVE mà không cần chuột (dùng cho phím tắt "chụp app đang dùng").

Phụ thuộc nền tảng: dùng win32gui (pywin32) trên Windows để xác định cửa sổ.
Nếu thiếu pywin32 hoặc không phải Windows, tính năng vô hiệu hoá nhẹ nhàng:
window_capture_available() trả False và overlay sẽ tự huỷ ngay khi start().

LƯU Ý TOẠ ĐỘ: mọi rect ở đây là PIXEL VẬT LÝ (Win32 + mss cùng hệ quy chiếu
vì mss bật SetProcessDpiAwareness). KHÔNG trộn với toạ độ Qt (pixel logic).
"""
from __future__ import annotations

import os

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


# ---------------------------------------------------------------------------
# Nền tảng: duyệt Z-order + lọc cửa sổ hợp lệ
#
# QUAN TRỌNG cho test: _is_capturable_window / _window_rect / _iter_zorder chỉ
# được phép gọi 6 API mà scripts/test_window_zorder.py monkeypatch (GetTopWindow,
# GetWindow, IsWindowVisible, IsIconic, GetWindowText, GetWindowRect). Mọi kiểm
# tra nặng hơn (pid, cloak, class) phải nằm ở hàm riêng bên dưới.
# ---------------------------------------------------------------------------

def _window_rect(hwnd: int) -> QRect | None:
    """QRect thô theo GetWindowRect; None nếu lỗi hoặc kích thước rỗng."""
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    except Exception:
        return None
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0:
        return None
    return QRect(left, top, w, h)


def _is_capturable_window(hwnd: int, exclude_hwnd: int = 0) -> bool:
    """Cửa sổ top-level đáng chụp: khác exclude_hwnd, đang hiện, không thu nhỏ,
    có tiêu đề. Lỗi truy cập → False (bỏ qua cửa sổ đó)."""
    if not hwnd or hwnd == exclude_hwnd:
        return False
    try:
        return bool(
            win32gui.IsWindowVisible(hwnd)
            and not win32gui.IsIconic(hwnd)
            and win32gui.GetWindowText(hwnd)
        )
    except Exception:
        return False


def _iter_zorder():
    """Sinh hwnd từ trên xuống theo Z-order ĐƯỢC ĐẢM BẢO bởi
    GetTopWindow(0) + GetWindow(GW_HWNDNEXT) (EnumWindows KHÔNG đảm bảo Z-order).
    Dừng im lặng khi gặp lỗi."""
    try:
        hwnd = win32gui.GetTopWindow(0)  # 0 = desktop; cửa sổ trên cùng nhất
    except Exception:
        return
    while hwnd:
        yield hwnd
        try:
            hwnd = win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)
        except Exception:
            return


def window_rect_at_point(x: int, y: int, exclude_hwnd: int = 0) -> QRect | None:
    """Trả về QRect (toạ độ màn hình ảo) của cửa sổ top-level NHÌN THẤY nằm
    trên cùng tại điểm (x, y), bỏ qua cửa sổ exclude_hwnd (overlay của app).

    Trả None nếu không có win32 hoặc không tìm thấy cửa sổ phù hợp.

    Vì overlay của app phủ lên trên cùng nên không thể dùng trực tiếp
    WindowFromPoint (sẽ luôn ra overlay). Thay vào đó duyệt theo Z-order:
    trả về cửa sổ hợp lệ ĐẦU TIÊN (topmost) có khung chứa điểm.
    """
    if not _HAS_WIN32:
        return None

    for hwnd in _iter_zorder():
        if not _is_capturable_window(hwnd, exclude_hwnd):
            continue
        rect = _window_rect(hwnd)
        if rect is not None and rect.contains(x, y):
            return rect

    return None


# ---------------------------------------------------------------------------
# Chụp cửa sổ ĐANG ACTIVE (không cần chuột) — dùng cho phím tắt
# ---------------------------------------------------------------------------

_DWMWA_EXTENDED_FRAME_BOUNDS = 9
_DWMWA_CLOAKED = 14

# Cửa sổ của shell: chụp chúng không có nghĩa gì khi báo bug.
# KHÔNG chặn ApplicationFrameWindow — đó là cửa sổ THẬT của app UWP;
# bản ma của chúng đã bị _is_cloaked loại.
_SHELL_CLASSES = frozenset({
    "Progman",                      # desktop
    "WorkerW",                      # lớp nền desktop
    "Shell_TrayWnd",                # thanh taskbar
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",   # Start menu / Search
})


def _is_own_process(hwnd: int) -> bool:
    """Cửa sổ này có thuộc chính app không (đừng tự chụp mình)."""
    try:
        import win32process
        return win32process.GetWindowThreadProcessId(hwnd)[1] == os.getpid()
    except Exception:
        return False


def _dwm_attribute(hwnd: int, attr: int, ctype_obj) -> bool:
    """Gọi DwmGetWindowAttribute vào ctype_obj. True nếu thành công (HRESULT 0)."""
    try:
        import ctypes
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.c_void_p(int(hwnd)),
            ctypes.c_uint(attr),
            ctypes.byref(ctype_obj),
            ctypes.sizeof(ctype_obj),
        )
        return hr == 0
    except Exception:
        return False


def _is_cloaked(hwnd: int) -> bool:
    """Cửa sổ bị DWM "cloak": app UWP đã tắt nhưng còn hwnd ma, hoặc cửa sổ
    nằm ở desktop ảo khác. Chúng vẫn qua được IsWindowVisible → phải lọc riêng."""
    try:
        import ctypes
        value = ctypes.c_int(0)
        return _dwm_attribute(hwnd, _DWMWA_CLOAKED, value) and value.value != 0
    except Exception:
        return False


def _is_shell_window(hwnd: int) -> bool:
    try:
        return win32gui.GetClassName(hwnd) in _SHELL_CLASSES
    except Exception:
        return False


def _extended_frame_rect(hwnd: int) -> QRect | None:
    """Khung THẬT của cửa sổ theo DWM (đã bỏ viền resize vô hình ~7px mỗi bên
    mà GetWindowRect vẫn tính). None nếu DWM không trả lời (Win7, lỗi quyền)."""
    try:
        import ctypes

        class _RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        r = _RECT()
        if not _dwm_attribute(hwnd, _DWMWA_EXTENDED_FRAME_BOUNDS, r):
            return None
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            return None
        return QRect(r.left, r.top, w, h)
    except Exception:
        return None


def _clamp_to_virtual(rect: QRect) -> QRect | None:
    """Cắt rect về trong vùng ảo (cửa sổ maximize thường lố vài px).

    Dùng capture_manager.virtual_screen_geometry() — pixel VẬT LÝ, cùng hệ với
    Win32. KHÔNG dùng QGuiApplication.screens() (pixel logic → lệch khi scale).
    """
    try:
        from . import capture_manager
        vg = capture_manager.virtual_screen_geometry()
        virtual = QRect(vg["left"], vg["top"], vg["width"], vg["height"])
    except Exception:
        return rect  # không xác định được vùng ảo → giữ nguyên
    clipped = rect.intersected(virtual)
    if clipped.width() <= 0 or clipped.height() <= 0:
        return None
    return clipped


def window_frame_rect(hwnd: int) -> QRect | None:
    """Khung cửa sổ để chụp: ưu tiên DWM frame bounds, lùi về GetWindowRect,
    rồi cắt về trong vùng ảo. None nếu không lấy được khung hợp lệ."""
    if not _HAS_WIN32 or not hwnd:
        return None
    rect = _extended_frame_rect(hwnd) or _window_rect(hwnd)
    if rect is None:
        return None
    return _clamp_to_virtual(rect)


def _is_good_target(hwnd: int) -> bool:
    """Cửa sổ hợp lệ để chụp tự động (loại cửa sổ của chính app, cửa sổ ma,
    cửa sổ shell)."""
    return (
        _is_capturable_window(hwnd)
        and not _is_own_process(hwnd)
        and not _is_cloaked(hwnd)
        and not _is_shell_window(hwnd)
    )


def active_window_target() -> tuple[int, QRect, bool] | None:
    """Cửa sổ nên chụp khi người dùng bấm phím tắt, KHÔNG cần chuột.

    Trả (hwnd, rect, from_foreground) hoặc None nếu không tìm được cửa sổ nào.

    - from_foreground=True: đúng cửa sổ đang được focus → nó chắc chắn nằm trên
      cửa sổ của app mình, chụp được ngay không cần ẩn gì.
    - from_foreground=False: foreground không dùng được (là cửa sổ của chính app
      — ví dụ vừa mở menu khay, hoặc Editor vừa được đưa lên sau lần chụp trước)
      → đoán bằng cửa sổ hợp lệ trên cùng theo Z-order. Người gọi nên ẩn cửa sổ
      của app rồi đọc lại khung trước khi chụp.
    """
    if not _HAS_WIN32:
        return None

    try:
        fg = win32gui.GetForegroundWindow()
    except Exception:
        fg = 0
    # fg = 0 khi màn hình khoá / secure desktop (UAC) / đang Alt-Tab.
    if fg and _is_good_target(fg):
        rect = window_frame_rect(fg)
        if rect is not None:
            return (fg, rect, True)

    for hwnd in _iter_zorder():
        if not _is_good_target(hwnd):
            continue
        rect = window_frame_rect(hwnd)
        if rect is not None:
            return (hwnd, rect, False)

    return None


def raise_window_no_focus(hwnd: int) -> None:
    """Nâng cửa sổ lên trên cùng mà KHÔNG cướp focus.

    Cần cho nhánh fallback: khi ta ẩn cửa sổ của mình, Windows sẽ kích hoạt và
    NÂNG cửa sổ kế tiếp — có thể che mất cửa sổ đích. SetForegroundWindow sẽ bị
    OS từ chối (khác process), còn SetWindowPos + SWP_NOACTIVATE thì được.
    """
    if not _HAS_WIN32 or not hwnd:
        return
    try:
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
        )
    except Exception:
        pass  # không nâng được cũng không sao, vẫn chụp theo khung đã biết


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
