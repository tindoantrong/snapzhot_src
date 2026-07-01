"""Quản lý đường dẫn lưu dữ liệu của ứng dụng (thư viện ảnh, DB, cấu hình).

Mọi dữ liệu người dùng nằm trong %LOCALAPPDATA%\\SnagTin để app khi đóng gói
EXE vẫn ghi được (không ghi vào thư mục cài đặt - thường read-only).
"""
from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    """Thư mục gốc chứa dữ liệu người dùng."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "SnagTin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def library_dir() -> Path:
    """Thư mục chứa file ảnh đã chụp."""
    d = app_data_dir() / "library"
    d.mkdir(parents=True, exist_ok=True)
    return d


def thumbnails_dir() -> Path:
    """Thư mục cache ảnh thu nhỏ."""
    d = app_data_dir() / "thumbnails"
    d.mkdir(parents=True, exist_ok=True)
    return d


def videos_dir() -> Path:
    """Thư mục chứa video đã quay."""
    d = app_data_dir() / "videos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def database_path() -> Path:
    """File SQLite chứa metadata thư viện."""
    return app_data_dir() / "library.db"


def config_path() -> Path:
    """File JSON cấu hình người dùng."""
    return app_data_dir() / "config.json"
