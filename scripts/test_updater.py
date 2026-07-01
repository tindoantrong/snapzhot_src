"""Test module kiểm tra cập nhật (app/updater.py) — không cần mạng thật.

- parse_version: bóc số đúng, bỏ tiền tố v.
- is_newer: cao/thấp/bằng.
- check_for_updates: monkeypatch urllib.request.urlopen cho 3 ca:
  có bản mới, đã mới nhất, lỗi mạng (error set, không crash).
"""
import io
import json
import urllib.error
import urllib.request

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

from app import updater

# --- parse_version ---
assert updater.parse_version("v1.2.0") == (1, 2, 0), "v1.2.0 -> (1,2,0)"
assert updater.parse_version("0.1.0") == (0, 1, 0)
assert updater.parse_version("V2.0") == (2, 0)
assert updater.parse_version("1.2.3-beta4") == (1, 2, 3, 4), "lấy mọi nhóm số"
assert updater.parse_version("") == (0,), "rỗng an toàn"
assert updater.parse_version("noversion") == (0,), "không số -> (0,)"
print("OK: parse_version")

# --- is_newer ---
assert updater.is_newer("1.0.1", "1.0.0") is True, "cao hơn"
assert updater.is_newer("0.9.0", "1.0.0") is False, "thấp hơn"
assert updater.is_newer("1.0.0", "1.0.0") is False, "bằng nhau"
assert updater.is_newer("v2.0.0", "1.9.9") is True, "bỏ tiền tố v vẫn so đúng"
# Khác số nhóm: pad 0 cho cùng độ dài (BUG1) — "1.2.0" == "1.2", "0.1" == "0.1.0".
assert updater.is_newer("1.2.0", "1.2") is False, "1.2.0 == 1.2 (pad 0)"
assert updater.is_newer("0.1", "0.1.0") is False, "0.1 == 0.1.0 (pad 0)"
assert updater.is_newer("1.3", "1.2.5") is True, "1.3 > 1.2.5"
assert updater.is_newer("1.2.1", "1.2") is True, "1.2.1 > 1.2"
print("OK: is_newer")


class _FakeResp:
    """Giả lập đối tượng trả về của urlopen (hỗ trợ context manager)."""

    def __init__(self, payload: bytes):
        self._buf = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._buf.read()


def _patch(fake):
    """Đổi urlopen, trả hàm khôi phục."""
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    return orig


# --- ca 1: có bản mới ---
def _open_new(req, timeout=None):
    body = json.dumps(
        {"version": "9.9.9", "url": "https://dl/x", "notes": "Bản vá lớn"}
    ).encode("utf-8")
    return _FakeResp(body)


orig = _patch(_open_new)
try:
    info = updater.check_for_updates("0.1.0", manifest_url="http://x/latest.json")
finally:
    urllib.request.urlopen = orig
assert info.available is True, "9.9.9 phải mới hơn 0.1.0"
assert info.latest == "9.9.9"
assert info.url == "https://dl/x"
assert info.notes == "Bản vá lớn"
assert info.error is None
print("OK: check_for_updates (có bản mới)")

# --- ca 2: đã mới nhất ---
def _open_same(req, timeout=None):
    body = json.dumps({"version": "0.1.0", "url": "https://dl/x"}).encode("utf-8")
    return _FakeResp(body)


orig = _patch(_open_same)
try:
    info = updater.check_for_updates("0.1.0", manifest_url="http://x/latest.json")
finally:
    urllib.request.urlopen = orig
assert info.available is False, "cùng version -> không có bản mới"
assert info.latest == "0.1.0"
assert info.error is None
print("OK: check_for_updates (đã mới nhất)")

# --- ca 3: lỗi mạng ---
def _open_err(req, timeout=None):
    raise urllib.error.URLError("no network")


orig = _patch(_open_err)
try:
    info = updater.check_for_updates("0.1.0", manifest_url="http://x/latest.json")
finally:
    urllib.request.urlopen = orig
assert info.available is False, "lỗi mạng -> không có bản mới"
assert info.error is not None, "phải set error thân thiện"
assert isinstance(info.error, str) and info.error, "error là chuỗi không rỗng"
print(f"OK: check_for_updates (lỗi mạng) -> {info.error!r}")

# --- ca 4: JSON hỏng (không crash) ---
def _open_badjson(req, timeout=None):
    return _FakeResp(b"{not-json")


orig = _patch(_open_badjson)
try:
    info = updater.check_for_updates("0.1.0", manifest_url="http://x/latest.json")
finally:
    urllib.request.urlopen = orig
assert info.available is False and info.error is not None, "JSON hỏng -> error, không crash"
print("OK: check_for_updates (JSON hỏng)")

print("=== UPDATER OK ===")
