"""Launcher mở Editor THẬT để eyes-test (QC kiểm bằng mắt).

Khác các script test (headless/offscreen): ở đây dựng QApplication THẬT và
hiện cửa sổ EditorWindow với một ảnh mẫu có sẵn nội dung (gradient + hình + chữ)
để thử move/resize/style trên object có sẵn lẫn vẽ mới.

Chạy:  python scripts/launch_editor_demo.py
Tự kiểm dựng-không-lỗi:  QT_QPA_PLATFORM=offscreen python scripts/launch_editor_demo.py
(khi offscreen sẽ tự thoát ngay sau khi dựng xong, không treo cửa sổ).
"""
import os
import sys

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
)

from app.editor.editor_window import EditorWindow


def make_sample_image(w: int = 1280, h: int = 800) -> QImage:
    """Ảnh mẫu: nền gradient + vài hình/chữ sẵn để có nội dung thao tác."""
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#ffffff"))

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    # Nền gradient chéo.
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0.0, QColor("#e3f2fd"))
    grad.setColorAt(0.5, QColor("#bbdefb"))
    grad.setColorAt(1.0, QColor("#90caf9"))
    p.fillRect(0, 0, w, h, QBrush(grad))

    # Hình chữ nhật bo góc.
    p.setPen(QPen(QColor("#1565c0"), 4))
    p.setBrush(QBrush(QColor("#ffffff")))
    p.drawRoundedRect(QRectF(120, 140, 360, 220), 18, 18)

    # Hình elip.
    p.setPen(QPen(QColor("#c62828"), 4))
    p.setBrush(QBrush(QColor("#ffcdd2")))
    p.drawEllipse(QRectF(640, 180, 300, 200))

    # Tam giác (polyline khép kín).
    p.setPen(QPen(QColor("#2e7d32"), 4))
    p.setBrush(QBrush(QColor("#c8e6c9")))
    from PySide6.QtGui import QPolygonF
    tri = QPolygonF([QPointF(300, 560), QPointF(180, 740), QPointF(420, 740)])
    p.drawPolygon(tri)

    # Đường thẳng / mũi tên minh hoạ.
    p.setPen(QPen(QColor("#6a1b9a"), 5))
    p.drawLine(700, 560, 1040, 700)

    # Chữ tiêu đề.
    p.setPen(QColor("#0d47a1"))
    p.setFont(QFont("Arial", 40, QFont.Bold))
    p.drawText(QRectF(120, 40, w - 240, 70), Qt.AlignCenter,
               "Editor Demo — Eyes Test")

    # Chữ mô tả nhỏ.
    p.setPen(QColor("#37474f"))
    p.setFont(QFont("Arial", 18))
    p.drawText(QRectF(640, 600, 560, 120),
               Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
               "Thử: chọn công cụ, vẽ hình/mũi tên/callout, "
               "direct-select để move/resize, đổi style ở panel phải, "
               "zoom, undo/redo, gõ text.")

    p.end()
    return img


def make_recent_thumbs() -> list[dict]:
    """Tạo vài thumbnail mẫu (lưu temp) để eyes-test dải 'Ảnh gần đây'."""
    import tempfile

    palette = [
        ("#FF6B6B", "anh_do.png"),
        ("#4DABF7", "anh_xanh.png"),
        ("#51CF66", "anh_la.png"),
        ("#FFD43B", "anh_vang.png"),
        ("#CC5DE8", "anh_tim.png"),
        ("#FF922B", "anh_cam.png"),
    ]
    tmp = tempfile.gettempdir()
    items: list[dict] = []
    for i, (hexc, name) in enumerate(palette, start=1):
        thumb = QImage(120, 80, QImage.Format_RGB32)
        thumb.fill(QColor(hexc))
        pp = QPainter(thumb)
        pp.setPen(QColor("#ffffff"))
        pp.setFont(QFont("Arial", 22, QFont.Bold))
        pp.drawText(thumb.rect(), Qt.AlignCenter, str(i))
        pp.end()
        path = os.path.join(tmp, f"recent_demo_{i}.png")
        thumb.save(path, "PNG")
        items.append({"id": i, "thumb": path, "label": name})
    return items


def main() -> int:
    app = QApplication(sys.argv)

    img = make_sample_image(1280, 800)

    w = EditorWindow()
    # capture_id=2 để filmstrip highlight đúng ảnh số 2 (viền xanh).
    w.load_image(img, capture_id=2)
    recents = make_recent_thumbs()
    w.set_recent_captures(recents)

    # Giả lập controller cho eyes-test xoá (REC2): right-click/Delete → confirm →
    # bỏ ảnh khỏi danh sách + nếu xoá ảnh đang mở thì nhảy sang ảnh còn lại.
    def on_delete(cid: int) -> None:
        nonlocal recents
        recents = [it for it in recents if it["id"] != cid]
        if cid == w.current_capture_id and recents:
            w.load_image(img, capture_id=recents[0]["id"])
        w.set_recent_captures(recents)

    w.delete_capture_requested.connect(on_delete)

    # Cửa sổ thường (windowed, resize được) — KHÔNG maximize/fullscreen.
    # Nhỏ hơn ảnh mẫu để thấy rõ là windowed, kéo resize được, và thử được
    # ca thu nhỏ cửa sổ → menu ">>".
    w.resize(1100, 720)
    screen = app.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        fg = w.frameGeometry()
        fg.moveCenter(geo.center())
        w.move(fg.topLeft())

    w.show()

    # Khi chạy headless (offscreen) chỉ để kiểm dựng-không-lỗi → thoát ngay,
    # tránh treo vô hạn trong CI/tự kiểm.
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        QTimer.singleShot(0, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
