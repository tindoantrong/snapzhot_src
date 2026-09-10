"""Theme sáng/tối dùng chung cho toàn app.

Mọi màu của phần "vỏ" (cửa sổ, toolbar, panel, menu, hộp thoại, chữ, icon) đi
qua đúng MỘT bảng token ở đây, thay vì rải mã hex trong từng file QSS. Đổi
theme = đổi bảng token rồi bảo các cửa sổ dựng lại stylesheet.

Cách dùng:
    from ..common import theme
    self.setStyleSheet(theme.qss(_MY_QSS_TPL))      # $token → mã màu
    theme.manager.changed.connect(self._apply_theme)

KHÔNG thuộc theme: nội dung ảnh, màu nét vẽ, ảnh xuất ra, và nền vùng ảnh
(canvas) — nền canvas do nút ô caro trong Editor điều khiển và nhớ riêng.
"""
from __future__ import annotations

from string import Template
from typing import Callable

from PySide6.QtCore import QObject, Signal

# ---------------------------------------------------------------- bảng token
# Cùng bộ khoá cho cả hai theme; thiếu khoá nào là lỗi ngay lúc substitute.
DARK: dict[str, str] = {
    # nền
    "bg": "#2B2D31",             # nền cửa sổ / panel
    "surface": "#33363B",        # toolbar, thanh tiêu đề panel
    "surface_alt": "#222428",    # thanh trạng thái
    "elevated": "#3E4248",       # hover, ô nhập
    "elevated_hi": "#484C53",    # hover của nút đặc
    "pressed": "#2F3338",        # đang nhấn
    "sunken": "#1E1F22",         # ô văn bản, rãnh progress
    "void": "#3A3D42",           # vùng trống sau nội dung (empty state)
    # viền
    "border": "#55585E",
    "border_subtle": "#4A4D52",
    # chữ
    "text": "#E8E8E8",
    "text_soft": "#DDDDDD",
    "text_dim": "#C8C8C8",
    "text_muted": "#9AA0A6",
    "disabled_bg": "#2F3136",
    "disabled_fg": "#7A7D82",
    # màu nhấn — giữ xanh nhận diện ở cả hai theme.
    # accent      : VIỀN / vòng focus / tay cầm slider — cần nổi trên nền TỐI.
    # accent_fill : MẢNG ĐẶC có chữ đè lên — cần đủ tối để chữ trắng đọc được.
    # Một mã màu không kham nổi cả hai: #1E90FF nổi trên nền tối (4.26:1) nhưng
    # chữ trắng trên nó chỉ 3.24:1; hạ xuống cho chữ đọc được thì viền lại chìm.
    "accent": "#1E90FF",
    "accent_hover": "#3AA0FF",
    "accent_pressed": "#187BDD",
    "accent_fill": "#1571C9",        # chữ trắng trên nó = 4.96:1
    "accent_fill_hover": "#1B84EB",
    "accent_soft": "#7EC8FF",    # chữ nhấn trên nền tối
    "on_accent": "#FFFFFF",
    "selected_bg": "#1E3A5F",    # nền thẻ đang chọn (kèm viền accent)
    # icon line-art
    "icon": "#E8E8E8",
    "icon_disabled": "#7A7D82",
}

LIGHT: dict[str, str] = {
    "bg": "#F4F5F7",
    "surface": "#FFFFFF",
    "surface_alt": "#E9EBEF",
    "elevated": "#E7E9ED",
    "elevated_hi": "#DCDFE5",
    "pressed": "#CFD4DB",
    "sunken": "#FFFFFF",
    "void": "#E2E4E9",
    "border": "#B9BEC7",
    "border_subtle": "#D8DBE1",
    "text": "#1F2328",
    "text_soft": "#2B3138",
    "text_dim": "#3F4750",
    "text_muted": "#68717B",
    "disabled_bg": "#E3E6EA",
    "disabled_fg": "#9AA1A9",
    # Xanh đậm hơn một nấc: vẫn đúng dải xanh nhận diện nhưng chữ trắng trên nó
    # mới đạt tương phản đọc được trên nền sáng.
    # Trên nền sáng, #0F6FD1 vừa đủ tối để làm viền rõ (4.98:1 với nền trắng)
    # vừa đủ tối để chữ trắng trên mảng đặc đọc được → hai vai trò dùng chung.
    "accent": "#0F6FD1",
    "accent_hover": "#1E90FF",
    "accent_pressed": "#0B57A6",
    "accent_fill": "#0F6FD1",
    "accent_fill_hover": "#1E90FF",
    "accent_soft": "#0B57A6",
    "on_accent": "#FFFFFF",
    "selected_bg": "#D6E8FF",
    "icon": "#2B3138",
    "icon_disabled": "#9AA1A9",
}

_MODES: dict[str, dict[str, str]] = {"dark": DARK, "light": LIGHT}
DEFAULT_MODE = "dark"


class _ThemeManager(QObject):
    """Giữ theme đang dùng và báo cho mọi cửa sổ khi nó đổi."""

    changed = Signal(str)  # "dark" | "light"

    def __init__(self) -> None:
        super().__init__()
        self._mode = DEFAULT_MODE
        # tool_icons đăng ký hàm xoá cache vào đây, tránh vòng import
        # (theme là lớp dưới, không được biết tới lớp icon của Editor).
        self._invalidators: list[Callable[[], None]] = []

    @property
    def mode(self) -> str:
        return self._mode

    def tokens(self) -> dict[str, str]:
        return _MODES[self._mode]

    def set_mode(self, mode: str) -> None:
        """Đổi theme; không phát tín hiệu nếu vốn đã đúng theme đó."""
        mode = mode if mode in _MODES else DEFAULT_MODE
        if mode == self._mode:
            return
        self._mode = mode
        for fn in self._invalidators:
            fn()
        self.changed.emit(mode)

    def toggle(self) -> str:
        self.set_mode("light" if self._mode == "dark" else "dark")
        return self._mode

    def add_invalidator(self, fn: Callable[[], None]) -> None:
        self._invalidators.append(fn)


manager = _ThemeManager()


# ------------------------------------------------------------------ tiện ích
def mode() -> str:
    return manager.mode


def is_dark() -> bool:
    return manager.mode == "dark"


def color(role: str) -> str:
    """Mã hex của một token theo theme đang dùng."""
    return manager.tokens()[role]


def qss(template: str) -> str:
    """Thay $token trong QSS template bằng màu của theme đang dùng."""
    return Template(template).substitute(manager.tokens())


# --------------------------------------------------------- stylesheet nền app
# Áp lên QApplication để những hộp thoại KHÔNG có QSS riêng (Cài đặt, đặt phím
# tắt, QMessageBox…) vẫn đổi theo theme. Cố ý KHÔNG đặt luật cho QWidget trần:
# một luật nền phủ toàn bộ sẽ sơn đè lên cả widget con của canvas/thumbnail.
APP_QSS_TPL = """
QDialog, QMessageBox, QInputDialog { background: $bg; color: $text; }
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel { color: $text; }
QDialog QGroupBox {
    color: $text;
    border: 1px solid $border_subtle;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
}
QDialog QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: $text_dim;
}
QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
    background: $elevated;
    color: $text;
    border: 1px solid $border;
    border-radius: 5px;
    padding: 6px 12px;
}
QDialog QPushButton:hover, QMessageBox QPushButton:hover { background: $elevated_hi; }
QDialog QPushButton:pressed, QMessageBox QPushButton:pressed { background: $pressed; }
QDialog QPushButton:disabled {
    background: $disabled_bg;
    color: $disabled_fg;
    border-color: $disabled_bg;
}
QDialog QPushButton:default { border: 1px solid $accent; }
QDialog QLineEdit, QDialog QSpinBox, QDialog QDoubleSpinBox, QDialog QComboBox,
QDialog QPlainTextEdit, QDialog QTextEdit, QInputDialog QLineEdit {
    background: $sunken;
    color: $text;
    border: 1px solid $border;
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: $accent_fill;
    selection-color: $on_accent;
}
QDialog QLineEdit:focus, QDialog QSpinBox:focus, QDialog QComboBox:focus,
QDialog QPlainTextEdit:focus, QDialog QTextEdit:focus { border: 1px solid $accent; }
QDialog QComboBox QAbstractItemView {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    selection-background-color: $accent_fill;
    selection-color: $on_accent;
}
QDialog QCheckBox, QDialog QRadioButton { color: $text; }
QDialog QCheckBox::indicator, QDialog QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid $border;
    border-radius: 3px;
    background: $sunken;
}
QDialog QCheckBox::indicator:checked, QDialog QRadioButton::indicator:checked {
    background: $accent;
    border-color: $accent;
}
QMenu { background: $surface; color: $text; border: 1px solid $border; }
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { background: $accent_fill; color: $on_accent; }
QMenu::separator { height: 1px; background: $border_subtle; margin: 4px 8px; }
QToolTip {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    padding: 3px 6px;
}
QScrollBar:vertical { background: $surface; width: 8px; margin: 0; }
QScrollBar:horizontal { background: $surface; height: 8px; margin: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: $border;
    border-radius: 4px;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


_app_hooked = False


def _reapply_app_qss(_mode: str = "") -> None:
    """Áp lại stylesheet nền lên QApplication đang sống (nếu còn).

    Cố ý tra QApplication.instance() mỗi lần thay vì giữ tham chiếu trong
    closure: manager là singleton cấp module, sống lâu hơn QApplication, giữ
    tham chiếu thì lúc tắt app còn đụng vào đối tượng đã bị huỷ.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(qss(APP_QSS_TPL))


def apply_to_app(app) -> None:
    """Áp stylesheet nền cho QApplication và giữ nó khớp theme về sau.

    Tự đăng ký nghe `changed` để nơi gọi không phải nhớ áp lại — quên chỗ này
    là hộp thoại kẹt ở theme cũ.
    """
    global _app_hooked
    app.setStyleSheet(qss(APP_QSS_TPL))
    if not _app_hooked:
        _app_hooked = True
        manager.changed.connect(_reapply_app_qss)
