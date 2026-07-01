"""Bootstrap dùng chung cho các script trong scripts/.

Cho phép chạy thẳng `python scripts/<ten>.py` từ thư mục gốc trên CMD mặc định:
- Chèn project root vào sys.path để import được package `app`
  (tránh ModuleNotFoundError: No module named 'app').
- Ép stdout/stderr về UTF-8 để in tiếng Việt không lỗi cp932 trên Windows.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
