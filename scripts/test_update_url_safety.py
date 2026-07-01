"""Test headless cho app/updater.is_safe_update_url — không cần mạng, không build thật.

Kiểm tra:
  1. True cho https://github.com/... (URL hợp lệ)
  2. True cho https://www.github.com/... (subdomain hợp lệ)
  3. False cho http://github.com/... (không phải https)
  4. False cho file:///path/to/exe
  5. False cho javascript:alert(1)
  6. False cho https://evil.com/...
  7. False cho https://github.com.evil.com/... (giả mạo domain)
  8. False cho chuỗi rỗng ""
  9. False cho None
"""
import os
import sys

import _bootstrap  # noqa: F401  (sys.path + UTF-8)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.updater import is_safe_update_url  # noqa: E402

# -----------------------------------------------------------------------
# 1. https://github.com/... → True
# -----------------------------------------------------------------------
assert is_safe_update_url(
    "https://github.com/tindoantrong/snapzhot_src/releases/latest/download/SnagTin-Setup-0.1.1.exe"
) is True, "https://github.com/... phải trả True"
print("OK: https://github.com/... → True")

# -----------------------------------------------------------------------
# 2. https://www.github.com/... → True
# -----------------------------------------------------------------------
assert is_safe_update_url(
    "https://www.github.com/tindoantrong/snapzhot_src/releases/latest/download/file.exe"
) is True, "https://www.github.com/... phải trả True"
print("OK: https://www.github.com/... → True")

# -----------------------------------------------------------------------
# 3. http:// → False
# -----------------------------------------------------------------------
assert is_safe_update_url(
    "http://github.com/tindoantrong/snapzhot_src/releases/latest/download/file.exe"
) is False, "http://... phải trả False"
print("OK: http://github.com/... → False")

# -----------------------------------------------------------------------
# 4. file:// → False
# -----------------------------------------------------------------------
assert is_safe_update_url("file:///C:/malware.exe") is False, "file:// phải trả False"
print("OK: file:///... → False")

# -----------------------------------------------------------------------
# 5. javascript: → False
# -----------------------------------------------------------------------
assert is_safe_update_url("javascript:alert(1)") is False, "javascript: phải trả False"
print("OK: javascript:alert(1) → False")

# -----------------------------------------------------------------------
# 6. https://evil.com → False
# -----------------------------------------------------------------------
assert is_safe_update_url("https://evil.com/malware.exe") is False, (
    "https://evil.com/... phải trả False"
)
print("OK: https://evil.com/... → False")

# -----------------------------------------------------------------------
# 7. https://github.com.evil.com → False (giả mạo domain)
# -----------------------------------------------------------------------
assert is_safe_update_url(
    "https://github.com.evil.com/tindoantrong/snapzhot_src/releases/latest/download/file.exe"
) is False, "https://github.com.evil.com/... phải trả False"
print("OK: https://github.com.evil.com/... → False (giả mạo domain bị chặn)")

# -----------------------------------------------------------------------
# 8. Chuỗi rỗng → False
# -----------------------------------------------------------------------
assert is_safe_update_url("") is False, "chuỗi rỗng phải trả False"
print('OK: "" → False')

# -----------------------------------------------------------------------
# 9. None → False
# -----------------------------------------------------------------------
assert is_safe_update_url(None) is False, "None phải trả False"
print("OK: None → False")

print()
print("=== TEST UPDATE URL SAFETY OK ===")
