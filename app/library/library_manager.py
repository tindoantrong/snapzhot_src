"""Quản lý thư viện ảnh đã chụp: lưu file PNG + metadata trong SQLite.

Mỗi bản ghi (capture) gồm: id, tên file, đường dẫn, thời gian tạo,
kích thước, và danh sách tag (chuỗi cách nhau bởi dấu phẩy cho đơn giản).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage

from ..common.paths import database_path, library_dir, thumbnails_dir

THUMB_SIZE = 220


@dataclass
class Capture:
    id: int
    filename: str
    path: str
    created_at: str
    width: int
    height: int
    tags: str
    media_type: str = "image"   # 'image' hoặc 'video'
    duration: float = 0.0       # thời lượng (giây) nếu là video

    @property
    def thumbnail_path(self) -> Path:
        return thumbnails_dir() / f"{self.id}.png"

    @property
    def is_video(self) -> bool:
        return self.media_type == "video"

    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class LibraryManager:
    def __init__(self) -> None:
        self._conn = sqlite3.connect(str(database_path()))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                tags TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Migration: thêm cột cho video nếu DB cũ chưa có (tương thích ngược).
        existing = {row["name"] for row in
                    self._conn.execute("PRAGMA table_info(captures)")}
        if "media_type" not in existing:
            self._conn.execute(
                "ALTER TABLE captures ADD COLUMN media_type TEXT NOT NULL DEFAULT 'image'"
            )
        if "duration" not in existing:
            self._conn.execute(
                "ALTER TABLE captures ADD COLUMN duration REAL NOT NULL DEFAULT 0"
            )
        self._conn.commit()

    # ---------- thêm / lưu ----------
    def add_capture(self, image: QImage, tags: str = "") -> Capture:
        """Lưu QImage thành PNG vào thư viện và ghi metadata."""
        ts = datetime.now()
        filename = f"capture_{ts:%Y%m%d_%H%M%S_%f}.png"
        full_path = library_dir() / filename
        image.save(str(full_path), "PNG")

        cur = self._conn.execute(
            "INSERT INTO captures (filename, path, created_at, width, height, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (filename, str(full_path), ts.isoformat(timespec="seconds"),
             image.width(), image.height(), tags),
        )
        self._conn.commit()
        cap = Capture(cur.lastrowid, filename, str(full_path),
                      ts.isoformat(timespec="seconds"),
                      image.width(), image.height(), tags)
        self._make_thumbnail(cap, image)
        return cap

    def add_video(self, video_path: str, duration: float,
                  thumbnail: QImage, width: int, height: int,
                  tags: str = "") -> Capture:
        """Ghi metadata cho một video đã quay (file đã nằm trên đĩa)."""
        ts = datetime.now()
        cur = self._conn.execute(
            "INSERT INTO captures "
            "(filename, path, created_at, width, height, tags, media_type, duration) "
            "VALUES (?, ?, ?, ?, ?, ?, 'video', ?)",
            (Path(video_path).name, video_path, ts.isoformat(timespec="seconds"),
             width, height, tags, duration),
        )
        self._conn.commit()
        cap = Capture(cur.lastrowid, Path(video_path).name, video_path,
                      ts.isoformat(timespec="seconds"), width, height, tags,
                      media_type="video", duration=duration)
        if not thumbnail.isNull():
            self._make_thumbnail(cap, thumbnail)
        return cap

    def update_image(self, capture_id: int, image: QImage) -> None:
        """Ghi đè ảnh (sau khi chỉnh sửa trong editor) và làm lại thumbnail."""
        cap = self.get(capture_id)
        if cap is None:
            return
        image.save(cap.path, "PNG")
        self._conn.execute(
            "UPDATE captures SET width=?, height=? WHERE id=?",
            (image.width(), image.height(), capture_id),
        )
        self._conn.commit()
        self._make_thumbnail(cap, image)

    def _make_thumbnail(self, cap: Capture, image: QImage) -> None:
        thumb = image.scaled(
            QSize(THUMB_SIZE, THUMB_SIZE),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        thumb.save(str(cap.thumbnail_path), "PNG")

    # ---------- truy vấn ----------
    def get(self, capture_id: int) -> Capture | None:
        row = self._conn.execute(
            "SELECT * FROM captures WHERE id=?", (capture_id,)
        ).fetchone()
        return self._row_to_capture(row) if row else None

    def list_captures(self, search: str = "") -> list[Capture]:
        if search:
            like = f"%{search}%"
            rows = self._conn.execute(
                "SELECT * FROM captures WHERE filename LIKE ? OR tags LIKE ? "
                "ORDER BY datetime(created_at) DESC",
                (like, like),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM captures ORDER BY datetime(created_at) DESC"
            ).fetchall()
        return [self._row_to_capture(r) for r in rows]

    # ---------- cập nhật / xoá ----------
    def set_tags(self, capture_id: int, tags: str) -> None:
        self._conn.execute(
            "UPDATE captures SET tags=? WHERE id=?", (tags, capture_id)
        )
        self._conn.commit()

    def delete(self, capture_id: int) -> None:
        cap = self.get(capture_id)
        if cap is None:
            return
        for p in (Path(cap.path), cap.thumbnail_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        self._conn.execute("DELETE FROM captures WHERE id=?", (capture_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_capture(row: sqlite3.Row) -> Capture:
        keys = row.keys()
        return Capture(
            id=row["id"], filename=row["filename"], path=row["path"],
            created_at=row["created_at"], width=row["width"],
            height=row["height"], tags=row["tags"],
            media_type=row["media_type"] if "media_type" in keys else "image",
            duration=row["duration"] if "duration" in keys else 0.0,
        )

    def close(self) -> None:
        self._conn.close()
