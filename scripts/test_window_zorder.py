"""Test window_rect_at_point dùng GetTopWindow+GW_HWNDNEXT (Z-order đảm bảo).

Monkeypatch toàn bộ win32gui/win32con/`_HAS_WIN32` tại module window_selector
để chạy offscreen không cần Windows API thật.
"""
import _bootstrap  # noqa: F401

import types
import unittest.mock as mock

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import app.capture.window_selector as _ws

# ---------- helper: dựng fake win32 từ danh sách hwnd theo Z-order ----------

def _make_win32(windows: list[dict], *, raise_top=False):
    """
    windows: list[dict] theo thứ tự Z-order trên-xuống-dưới.
      Mỗi dict: {hwnd, visible, iconic, title, rect=(l,t,r,b)}
    raise_top: GetTopWindow throw Exception.
    Trả (fake_gui, fake_con).
    """
    by_hwnd = {w["hwnd"]: w for w in windows}
    hwnds = [w["hwnd"] for w in windows]   # Z-order list

    GW_HWNDNEXT = 2

    def GetTopWindow(desktop):
        if raise_top:
            raise OSError("fake error")
        return hwnds[0] if hwnds else 0

    def GetWindow(hwnd, flag):
        assert flag == GW_HWNDNEXT
        idx = hwnds.index(hwnd)
        return hwnds[idx + 1] if idx + 1 < len(hwnds) else 0

    def IsWindowVisible(hwnd):
        return by_hwnd[hwnd]["visible"]

    def IsIconic(hwnd):
        return by_hwnd[hwnd].get("iconic", False)

    def GetWindowText(hwnd):
        return by_hwnd[hwnd].get("title", "")

    def GetWindowRect(hwnd):
        return by_hwnd[hwnd]["rect"]  # (left, top, right, bottom)

    gui = types.SimpleNamespace(
        GetTopWindow=GetTopWindow,
        GetWindow=GetWindow,
        IsWindowVisible=IsWindowVisible,
        IsIconic=IsIconic,
        GetWindowText=GetWindowText,
        GetWindowRect=GetWindowRect,
    )
    con = types.SimpleNamespace(GW_HWNDNEXT=GW_HWNDNEXT)
    return gui, con


def _call(windows, x, y, exclude=0, *, raise_top=False, has_win32=True):
    gui, con = _make_win32(windows, raise_top=raise_top)
    with mock.patch.object(_ws, "_HAS_WIN32", has_win32), \
         mock.patch.object(_ws, "win32gui", gui if has_win32 else None), \
         mock.patch.object(_ws, "win32con", con if has_win32 else None):
        return _ws.window_rect_at_point(x, y, exclude)


# ---------- CA 1: 2 cửa sổ chồng nhau → trả cửa sổ TRÊN CÙNG ----------

wins_overlap = [
    {"hwnd": 10, "visible": True, "title": "Top",    "rect": (0, 0, 800, 600)},
    {"hwnd": 20, "visible": True, "title": "Bottom", "rect": (0, 0, 800, 600)},
]
result = _call(wins_overlap, 400, 300)
assert result == QRect(0, 0, 800, 600), f"Phải trả rect hwnd=10 (top): {result}"
# Đảm bảo KHÔNG phải chỉ tình cờ: kiểm tra hwnd được chọn bằng cách để rect khác nhau
wins_diff = [
    {"hwnd": 10, "visible": True, "title": "Top",    "rect": (0,   0, 400, 300)},
    {"hwnd": 20, "visible": True, "title": "Bottom", "rect": (0,   0, 800, 600)},
]
result = _call(wins_diff, 500, 400)   # điểm (500,400) chỉ nằm trong hwnd=20
assert result == QRect(0, 0, 800, 600), f"Phải trả hwnd=20 (duy nhất chứa điểm): {result}"
result = _call(wins_diff, 200, 200)   # điểm nằm trong cả 2, trả hwnd=10 (top)
assert result == QRect(0, 0, 400, 300), f"Phải trả hwnd=10 (topmost tại điểm 200,200): {result}"
print("OK: 2 cửa sổ chồng nhau → trả cửa sổ TRÊN CÙNG (topmost-first)")

# ---------- CA 2: loại trừ exclude_hwnd ----------

wins_excl = [
    {"hwnd": 99, "visible": True, "title": "Overlay", "rect": (0, 0, 1920, 1080)},
    {"hwnd": 10, "visible": True, "title": "App",     "rect": (100, 100, 500, 400)},
]
result = _call(wins_excl, 300, 200, exclude=99)
assert result == QRect(100, 100, 400, 300), \
    f"hwnd=99 phải bị loại, trả hwnd=10: {result}"
print("OK: exclude_hwnd bị loại, trả cửa sổ kế tiếp hợp lệ")

# ---------- CA 3: loại cửa sổ invisible / iconic / không tiêu đề ----------

wins_filter = [
    {"hwnd": 1, "visible": False, "title": "Invis",   "rect": (0, 0, 800, 600)},
    {"hwnd": 2, "visible": True,  "iconic": True,  "title": "Iconic",  "rect": (0, 0, 800, 600)},
    {"hwnd": 3, "visible": True,  "title": "",          "rect": (0, 0, 800, 600)},
    {"hwnd": 4, "visible": True,  "title": "Valid",     "rect": (0, 0, 800, 600)},
]
result = _call(wins_filter, 400, 300)
assert result == QRect(0, 0, 800, 600), \
    f"3 cửa sổ đầu bị lọc, phải trả hwnd=4: {result}"
# Kiểm tra nếu hwnd=4 cũng bị kích thước 0
wins_zero = [
    {"hwnd": 1, "visible": True, "title": "ZeroW", "rect": (0, 0, 0, 600)},
    {"hwnd": 2, "visible": True, "title": "ZeroH", "rect": (0, 0, 800, 0)},
    {"hwnd": 3, "visible": True, "title": "OK",    "rect": (0, 0, 800, 600)},
]
result = _call(wins_zero, 400, 300)
assert result == QRect(0, 0, 800, 600), \
    f"cửa sổ kích thước 0 bị lọc, trả hwnd=3: {result}"
print("OK: invisible/iconic/no-title/zero-size bị lọc đúng")

# ---------- CA 4: điểm ngoài mọi cửa sổ → None ----------

wins_no_match = [
    {"hwnd": 10, "visible": True, "title": "Win", "rect": (100, 100, 500, 400)},
]
result = _call(wins_no_match, 10, 10)   # điểm (10,10) ngoài rect
assert result is None, f"Không cửa sổ nào chứa điểm, phải trả None: {result}"
print("OK: điểm ngoài mọi cửa sổ → None")

# ---------- CA 5: thiếu win32 (_HAS_WIN32 = False) → None ngay ----------

result = _call(wins_no_match, 400, 300, has_win32=False)
assert result is None, f"Thiếu win32 phải trả None: {result}"
print("OK: _HAS_WIN32=False → None ngay")

# ---------- CA 6: GetTopWindow throw → None ----------

result = _call(wins_overlap, 400, 300, raise_top=True)
assert result is None, f"GetTopWindow lỗi phải trả None: {result}"
print("OK: GetTopWindow throw → None")

# ---------- CA 7: danh sách rỗng → None ----------

result = _call([], 400, 300)
assert result is None, f"Không có cửa sổ → None: {result}"
print("OK: danh sách cửa sổ rỗng → None")

print("=== WINDOW Z-ORDER (GetTopWindow+GW_HWNDNEXT) OK ===")
print("LƯU Ý: Z-order thật với cửa sổ desktop thật = LIVE-ONLY (user eyes-test).")
