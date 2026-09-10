"""Đọc/ghi cấu hình người dùng dạng JSON đơn giản."""
from __future__ import annotations

import json
from typing import Any

from .paths import config_path

DEFAULTS: dict[str, Any] = {
    "hotkey_region": "print screen",      # chụp vùng chọn (mặc định PrtScrn)
    "hotkey_video": "ctrl+shift+r",       # bật/tắt quay video
    # Chụp ngay cửa sổ đang dùng. KHÔNG dùng ctrl+shift+w (Chrome đóng cửa sổ,
    # vì hotkey này không suppress) và KHÔNG dùng tổ hợp kết thúc bằng
    # "print screen" (hook_key PrtSc suppress mọi PrtSc bất kể modifier).
    "hotkey_window": "ctrl+alt+w",
    "video_fps": 15,                      # FPS mục tiêu khi quay
    "record_audio": True,                 # thu mic kèm video (nếu có thiết bị)
    "capture_delay_seconds": 3,           # số giây mặc định cho chụp hẹn giờ
    "open_editor_after_capture": True,    # mở editor ngay sau khi chụp
    "default_color": "#FF3B30",           # màu công cụ mặc định (đỏ giống Snagit)
    "default_width": 6,                   # độ dày nét mặc định (pt)
    "run_in_background": True,            # giữ chạy nền ở khay hệ thống
    "start_on_boot": False,               # tự chạy khi Windows khởi động
    "show_shortcuts_on_startup": True,    # hiện dialog phím tắt mỗi lần mở app
    "recent_strip_expanded": True,        # dải "Ảnh gần đây" ở Editor đang mở?
    "theme": "dark",                      # giao diện toàn app: "dark" | "light"
    "canvas_bg": 0,                       # nền vùng ảnh trong Editor (0/1/2)
}


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    p = config_path()
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    config_path().write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
