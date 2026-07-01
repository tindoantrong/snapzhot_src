"""Test headless cho scripts/make_release.py — không cần mạng, không build thật.

Kiểm tra:
  1. build_manifest trả đúng version == __version__, url khớp repo đúng + tên exe.
  2. url KHÔNG chứa "doanleox".
  3. write_manifest ghi ra file tạm, đọc lại khớp.
  4. write_manifest giữ nguyên notes cũ khi không truyền notes_override.
  5. write_manifest dùng notes_override khi được truyền (override notes cũ).
"""
import json
import os
import sys
import tempfile

import _bootstrap  # noqa: F401  (sys.path + UTF-8)

from app import __version__

# Import hàm thuần và hàm ghi từ make_release
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from make_release import build_manifest, write_manifest  # noqa: E402

# -----------------------------------------------------------------------
# 1. build_manifest: trường version
# -----------------------------------------------------------------------
m = build_manifest(__version__, "notes test")
assert m["version"] == __version__, (
    f"version phải == __version__ ({__version__!r}), got {m['version']!r}"
)
print(f"OK: build_manifest version == __version__ ({__version__})")

# -----------------------------------------------------------------------
# 2. build_manifest: url chứa repo đúng + tên exe đúng
# -----------------------------------------------------------------------
assert "tindoantrong/snapzhot_src" in m["url"], (
    f"url phải chứa 'tindoantrong/snapzhot_src', got: {m['url']!r}"
)
assert f"SnagTin-Setup-{__version__}.exe" in m["url"], (
    f"url phải chứa 'SnagTin-Setup-{__version__}.exe', got: {m['url']!r}"
)
print(f"OK: build_manifest url chứa repo đúng + tên exe đúng")
print(f"    url = {m['url']}")

# -----------------------------------------------------------------------
# 3. build_manifest: url KHÔNG chứa doanleox
# -----------------------------------------------------------------------
assert "doanleox" not in m["url"], (
    f"url KHÔNG được chứa 'doanleox', got: {m['url']!r}"
)
print("OK: 'doanleox' không xuất hiện trong url")

# -----------------------------------------------------------------------
# 4. write_manifest: ghi ra file tạm, đọc lại khớp
# -----------------------------------------------------------------------
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", delete=False, encoding="utf-8"
) as tf:
    tmp_path = tf.name

try:
    written = write_manifest(tmp_path, notes_override="Bản đầu tiên")
    with open(tmp_path, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk == written, "nội dung ghi ra phải khớp dict trả về"
    assert on_disk["version"] == __version__
    assert on_disk["notes"] == "Bản đầu tiên"
    print("OK: write_manifest ghi ra file tạm, đọc lại khớp")
finally:
    os.unlink(tmp_path)

# -----------------------------------------------------------------------
# 5. write_manifest: giữ notes cũ khi không truyền notes_override
# -----------------------------------------------------------------------
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", delete=False, encoding="utf-8"
) as tf:
    tmp_path = tf.name
    json.dump({"version": "0.0.1", "url": "x", "notes": "Notes gốc không đổi"}, tf)

try:
    written2 = write_manifest(tmp_path, notes_override=None)
    assert written2["notes"] == "Notes gốc không đổi", (
        f"notes phải giữ nguyên khi không truyền override, got: {written2['notes']!r}"
    )
    assert written2["version"] == __version__, "version phải cập nhật lên __version__"
    print("OK: write_manifest giữ notes cũ khi không truyền notes_override")
finally:
    os.unlink(tmp_path)

# -----------------------------------------------------------------------
# 6. write_manifest: notes_override ghi đè notes cũ
# -----------------------------------------------------------------------
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", delete=False, encoding="utf-8"
) as tf:
    tmp_path = tf.name
    json.dump({"version": "0.0.1", "url": "x", "notes": "Notes cũ"}, tf)

try:
    written3 = write_manifest(tmp_path, notes_override="Notes mới override")
    assert written3["notes"] == "Notes mới override", (
        f"notes_override phải ghi đè notes cũ, got: {written3['notes']!r}"
    )
    print("OK: write_manifest notes_override ghi đè notes cũ")
finally:
    os.unlink(tmp_path)

print()
print("=== TEST RELEASE MANIFEST OK ===")
