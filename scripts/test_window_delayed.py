"""Test Chụp cửa sổ + Chụp hẹn giờ (offscreen, không cần thao tác tay)."""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage

app = QApplication([])

from app.capture import window_selector as ws
from app.capture.countdown_overlay import CountdownOverlay

# --- window_selector: import + logic lọc/đổi toạ độ không lỗi ---
assert isinstance(ws.window_capture_available(), bool)
print("OK: window_capture_available() =", ws.window_capture_available())

# window_rect_at_point chạy không lỗi, trả None hoặc QRect.
r = ws.window_rect_at_point(0, 0)
assert r is None or isinstance(r, QRect), f"phải None hoặc QRect, got {type(r)}"
# Điểm rất xa ngoài màn hình -> không có cửa sổ.
r_far = ws.window_rect_at_point(10**6, 10**6)
assert r_far is None, "điểm ngoài mọi cửa sổ phải trả None"
print("OK: window_rect_at_point chạy không lỗi (mọi nền tảng)")

# Tạo WindowSelector + kiểm tra đổi toạ độ virtual->widget không lỗi.
sel = ws.WindowSelector()
captured_rects = []
sel.window_selected.connect(lambda rect: captured_rects.append(rect))
cancelled = []
sel.cancelled.connect(lambda: cancelled.append(True))
# Khi thiếu win32, start() phải huỷ nhẹ nhàng (không hiện overlay vô dụng).
if not ws.window_capture_available():
    sel.start()
    assert cancelled, "thiếu pywin32: start() phải phát cancelled"
    print("OK: fallback thiếu pywin32 -> cancelled, không crash")
else:
    # Có win32: _detect chạy không lỗi cho 1 điểm bất kỳ.
    rect = sel._detect(100, 100)
    assert rect is None or isinstance(rect, QRect)
    print("OK: WindowSelector._detect chạy không lỗi với pywin32")

# --- CountdownOverlay: hiển thị + vẽ không lỗi ---
ov = CountdownOverlay()
ov.show_count(3)
assert ov._value == 3
pix = ov.grab()  # buộc paintEvent chạy
assert not pix.isNull(), "grab overlay đếm ngược phải ra pixmap hợp lệ"
ov.hide()
print("OK: CountdownOverlay hiển thị + paint không lỗi")

# --- Logic đếm ngược -> kích hoạt chụp tạo QImage hợp lệ ---
from app.app_controller import AppController

ctrl = AppController()
captured_images = []
# Chặn luồng mở Editor/ghi thư viện: chỉ lấy ảnh để kiểm tra.
ctrl._handle_new_capture = lambda img: captured_images.append(img)

ctrl.capture_fullscreen_delayed(2)
assert ctrl._delay_timer.isActive(), "đếm ngược phải đang chạy"
assert ctrl._delay_remaining == 2

# Mô phỏng các nhịp 1 giây thay vì chờ thật.
ctrl._on_delay_tick()  # 2 -> 1
assert ctrl._delay_remaining == 1
assert ctrl._delay_timer.isActive(), "còn 1s thì vẫn đang đếm"
ctrl._on_delay_tick()  # 1 -> 0 -> chụp
assert not ctrl._delay_timer.isActive(), "hết giờ phải dừng timer"
assert len(captured_images) == 1, f"phải chụp đúng 1 ảnh, got {len(captured_images)}"
img = captured_images[0]
assert isinstance(img, QImage) and not img.isNull(), "ảnh chụp phải hợp lệ"
assert img.width() > 0 and img.height() > 0
print(f"OK: đếm ngược -> chụp ra QImage {img.width()}x{img.height()}")

# Window capture đi qua đúng luồng _on_region_selected (dùng chung với region).
# Mô phỏng chọn 1 cửa sổ -> phải sinh thêm 1 ảnh.
captured_images.clear()
ctrl._on_region_selected(QRect(0, 0, 50, 40))
assert len(captured_images) == 1, "window_selected nối vào _on_region_selected phải chụp"
print("OK: window_selected dùng chung luồng chụp region")

print("=== WINDOW + DELAYED CAPTURE OK ===")
