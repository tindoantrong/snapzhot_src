r"""Test list_captures() escape ký tự LIKE wildcard (%, _, \).

BUG đã fix: trước đây `like = f"%{search}%"` không escape nên "50%" -> "%50%%"
match mọi record; "_" match mọi ký tự. Sau fix dùng ESCAPE '\'.

Chạy offscreen (không cần màn hình).
"""
import _bootstrap  # noqa: F401

import os
import shutil
import tempfile
import unittest.mock as mock
from pathlib import Path

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

# ---------- setup: LibraryManager dùng DB + thư mục tạm, patch tại source module ----------

tmpdir = Path(tempfile.mkdtemp(prefix="snagit_test_"))
db_path = tmpdir / "test.db"
lib_dir = tmpdir / "library"
thumb_dir = tmpdir / "thumbnails"
lib_dir.mkdir()
thumb_dir.mkdir()

# Phải patch tên đã import VÀO library_manager, không phải module paths gốc.
import app.library.library_manager as _lm

with mock.patch.object(_lm, "database_path", return_value=db_path), \
     mock.patch.object(_lm, "library_dir", return_value=lib_dir), \
     mock.patch.object(_lm, "thumbnails_dir", return_value=thumb_dir):

    from app.library.library_manager import LibraryManager
    lib = LibraryManager()

    def _insert(name: str) -> None:
        """Chèn trực tiếp vào DB (bỏ qua file I/O) để test tên đặc biệt."""
        from datetime import datetime
        ts = datetime.now().isoformat(timespec="seconds")
        lib._conn.execute(
            "INSERT INTO captures (filename, path, created_at, width, height, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, f"/fake/{name}", ts, 10, 10, name),
        )
        lib._conn.commit()

    # Chọn tên KHÔNG chồng nhau: "promo%" chỉ có %, "xyz_1" chỉ có _, "back\slash" chỉ có \
    _insert("promo%")      # literal % trong filename + tags, không có _
    _insert("abc")         # bình thường, không ký tự đặc biệt
    _insert("xyz_1")       # literal _ trong filename + tags, không có %
    _insert("back\\slash") # literal \ trong filename + tags

    # --- test 1: search "%" không được trả tất cả record ---
    res = lib.list_captures("%")
    names = [c.filename for c in res]
    assert names == ["promo%"], \
        f"search '%' phải chỉ trả 'promo%', nhưng trả: {names}"
    print("OK: search '%' chỉ trả record chứa literal '%'")

    # --- test 2: search "_" chỉ trả record chứa dấu gạch dưới literal ---
    res = lib.list_captures("_")
    names = [c.filename for c in res]
    assert "xyz_1" in names, f"search '_' phải trả 'xyz_1', nhận: {names}"
    assert "abc" not in names, f"search '_' không được trả 'abc', nhận: {names}"
    assert "promo%" not in names, \
        f"search '_' không được trả 'promo%' (không chứa literal _), nhận: {names}"
    print("OK: search '_' chỉ trả record chứa literal '_'")

    # --- test 3: search "mo%" chỉ trả record có literal "mo%" (trong "promo%") ---
    res = lib.list_captures("mo%")
    names = [c.filename for c in res]
    assert names == ["promo%"], \
        f"search 'mo%' phải chỉ trả 'promo%', nhận: {names}"
    print("OK: search 'mo%' chỉ trả record chứa literal 'mo%'")

    # --- test 4: search thường vẫn hoạt động ---
    res = lib.list_captures("abc")
    names = [c.filename for c in res]
    assert names == ["abc"], f"search 'abc' phải trả ['abc'], nhận: {names}"
    print("OK: search thường 'abc' hoạt động bình thường")

    # --- test 5: search rỗng trả tất cả (4 record) ---
    res = lib.list_captures("")
    assert len(res) == 4, f"search rỗng phải trả 4 record, nhận: {len(res)}"
    print("OK: search rỗng trả tất cả record")

    # --- test 6: search backslash literal ---
    res = lib.list_captures("\\")
    names = [c.filename for c in res]
    assert "back\\slash" in names, \
        f"search '\\\\' phải trả 'back\\\\slash', nhận: {names}"
    print(r"OK: search '\' trả đúng record chứa backslash literal")

    lib.close()

shutil.rmtree(tmpdir, ignore_errors=True)
print("=== LIBRARY SEARCH ESCAPE OK ===")
