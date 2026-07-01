"""Test REC1: dải 'Ảnh gần đây' (filmstrip) trong EditorWindow.

Kiểm offscreen: set_recent_captures dựng đúng số item; load_image highlight
theo capture_id; click item khác phát open_capture_requested(id); click ảnh đang
mở KHÔNG phát; rỗng → ẩn dock. load_image GIỮ NGUYÊN signature (image, capture_id).
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

app = QApplication([])

from app.editor.editor_window import EditorWindow

img = QImage(120, 80, QImage.Format_RGB32)
img.fill(QColor("#3366cc"))


def fake_items():
    # thumb path không tồn tại → QIcon rỗng (vẫn dựng item hợp lệ)
    return [
        {"id": 1, "thumb": "/no/such/1.png", "label": "anh_1.png"},
        {"id": 2, "thumb": "/no/such/2.png", "label": "anh_2.png"},
        {"id": 3, "thumb": "/no/such/3.png", "label": "anh_3.png"},
    ]


def selected_id(w):
    it = w.recent_strip.currentItem()
    return None if it is None else it.data(Qt.UserRole)


def main() -> int:
    w = EditorWindow()

    # --- 0. khởi tạo: dock ẩn khi chưa có ảnh gần đây ---
    assert not w.recent_dock.isVisible(), "dock phải ẩn lúc khởi tạo"
    assert w.recent_strip.count() == 0

    # --- 1. set_recent_captures(3) → 3 item, dock hiện ---
    w.set_recent_captures(fake_items())
    assert w.recent_strip.count() == 3, w.recent_strip.count()
    # show để isVisible phản ánh setVisible(True) một cách đáng tin
    w.show()
    app.processEvents()
    assert w.recent_dock.isVisible(), "dock phải hiện khi có item"
    ids = [w.recent_strip.item(i).data(Qt.UserRole) for i in range(3)]
    assert ids == [1, 2, 3], ids
    # chưa load ảnh nào → không item nào selected
    assert selected_id(w) is None, selected_id(w)

    # --- 2. load_image(capture_id=2) → item id=2 selected (highlight) ---
    w.load_image(img, capture_id=2)
    assert w.current_capture_id == 2
    assert selected_id(w) == 2, selected_id(w)
    sel = [i for i in range(3) if w.recent_strip.item(i).isSelected()]
    assert sel == [1], sel  # index 1 == id 2

    # --- 3. click item id=3 → emit open_capture_requested(3) ---
    emitted = []
    w.open_capture_requested.connect(lambda cid: emitted.append(cid))
    item3 = w.recent_strip.item(2)
    w._on_recent_item_clicked(item3)
    assert emitted == [3], emitted

    # --- 3b. click ảnh ĐANG mở (id=2) → KHÔNG phát thêm ---
    item2 = w.recent_strip.item(1)
    w._on_recent_item_clicked(item2)
    assert emitted == [3], emitted  # vẫn chỉ có 3
    # highlight giữ ở ảnh đang mở
    assert selected_id(w) == 2, selected_id(w)

    # --- 4. set_recent_captures rebuild giữ highlight theo _current_capture_id ---
    w.set_recent_captures(fake_items())
    assert selected_id(w) == 2, selected_id(w)

    # --- 5. rỗng → ẩn dock ---
    w.set_recent_captures([])
    app.processEvents()
    assert w.recent_strip.count() == 0
    assert not w.recent_dock.isVisible(), "dock phải ẩn khi rỗng"

    # --- 6. load_image vẫn nhận capture_id=None (signature giữ nguyên) ---
    w.load_image(img)
    assert w.current_capture_id is None

    print("=== RECENT STRIP OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
