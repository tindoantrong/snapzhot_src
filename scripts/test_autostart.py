"""Test bật/tắt khởi động cùng Windows (autostart).

- is_supported() trả bool.
- Trên win32: bật/tắt được qua registry; khôi phục trạng thái ban đầu để không
  làm bẩn registry máy user.
- Ngoài win32: mọi thao tác là no-op an toàn (False), không ném.
"""
import os
import sys

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

from app.common import autostart

assert isinstance(autostart.is_supported(), bool)

if sys.platform == "win32":
    prev = autostart.is_enabled()
    try:
        assert autostart.set_enabled(True) is True, "phải bật được"
        assert autostart.is_enabled() is True, "bật xong is_enabled phải True"
        assert autostart.set_enabled(False) is True, "phải tắt được"
        assert autostart.is_enabled() is False, "tắt xong is_enabled phải False"
        print("OK: win32 bật/tắt autostart hoạt động")
    finally:
        # Khôi phục đúng trạng thái ban đầu của máy user.
        autostart.set_enabled(prev)
        assert autostart.is_enabled() == prev, "phải khôi phục trạng thái ban đầu"
        print(f"OK: đã khôi phục trạng thái ban đầu (enabled={prev})")
else:
    assert autostart.set_enabled(True) is False, "non-win32 phải trả False"
    assert autostart.is_enabled() is False, "non-win32 is_enabled phải False"
    print("OK: non-win32 no-op an toàn")

print("=== AUTOSTART OK ===")
