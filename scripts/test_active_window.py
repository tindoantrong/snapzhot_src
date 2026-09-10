"""Test "Chụp cửa sổ đang dùng" (ACTIVE-WIN): active_window_target + slot điều khiển.

Phần 1 — logic thuần, monkeypatch win32gui/win32con/_HAS_WIN32 tại module
window_selector (giống test_window_zorder.py) nên chạy được cả trên máy KHÔNG
có pywin32.
Phần 2 — luồng controller offscreen: debounce, guard dialog, thiếu pywin32.
Phần 3-4 — không đăng ký phím tắt; nút trên toolbar Editor nối đúng slot.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import types
import unittest.mock as mock
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

# Config tạm TRƯỚC khi import bên dùng → không đụng config thật của user.
_tmp_cfg = Path(tempfile.mktemp(suffix="_test_active_window.json"))
import app.common.config as _cfg_mod
_cfg_mod.config_path = lambda: _tmp_cfg

import app.capture.capture_manager as _cm
import app.capture.window_selector as _ws

# Vùng ảo cố định để kiểm tra clamp không phụ thuộc màn hình máy chạy test.
VIRTUAL = {"left": 0, "top": 0, "width": 1920, "height": 1080}


# ---------- helper: fake win32 theo Z-order + foreground ----------

def _make_win32(windows: list[dict], foreground: int = 0):
    """windows: list dict theo Z-order trên-xuống.
      {hwnd, visible, iconic, title, rect=(l,t,r,b), cls, own, cloaked}
    """
    by_hwnd = {w["hwnd"]: w for w in windows}
    hwnds = [w["hwnd"] for w in windows]
    GW_HWNDNEXT = 2

    def GetWindow(hwnd, flag):
        assert flag == GW_HWNDNEXT
        idx = hwnds.index(hwnd)
        return hwnds[idx + 1] if idx + 1 < len(hwnds) else 0

    gui = types.SimpleNamespace(
        GetTopWindow=lambda desktop: hwnds[0] if hwnds else 0,
        GetWindow=GetWindow,
        GetForegroundWindow=lambda: foreground,
        IsWindowVisible=lambda h: by_hwnd[h]["visible"],
        IsIconic=lambda h: by_hwnd[h].get("iconic", False),
        GetWindowText=lambda h: by_hwnd[h].get("title", ""),
        GetWindowRect=lambda h: by_hwnd[h]["rect"],
        GetClassName=lambda h: by_hwnd[h].get("cls", "Chrome_WidgetWin_1"),
    )
    con = types.SimpleNamespace(GW_HWNDNEXT=GW_HWNDNEXT)
    return gui, con, by_hwnd


def _target(windows, foreground=0, *, has_win32=True, dwm_rect=None):
    """Gọi active_window_target() với win32 giả + DWM giả."""
    gui, con, by_hwnd = _make_win32(windows, foreground)

    def fake_extended(hwnd):
        return dwm_rect if dwm_rect is not None else None

    with mock.patch.object(_ws, "_HAS_WIN32", has_win32), \
         mock.patch.object(_ws, "win32gui", gui if has_win32 else None), \
         mock.patch.object(_ws, "win32con", con if has_win32 else None), \
         mock.patch.object(_ws, "_extended_frame_rect", fake_extended), \
         mock.patch.object(_ws, "_is_own_process",
                           lambda h: by_hwnd.get(h, {}).get("own", False)), \
         mock.patch.object(_ws, "_is_cloaked",
                           lambda h: by_hwnd.get(h, {}).get("cloaked", False)), \
         mock.patch.object(_cm, "virtual_screen_geometry", lambda: VIRTUAL):
        return _ws.active_window_target()


APP = {"hwnd": 10, "visible": True, "title": "Chrome", "rect": (100, 100, 900, 700)}
APP_RECT = QRect(100, 100, 800, 600)
OTHER = {"hwnd": 20, "visible": True, "title": "Excel", "rect": (0, 0, 600, 400)}
OTHER_RECT = QRect(0, 0, 600, 400)

# ---------- CA 1: foreground hợp lệ → chụp thẳng ----------
res = _target([APP, OTHER], foreground=10)
assert res == (10, APP_RECT, True), f"foreground hợp lệ phải trả thẳng: {res}"
print("OK: foreground hợp lệ → (hwnd, rect, from_foreground=True)")

# ---------- CA 2: foreground là cửa sổ CỦA CHÍNH APP → lùi về Z-order ----------
own = dict(APP, own=True)
res = _target([own, OTHER], foreground=10)
assert res == (20, OTHER_RECT, False), f"phải bỏ cửa sổ của chính app: {res}"
print("OK: foreground thuộc process mình → fallback Z-order (from_foreground=False)")

# ---------- CA 3: foreground = 0 (khoá máy/UAC/Alt-Tab) → fallback ----------
res = _target([APP, OTHER], foreground=0)
assert res == (10, APP_RECT, False), f"fg=0 phải fallback topmost: {res}"
print("OK: GetForegroundWindow()=0 → fallback, không crash")

# ---------- CA 4: foreground thu nhỏ / ẩn / không tiêu đề → fallback ----------
for bad in ({"iconic": True}, {"visible": False}, {"title": ""}):
    res = _target([dict(APP, **bad), OTHER], foreground=10)
    assert res == (20, OTHER_RECT, False), f"{bad} phải bị loại: {res}"
print("OK: foreground iconic/invisible/không tiêu đề → fallback")

# ---------- CA 5: cửa sổ ma (cloaked) → fallback ----------
res = _target([dict(APP, cloaked=True), OTHER], foreground=10)
assert res == (20, OTHER_RECT, False), f"cửa sổ cloaked phải bị loại: {res}"
print("OK: cửa sổ cloaked (UWP ma / desktop ảo khác) → fallback")

# ---------- CA 6: cửa sổ shell (desktop, taskbar, Start) → fallback ----------
for cls in ("Progman", "WorkerW", "Shell_TrayWnd", "Windows.UI.Core.CoreWindow"):
    res = _target([dict(APP, cls=cls), OTHER], foreground=10)
    assert res == (20, OTHER_RECT, False), f"class {cls} phải bị loại: {res}"
print("OK: cửa sổ shell (Progman/WorkerW/taskbar/Start) → fallback")

# ---------- CA 7: không cửa sổ nào hợp lệ → None ----------
assert _target([], foreground=0) is None, "không có cửa sổ → None"
assert _target([dict(APP, own=True)], foreground=10) is None, \
    "chỉ có cửa sổ của chính app → None"
print("OK: không có cửa sổ hợp lệ → None")

# ---------- CA 8: thiếu pywin32 → None ngay ----------
assert _target([APP], foreground=10, has_win32=False) is None
print("OK: _HAS_WIN32=False → None (máy không có pywin32 vẫn chạy được)")

# ---------- CA 9: ưu tiên khung DWM (bỏ viền resize vô hình) ----------
res = _target([APP], foreground=10, dwm_rect=QRect(107, 100, 786, 593))
assert res == (10, QRect(107, 100, 786, 593), True), \
    f"phải ưu tiên DWM frame bounds hơn GetWindowRect: {res}"
print("OK: DWM EXTENDED_FRAME_BOUNDS được ưu tiên (ảnh không dính viền/bóng)")

# ---------- CA 10: clamp về vùng ảo (cửa sổ maximize lố ra ngoài) ----------
over = {"hwnd": 30, "visible": True, "title": "Max", "rect": (-8, -8, 1928, 1088)}
res = _target([over], foreground=30)
assert res == (30, QRect(0, 0, 1920, 1080), True), f"phải cắt về vùng ảo: {res}"
print("OK: rect lố ra ngoài vùng ảo → clamp đúng")

# ---------- CA 11: cửa sổ nằm hoàn toàn ngoài vùng ảo → bỏ qua ----------
ghost = {"hwnd": 40, "visible": True, "title": "Ghost", "rect": (5000, 5000, 5800, 5600)}
res = _target([ghost, OTHER], foreground=40)
assert res == (20, OTHER_RECT, False), f"cửa sổ ngoài màn hình phải bị bỏ: {res}"
print("OK: cửa sổ ngoài vùng ảo → bỏ qua, lấy cửa sổ hợp lệ kế tiếp")

# ---------- Phần 2: luồng controller ----------
import app.app_controller as _ac
from app.app_controller import AppController

ctrl = AppController()
shots = []
ctrl._handle_new_capture = lambda img: shots.append(img)

RECT = QRect(0, 0, 50, 40)


def _run_capture(target=(1, RECT, True), available=True):
    with mock.patch.object(_ac, "active_window_target", lambda: target), \
         mock.patch.object(_ac, "window_capture_available", lambda: available):
        ctrl.capture_active_window()


# Nhánh foreground: chụp NGAY, không cần timer.
ctrl._last_active_window_capture = 0.0
_run_capture()
assert len(shots) == 1, f"foreground hợp lệ phải chụp ngay 1 ảnh: {len(shots)}"
assert not shots[0].isNull() and shots[0].width() > 0
print(f"OK: nhánh foreground chụp ngay → QImage {shots[0].width()}x{shots[0].height()}")

# Debounce: gọi lại ngay lập tức (auto-repeat khi giữ phím) → KHÔNG chụp thêm.
_run_capture()
_run_capture()
assert len(shots) == 1, f"debounce phải chặn auto-repeat, got {len(shots)} ảnh"
print("OK: giữ phím (auto-repeat) chỉ ra 1 ảnh — debounce hoạt động")

# Hết cửa sổ debounce → chụp lại được.
shots.clear()
ctrl._last_active_window_capture = 0.0
_run_capture()
assert len(shots) == 1, "qua thời gian debounce phải chụp lại được"
print("OK: qua thời gian debounce → chụp lại bình thường")

# Guard: dialog phím tắt đang mở → không chụp.
shots.clear()
ctrl._last_active_window_capture = 0.0
ctrl._hotkey_dialog_open = True
_run_capture()
assert not shots, "dialog phím tắt đang mở thì không được chụp"
ctrl._hotkey_dialog_open = False
print("OK: dialog phím tắt đang mở → bỏ qua (không kẹt chế độ chụp)")

# Thiếu pywin32 → báo nhẹ nhàng, không crash, không chụp.
shots.clear()
ctrl._last_active_window_capture = 0.0
_run_capture(available=False)
assert not shots, "thiếu pywin32 thì không chụp"
print("OK: thiếu pywin32 → thông báo, không crash")

# Không tìm được cửa sổ nào → không chụp, không crash.
shots.clear()
ctrl._last_active_window_capture = 0.0
_run_capture(target=None)
assert not shots, "không có cửa sổ đích thì không chụp"
print("OK: không tìm thấy cửa sổ → thông báo, không crash")

# _grab_window: khung đọc lại hụt thì lùi về khung đã biết.
shots.clear()
with mock.patch.object(_ac, "window_frame_rect", lambda h: None):
    ctrl._grab_window(1, RECT)
assert len(shots) == 1, "đọc lại khung hụt phải lùi về fallback_rect"
print("OK: _grab_window lùi về khung đã biết khi đọc lại hụt")

# ---------- Phần 3: KHÔNG được đăng ký phím tắt cho chế độ này ----------
# Quyết định: chụp app đang dùng chỉ qua NÚT (toolbar Editor) + menu khay.
# Test này canh cho phím tắt không bị thêm lại một cách vô tình.
import sys as _sys
import types as _types

_registered = []
_fake_kb = _types.ModuleType("keyboard")
_fake_kb.KEY_DOWN = "down"
_fake_kb.add_hotkey = lambda key, cb, **kw: (_registered.append(("add_hotkey", key, cb)), "h")[1]
_fake_kb.hook_key = lambda key, cb, **kw: (_registered.append(("hook_key", key, cb)), (lambda: None))[1]
_fake_kb.remove_hotkey = lambda h: None
_fake_kb.remove_all_hotkeys = lambda: _registered.append(("remove_all", None, None))
_sys.modules["keyboard"] = _fake_kb

ctrl.install_global_hotkeys()
_keys = {k for kind, k, _ in _registered if kind in ("add_hotkey", "hook_key")}
assert "ctrl+alt+w" not in _keys, f"không được đăng ký phím tắt chụp app: {_keys}"
assert not hasattr(ctrl, "request_active_window"),     "signal request_active_window chỉ phục vụ luồng hotkey — phải gỡ cùng phím tắt"
assert "hotkey_window" not in _cfg_mod.DEFAULTS, "config không được còn key hotkey_window"
print("OK: không đăng ký phím tắt cho chụp app (chỉ dùng nút)")

# Các phím tắt CŨ phải còn nguyên — gỡ phím mới không được đụng chúng.
assert "print screen" in _keys, f"phải giữ hotkey chụp vùng: {_keys}"
assert "ctrl+shift+r" in _keys, f"phải giữ hotkey quay video: {_keys}"
print("OK: hotkey chụp vùng (PrtSc) + quay video (Ctrl+Shift+R) vẫn còn")

# ---------- Phần 4: nút "Chụp app đang dùng" trên toolbar Editor ----------
from PySide6.QtGui import QAction as _QAction
_actions = {a.text(): a for a in ctrl.editor.findChildren(_QAction)}
assert "Chụp app đang dùng" in _actions,     f"toolbar Editor phải có nút Chụp app đang dùng: {sorted(_actions)}"
_act = _actions["Chụp app đang dùng"]
assert not _act.icon().isNull(), "nút phải có icon (capture_window)"
assert "Ctrl" not in _act.toolTip(), f"tooltip không được nhắc phím tắt nữa: {_act.toolTip()!r}"
assert "Editor" in _act.toolTip(), f"tooltip phải nói rõ chụp cửa sổ sau Editor: {_act.toolTip()!r}"
print("OK: Editor có nút 'Chụp app đang dùng' (có icon + tooltip đúng)")

# Bấm nút → phải chạy đúng slot capture_active_window (không phải chụp vùng/toàn màn hình).
_calls = []
_orig_slot = ctrl.capture_active_window
ctrl.capture_active_window = lambda: _calls.append(1)
ctrl.editor.request_capture_active_window.disconnect()
ctrl.editor.request_capture_active_window.connect(ctrl.capture_active_window)
_act.trigger()
app.processEvents()
assert _calls, "bấm nút phải gọi capture_active_window"
ctrl.capture_active_window = _orig_slot
print("OK: bấm nút → capture_active_window (đúng slot, không phải chụp vùng/toàn màn hình)")

if _tmp_cfg.exists():
    _tmp_cfg.unlink()

print("=== ACTIVE WINDOW CAPTURE OK ===")
print("LƯU Ý: bấm nút thật + Z-order thật = LIVE-ONLY (user eyes-test).")
