"""Dialog phím tắt — hiện khi khởi động và mở lại được từ menu tray.

Hai hàm thuần (không Qt) để test headless:
    should_show_on_startup(cfg) -> bool
    set_show_on_startup(show)   -> None  (load → set 1 key → save; merge an toàn)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QPushButton,
)

from .config import load_config, save_config

# ---------------------------------------------------------------------------
# Hàm thuần — KHÔNG phụ thuộc Qt, có thể test headless
# ---------------------------------------------------------------------------

def should_show_on_startup(cfg: dict) -> bool:
    """True nếu dialog phím tắt nên hiện khi khởi động (mặc định True)."""
    return bool(cfg.get("show_shortcuts_on_startup", True))


def set_show_on_startup(show: bool) -> None:
    """Ghi cờ vào file config (merge an toàn — không xoá các key khác)."""
    cfg = load_config()
    cfg["show_shortcuts_on_startup"] = show
    save_config(cfg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_key(key: str) -> str:
    """Định dạng hotkey từ config: 'ctrl+shift+r' → 'Ctrl+Shift+R'."""
    return "+".join(p.strip().title() for p in key.split("+"))


_DIALOG_QSS = """
QDialog {
    background: #2B2D31;
    color: #E8E8E8;
}
#dlgTitle {
    color: #FFFFFF;
    font-size: 18px;
    font-weight: bold;
}
#dlgSub {
    color: #9AA0A6;
    font-size: 13px;
}
#groupHeading {
    color: #7EC8FF;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
}
#actionLabel {
    color: #DDDDDD;
    font-size: 13px;
}
#keycap {
    background: #3E4248;
    color: #E8E8E8;
    border: 1px solid #55585E;
    border-radius: 4px;
    padding: 2px 8px;
    font-family: "Courier New", Courier, monospace;
    font-size: 12px;
    min-width: 32px;
}
QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #33363B;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #55585E;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QFrame#separator {
    background: #3E4248;
}
QCheckBox {
    color: #9AA0A6;
    font-size: 12px;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #55585E;
    border-radius: 3px;
    background: #33363B;
}
QCheckBox::indicator:checked {
    background: #1E90FF;
    border-color: #1E90FF;
}
QPushButton#closeBtn {
    background: #1E90FF;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 7px 28px;
    font-size: 13px;
}
QPushButton#closeBtn:hover { background: #3AA0FF; }
QPushButton#closeBtn:pressed { background: #187BDD; }
"""


class ShortcutsDialog(QDialog):
    """Dialog danh sách phím tắt — hiện lúc khởi động hoặc từ tray menu."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Phím tắt — SnagTin")
        self.setMinimumSize(480, 540)
        self.resize(520, 660)
        self.setModal(True)
        self._build_ui()
        self.setStyleSheet(_DIALOG_QSS)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        cfg = load_config()

        # Import TOOLS lazily để sinh danh sách tool động, tránh lệch khi cập nhật.
        try:
            from ..editor.editor_window import TOOLS as _tools
            tool_rows: list[tuple[str, str]] = [
                (name, shortcut) for _, name, _, shortcut in _tools
            ]
        except Exception:
            # Fallback tĩnh nếu import thất bại (vd test môi trường không có PySide6).
            tool_rows = [
                ("Chọn", "V"), ("Mũi tên", "A"), ("Chữ nhật", "R"), ("Elip", "E"),
                ("Bút vẽ", "P"), ("Chữ", "T"), ("Callout", "O"), ("Đánh dấu", "H"),
                ("Làm mờ", "B"), ("Số bước", "S"), ("Cắt", "C"),
                ("Stamp", "M"), ("Tiêu điểm", "F"),
            ]

        try:
            from ..ocr import claude_cli_available
            has_ocr = claude_cli_available()
        except Exception:
            has_ocr = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Tiêu đề ---
        header = QWidget()
        hl = QVBoxLayout(header)
        hl.setContentsMargins(24, 20, 24, 14)
        hl.setSpacing(4)
        title = QLabel("Phím tắt — SnagTin")
        title.setObjectName("dlgTitle")
        sub = QLabel("Làm quen nhanh các phím tắt trong app")
        sub.setObjectName("dlgSub")
        hl.addWidget(title)
        hl.addWidget(sub)
        outer.addWidget(header)

        sep1 = QFrame()
        sep1.setObjectName("separator")
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFixedHeight(1)
        outer.addWidget(sep1)

        # --- Nội dung cuộn ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 16, 24, 16)
        cl.setSpacing(18)

        # Toàn cục: đọc từ config để hiển thị phím tắt thực tế của user.
        global_rows = [
            ("Chụp vùng chọn", _fmt_key(cfg.get("hotkey_region", "print screen"))),
            ("Bật/tắt quay video", _fmt_key(cfg.get("hotkey_video", "ctrl+shift+r"))),
        ]
        cl.addWidget(self._make_group("TOÀN CỤC (hệ thống)", global_rows))

        # Công cụ: sinh từ TOOLS trong editor_window.
        cl.addWidget(self._make_group("CÔNG CỤ (trong Editor)", tool_rows))

        # Chỉnh sửa
        edit_rows = [
            ("Hoàn tác", "Ctrl+Z"),
            ("Làm lại", "Ctrl+Y"),
            ("Xoá đối tượng", "Delete"),
        ]
        cl.addWidget(self._make_group("CHỈNH SỬA", edit_rows))

        # Tệp / Clipboard
        file_rows = [
            ("Lưu vào thư viện", "Ctrl+S"),
            ("Xuất ra file", "Ctrl+E"),
            ("Copy ảnh", "Ctrl+C"),
            ("Dán ảnh", "Ctrl+V"),
        ]
        cl.addWidget(self._make_group("TỆP / CLIPBOARD", file_rows))

        # Xem
        view_rows = [
            ("Thu nhỏ", "Ctrl+−"),
            ("Phóng to", "Ctrl+="),
            ("Vừa khung nhìn", "Ctrl+0"),
            ("Kích thước 100%", "Ctrl+1"),
            ("Ẩn/hiện panel thuộc tính", "F4"),
        ]
        cl.addWidget(self._make_group("XEM", view_rows))

        # OCR — chỉ hiện khi máy có claude CLI
        if has_ocr:
            ocr_rows = [
                ("OCR toàn ảnh", "Ctrl+Shift+O"),
                ("OCR vùng chọn", "Ctrl+Shift+R"),
                ("Lịch sử OCR", "Ctrl+Shift+H"),
            ]
            cl.addWidget(self._make_group("OCR (trích xuất văn bản)", ocr_rows))

        cl.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # --- Chân dialog ---
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFixedHeight(1)
        outer.addWidget(sep2)

        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 12, 20, 16)
        fl.setSpacing(12)

        self._no_show_cb = QCheckBox(
            "Không hiển thị hộp thoại này khi khởi động"
        )
        # Checkbox phản ánh trạng thái hiện tại: đã tắt startup → tick sẵn.
        self._no_show_cb.setChecked(not should_show_on_startup(cfg))
        fl.addWidget(self._no_show_cb)
        fl.addStretch(1)

        close_btn = QPushButton("Đóng")
        close_btn.setObjectName("closeBtn")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        fl.addWidget(close_btn)

        outer.addWidget(footer)

    # ------------------------------------------------------------------
    @staticmethod
    def _make_group(title: str, rows: list[tuple[str, str]]) -> QWidget:
        """Tạo một nhóm phím tắt (tiêu đề + danh sách hành động ↔ keycap)."""
        group = QWidget()
        gl = QVBoxLayout(group)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(5)

        heading = QLabel(title)
        heading.setObjectName("groupHeading")
        gl.addWidget(heading)

        for action_name, key in rows:
            row_w = QWidget()
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(4, 0, 0, 0)
            rl.setSpacing(8)

            action_lbl = QLabel(action_name)
            action_lbl.setObjectName("actionLabel")
            action_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            rl.addWidget(action_lbl)

            key_lbl = QLabel(key)
            key_lbl.setObjectName("keycap")
            key_lbl.setAlignment(Qt.AlignCenter)
            rl.addWidget(key_lbl)

            gl.addWidget(row_w)

        return group

    # ------------------------------------------------------------------
    def done(self, result: int) -> None:
        """Persist checkbox state khi đóng dialog theo bất kỳ cách nào (Đóng / Esc / X)."""
        # checkbox "Không hiển thị" → show = NOT checked
        set_show_on_startup(not self._no_show_cb.isChecked())
        super().done(result)
