"""Test trực quan overlay chọn vùng (CHẠY TRÊN MÀN HÌNH THẬT, không offscreen).

Mục đích: người dùng tự kiểm tra bằng mắt rằng overlay chụp vùng làm tối mờ
desktop nhưng VẪN nhìn rõ các đối tượng phía sau (fix WA_TranslucentBackground).

Cách chạy:  python scripts/test_region_overlay.py
"""
import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from app.capture.region_selector import RegionSelector

app = QApplication([])

selector = RegionSelector()


def _on_selected(rect) -> None:
    print(f"OK: đã chọn vùng (toạ độ màn hình ảo) = "
          f"x={rect.x()} y={rect.y()} w={rect.width()} h={rect.height()}")
    app.quit()


def _on_cancelled() -> None:
    print("Đã huỷ (Esc / chuột phải / hết giờ).")
    app.quit()


selector.region_selected.connect(_on_selected)
selector.cancelled.connect(_on_cancelled)

print("=== TEST OVERLAY CHỌN VÙNG ===")
print("Toàn màn hình bị phủ TỐI MỜ (overlay bắt được chuột); vùng đang kéo")
print("được 'khoét' sáng rõ, có viền GẠCH GẠCH (dashed) xanh + nhãn kích thước.")
print("Kiểm tra: phải KÉO CHỌN ĐƯỢC (không bị click-through).")
print("Nhấn Esc hoặc chuột phải để huỷ. Tự đóng sau 15 giây nếu không thao tác.")

selector.start()

# Tự đóng phòng khi người dùng không thao tác -> tránh treo tiến trình.
QTimer.singleShot(15000, lambda: (print("Hết giờ tự đóng."), selector._finish_cancel()))

app.exec()
