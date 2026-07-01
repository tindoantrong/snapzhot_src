"""Bật/tắt tự khởi động cùng Windows qua registry Run key (HKCU)."""
from __future__ import annotations

import os
import sys

from .. import APP_NAME

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported() -> bool:
    return sys.platform == "win32"


def _command() -> str:
    if getattr(sys, "frozen", False):           # bản đóng gói PyInstaller
        return f'"{sys.executable}"'
    # chạy bằng python: ưu tiên pythonw.exe để KHÔNG bật cửa sổ console mỗi lần boot
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    main_py = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
    return f'"{exe}" "{main_py}"'


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            val, _ = winreg.QueryValueEx(k, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Trả True nếu đặt được; False nếu lỗi/không hỗ trợ."""
    if not is_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
