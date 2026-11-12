"""Vẽ con trỏ chuột + hiệu ứng click lên frame video (Windows).

mss/BitBlt KHÔNG chụp con trỏ → video quay ra không thấy chuột. Mỗi frame:
1. Click đang giữ (hoặc vừa nhả, mờ dần ~0.35s) → vẽ vòng tròn màu quanh mũi
   chuột: trái = vàng, phải = xanh.
2. Vẽ CHÍNH con trỏ hệ thống hiện tại (mũi tên, bàn tay, I-beam…) bằng
   DrawIconEx lên một mảnh nhỏ của frame → đúng hình, đúng cả con trỏ đảo màu.

Toạ độ: GetCursorPos trả pixel vật lý (mss đã bật DPI-aware cho tiến trình),
cùng hệ với vùng quay ``{left, top, width, height}`` của mss.
Không phải Windows / lỗi API → no-op, video vẫn quay bình thường.
"""
from __future__ import annotations

import ctypes
import sys
import time

import numpy as np

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32

    class _CURSORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("hCursor", wintypes.HANDLE), ("ptScreenPos", wintypes.POINT)]

    class _ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD),
                    ("yHotspot", wintypes.DWORD), ("hbmMask", wintypes.HBITMAP),
                    ("hbmColor", wintypes.HBITMAP)]

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    _user32.GetCursorInfo.argtypes = [ctypes.POINTER(_CURSORINFO)]
    _user32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ICONINFO)]
    _user32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                                   wintypes.HANDLE, ctypes.c_int, ctypes.c_int,
                                   wintypes.UINT, wintypes.HANDLE, wintypes.UINT]
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    _gdi32.CreateCompatibleDC.restype = wintypes.HDC
    _gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                        ctypes.POINTER(ctypes.c_void_p),
                                        wintypes.HANDLE, wintypes.DWORD]
    _gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    _gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    _gdi32.SelectObject.restype = wintypes.HGDIOBJ
    _gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _gdi32.DeleteDC.argtypes = [wintypes.HDC]
    _gdi32.GdiFlush.argtypes = []

_CURSOR_SHOWING = 0x1
_DI_NORMAL = 0x3
_VK_LBUTTON, _VK_RBUTTON = 0x01, 0x02
_PATCH = 128            # mảnh frame để vẽ con trỏ (đủ cho con trỏ phóng to)
_CLICK_RADIUS = 22
_CLICK_FADE_S = 0.35
_LEFT_COLOR = (0, 200, 255)    # BGR: vàng
_RIGHT_COLOR = (255, 140, 30)  # BGR: xanh dương


def _ring_masks(r: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.sqrt(xx * xx + yy * yy)
    fill = (d <= r - 3).astype(np.float32)
    ring = ((d > r - 3) & (d <= r)).astype(np.float32)
    return fill, ring


class CursorOverlay:
    """Gọi ``draw(frame_bgra, left, top)`` mỗi frame (frame phải ghi được)."""

    def __init__(self) -> None:
        self.enabled = _IS_WIN
        self._fill, self._ring = _ring_masks(_CLICK_RADIUS)
        self._last_click_t = 0.0
        self._last_click_color = _LEFT_COLOR
        self._hdc = None
        self._hbmp = None
        self._bits = None
        if self.enabled:
            try:
                self._init_gdi()
            except Exception:
                self.enabled = False

    # ----- GDI: một DIB 32bpp top-down cỡ _PATCH, tái dùng mọi frame -----
    def _init_gdi(self) -> None:
        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = _PATCH
        bmi.biHeight = -_PATCH  # âm = top-down, khớp thứ tự hàng của numpy
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bits = ctypes.c_void_p()
        self._hdc = _gdi32.CreateCompatibleDC(None)
        self._hbmp = _gdi32.CreateDIBSection(self._hdc, ctypes.byref(bmi), 0,
                                             ctypes.byref(bits), None, 0)
        if not self._hdc or not self._hbmp or not bits.value:
            raise OSError("CreateDIBSection lỗi")
        _gdi32.SelectObject(self._hdc, self._hbmp)
        buf = (ctypes.c_uint8 * (_PATCH * _PATCH * 4)).from_address(bits.value)
        self._bits = np.frombuffer(buf, dtype=np.uint8).reshape(_PATCH, _PATCH, 4)

    def close(self) -> None:
        if self._hbmp:
            _gdi32.DeleteObject(self._hbmp)
            self._hbmp = None
        if self._hdc:
            _gdi32.DeleteDC(self._hdc)
            self._hdc = None
        self._bits = None
        self.enabled = False

    # ----- vẽ -----
    def draw(self, frame: np.ndarray, left: int, top: int) -> None:
        if not self.enabled:
            return
        try:
            info = _CURSORINFO()
            info.cbSize = ctypes.sizeof(_CURSORINFO)
            if not _user32.GetCursorInfo(ctypes.byref(info)):
                return
            x = info.ptScreenPos.x - left
            y = info.ptScreenPos.y - top
            self._draw_click(frame, x, y)
            if info.flags & _CURSOR_SHOWING and info.hCursor:
                self._draw_icon(frame, info.hCursor, x, y)
        except Exception:
            self.enabled = False  # lỗi API → tắt hẳn, không làm hỏng video

    def _draw_click(self, frame: np.ndarray, x: int, y: int) -> None:
        now = time.perf_counter()
        if _user32.GetAsyncKeyState(_VK_LBUTTON) & 0x8000:
            self._last_click_t, self._last_click_color = now, _LEFT_COLOR
        elif _user32.GetAsyncKeyState(_VK_RBUTTON) & 0x8000:
            self._last_click_t, self._last_click_color = now, _RIGHT_COLOR
        age = now - self._last_click_t
        if age > _CLICK_FADE_S:
            return
        strength = 1.0 - age / _CLICK_FADE_S
        r = _CLICK_RADIUS
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = max(x - r, 0), max(y - r, 0), min(x + r + 1, w), min(y + r + 1, h)
        if x0 >= x1 or y0 >= y1:
            return
        mx0, my0 = x0 - (x - r), y0 - (y - r)
        sl = (slice(my0, my0 + (y1 - y0)), slice(mx0, mx0 + (x1 - x0)))
        alpha = (self._fill[sl] * 0.40 + self._ring[sl] * 0.95) * strength
        region = frame[y0:y1, x0:x1, :3].astype(np.float32)
        color = np.array(self._last_click_color, dtype=np.float32)
        a = alpha[..., None]
        frame[y0:y1, x0:x1, :3] = (region * (1 - a) + color * a).astype(np.uint8)

    def _draw_icon(self, frame: np.ndarray, hcursor, x: int, y: int) -> None:
        ii = _ICONINFO()
        if not _user32.GetIconInfo(hcursor, ctypes.byref(ii)):
            return
        hx, hy = ii.xHotspot, ii.yHotspot
        # GetIconInfo tạo bitmap mới mỗi lần → phải xoá, không thì rò GDI.
        if ii.hbmMask:
            _gdi32.DeleteObject(ii.hbmMask)
        if ii.hbmColor:
            _gdi32.DeleteObject(ii.hbmColor)
        # Góc trên-trái của con trỏ trong frame; mảnh _PATCH bắt đầu từ đó.
        cx, cy = x - hx, y - hy
        h, w = frame.shape[:2]
        x0, y0 = max(cx, 0), max(cy, 0)
        x1, y1 = min(cx + _PATCH, w), min(cy + _PATCH, h)
        if x0 >= x1 or y0 >= y1:
            return
        px, py = x0 - cx, y0 - cy
        pw, ph = x1 - x0, y1 - y0
        # Chép nền thật vào DIB → DrawIconEx (AND/XOR mask chuẩn) → chép ngược ra.
        self._bits[py:py + ph, px:px + pw] = frame[y0:y1, x0:x1]
        _user32.DrawIconEx(self._hdc, 0, 0, hcursor, 0, 0, 0, None, _DI_NORMAL)
        _gdi32.GdiFlush()
        frame[y0:y1, x0:x1, :3] = self._bits[py:py + ph, px:px + pw, :3]
