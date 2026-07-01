"""Hộp thoại đặt phím tắt chụp vùng + chuyển đổi chuỗi phím.

Hai "vũ trụ" tên phím khác nhau:
- Thư viện `keyboard` (đăng ký hotkey toàn cục): chuỗi thường, tổ hợp nối bằng "+",
  ví dụ "ctrl+shift+a", "print screen" (CÓ DẤU CÁCH, không phải "+").
- Qt `QKeySequence` (widget bắt phím): PortableText như "Ctrl+Shift+A", "Print".

Hai hàm dưới đây map qua lại, chú ý ca lệch phím Print:
    keyboard "print screen"  <->  Qt "Print"
    keyboard "windows"       <->  Qt "Meta"
"""
from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QKeySequenceEdit,
    QLabel,
    QVBoxLayout,
)

# keyboard -> Qt portable (chỉ những token cần dịch đặc biệt).
_KB_TO_QT = {
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "windows": "Meta",
    "win": "Meta",
    "cmd": "Meta",
    "super": "Meta",
    "meta": "Meta",
    "print screen": "Print",
    "print_screen": "Print",
    "printscreen": "Print",
    "prtsc": "Print",
    "prtscn": "Print",
    "print": "Print",
}

# Qt portable (lower) -> keyboard.
_QT_TO_KB = {
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "meta": "windows",
    "print": "print screen",
}


def keyboard_to_qkeyseq(s: str) -> QKeySequence:
    """Chuỗi của thư viện `keyboard` -> QKeySequence.

    Tách theo "+" (giữ nguyên token có dấu cách như "print screen").
    """
    if not s:
        return QKeySequence()
    parts: list[str] = []
    for raw in s.split("+"):
        tok = raw.strip().lower()
        if not tok:
            continue
        if tok in _KB_TO_QT:
            parts.append(_KB_TO_QT[tok])
        elif len(tok) == 1:
            parts.append(tok.upper())
        else:
            parts.append(tok.capitalize())
    return QKeySequence("+".join(parts))


def qkeyseq_to_keyboard(seq: QKeySequence) -> str:
    """QKeySequence -> chuỗi cho thư viện `keyboard` (lấy tổ hợp đầu tiên)."""
    if seq is None or seq.isEmpty():
        return ""
    text = seq.toString(QKeySequence.PortableText)
    if not text:
        return ""
    # Chỉ lấy tổ hợp đầu nếu có nhiều (PortableText nối nhiều combo bằng ", ").
    text = text.split(", ")[0]
    out: list[str] = []
    for tok in text.split("+"):
        tl = tok.strip().lower()
        if not tl:
            continue
        out.append(_QT_TO_KB.get(tl, tl))
    return "+".join(out)


class HotkeyDialog(QDialog):
    """Hộp thoại nhỏ: bắt 1 tổ hợp phím, trả về chuỗi `keyboard`."""

    def __init__(self, current: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt phím tắt chụp vùng")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Nhấn tổ hợp phím muốn dùng để chụp vùng:"))

        self._edit = QKeySequenceEdit(self)
        # Chỉ cho phép một tổ hợp phím (Qt >= 6.5).
        try:
            self._edit.setMaximumSequenceLength(1)
        except Exception:
            pass
        if current:
            self._edit.setKeySequence(keyboard_to_qkeyseq(current))
        layout.addWidget(self._edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> str:
        """Chuỗi phím theo định dạng thư viện `keyboard` (rỗng nếu chưa nhập)."""
        return qkeyseq_to_keyboard(self._edit.keySequence())
