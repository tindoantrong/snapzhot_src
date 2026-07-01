"""Test setting phím tắt chụp vùng (mặc định PrtScrn) + round-trip chuỗi phím.

- DEFAULTS["hotkey_region"] == "print screen".
- Round-trip keyboard <-> Qt cho "print screen" và "ctrl+shift+a" (ca lệch Print).
- keyboard_to_qkeyseq("print screen") cho ra QKeySequence "Print".
- HotkeyDialog.value() (chạy offscreen): trả đúng chuỗi keyboard.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from app.common.config import DEFAULTS
from app.common.settings_dialog import (
    HotkeyDialog,
    keyboard_to_qkeyseq,
    qkeyseq_to_keyboard,
)

# 1) Mặc định đã đổi sang Print Screen.
assert DEFAULTS["hotkey_region"] == "print screen", DEFAULTS["hotkey_region"]

# 2) Round-trip không mất mát.
for s in ("print screen", "ctrl+shift+a", "ctrl+alt+s", "windows+shift+s"):
    back = qkeyseq_to_keyboard(keyboard_to_qkeyseq(s))
    assert back == s, f"round-trip lệch: {s!r} -> {back!r}"

# 3) Ca lệch phím Print: keyboard 'print screen' <-> Qt 'Print'.
assert keyboard_to_qkeyseq("print screen").toString(QKeySequence.PortableText) == "Print"
assert qkeyseq_to_keyboard(QKeySequence("Print")) == "print screen"
# windows <-> Meta.
assert qkeyseq_to_keyboard(QKeySequence("Meta+Shift+S")) == "windows+shift+s"

print("OK: round-trip + ca Print/Meta đúng")

# 4) Dialog offscreen: value() phản ánh sequence hiện tại.
app = QApplication.instance() or QApplication([])

dlg = HotkeyDialog("print screen")
assert dlg.value() == "print screen", dlg.value()

dlg2 = HotkeyDialog("ctrl+shift+a")
assert dlg2.value() == "ctrl+shift+a", dlg2.value()

# Đổi sequence thủ công -> value() cập nhật.
dlg2._edit.setKeySequence(keyboard_to_qkeyseq("print screen"))
assert dlg2.value() == "print screen", dlg2.value()

print("OK: HotkeyDialog.value() đúng")
print("=== HOTKEY SETTING OK ===")
