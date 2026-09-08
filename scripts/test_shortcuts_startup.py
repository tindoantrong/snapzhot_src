"""Test SHORTCUTS-01: logic persist should_show_on_startup / set_show_on_startup.

Chạy headless (không cần display/QApplication):
    python scripts/test_shortcuts_startup.py

Kiểm tra:
    1. Default (không có key trong file) → should_show_on_startup = True.
    2. set_show_on_startup(False) → đọc lại file → False.
    3. set_show_on_startup(True)  → đọc lại → True.
    4. Các key khác (hotkey_region, hotkey_video, default_color…) KHÔNG mất.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401  (sys.path + UTF-8)

# ---------------------------------------------------------------------------
# Redirect config path sang file tạm để test không đụng config thật của user.
# Phải patch TRƯỚC khi import bất kỳ module nào dùng config_path().
# ---------------------------------------------------------------------------
_tmp_cfg = Path(tempfile.mktemp(suffix="_test_shortcuts.json"))

import app.common.config as _cfg_mod
_cfg_mod.config_path = lambda: _tmp_cfg  # type: ignore[assignment]

from app.common.shortcuts_dialog import should_show_on_startup, set_show_on_startup
from app.common.config import load_config, save_config


def main() -> int:
    errors: list[str] = []

    def ok(msg: str) -> None:
        print(f"OK: {msg}")

    def fail(msg: str) -> None:
        errors.append(msg)
        print(f"FAIL: {msg}")

    # Seed file với các key khác để kiểm tra merge.
    seed = {
        "hotkey_region": "ctrl+shift+a",
        "hotkey_video": "ctrl+shift+r",
        "default_color": "#FF3B30",
        "default_width": 6,
    }
    save_config(seed)

    # 1. Chưa có key show_shortcuts_on_startup → default True
    cfg1 = load_config()
    if should_show_on_startup(cfg1) is True:
        ok("default (không có key) → True")
    else:
        fail(f"default phải True, nhận: {cfg1.get('show_shortcuts_on_startup')!r}")

    # 2. set_show_on_startup(False) → đọc lại → False
    set_show_on_startup(False)
    cfg2 = load_config()
    if should_show_on_startup(cfg2) is False:
        ok("set False → False")
    else:
        fail(f"sau set False phải False, nhận: {cfg2.get('show_shortcuts_on_startup')!r}")

    # 3. set_show_on_startup(True) → đọc lại → True
    set_show_on_startup(True)
    cfg3 = load_config()
    if should_show_on_startup(cfg3) is True:
        ok("set True → True")
    else:
        fail(f"sau set True phải True, nhận: {cfg3.get('show_shortcuts_on_startup')!r}")

    # 4. Các key khác không bị mất sau các lần save
    cfg4 = load_config()
    for k, v in seed.items():
        if cfg4.get(k) == v:
            ok(f"key '{k}' còn nguyên = {v!r}")
        else:
            fail(f"key '{k}' bị mất hoặc sai: nhận {cfg4.get(k)!r}, mong {v!r}")

    # Dọn file tạm
    try:
        _tmp_cfg.unlink()
    except Exception:
        pass

    if errors:
        print(f"\n=== SHORTCUTS STARTUP FAIL ({len(errors)} lỗi) ===")
        return 1

    print("\n=== SHORTCUTS STARTUP OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
