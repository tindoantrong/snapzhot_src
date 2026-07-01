"""Bộ icon line-art đơn sắc cho Editor, vẽ runtime bằng QPainter.

Icon được vẽ trực tiếp lên QPixmap nền trong suốt thay vì load file PNG/SVG.
Lý do: nét có thể scale theo `size` (sắc nét ở mọi DPI) và màu đồng bộ với
theme (truyền `color` của theme vào). Kết quả được cache theo (name, color, size)
để không phải vẽ lại mỗi lần dựng action.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# Cache: khoá (name, color, size) -> QIcon đã vẽ.
_CACHE: dict[tuple[str, str, int], QIcon] = {}


def tool_icon(name: str, color: str = "#E8E8E8", size: int = 26) -> QIcon:
    """Trả về QIcon line-art cho `name`, vẽ runtime và cache lại.

    name: tên icon (xem _DRAWERS). color: màu nét (hex). size: cạnh pixmap (px).
    """
    key = (name, color, size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)

    qcolor = QColor(color)
    # Nét rộng ~2.2px, đầu/khớp bo tròn cho cảm giác mềm, hiện đại.
    pen = QPen(qcolor, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)

    # Vùng vẽ có lề ~20% mỗi cạnh.
    m = size * 0.20
    rect = QRectF(m, m, size - 2 * m, size - 2 * m)

    drawer = _DRAWERS.get(name)
    if drawer is not None:
        drawer(painter, rect, qcolor)
    painter.end()

    icon = QIcon(pm)
    _CACHE[key] = icon
    return icon


# ---------- các hàm vẽ từng icon ----------
# Mỗi hàm nhận (painter, rect, color); painter đã set pen/antialiasing.

def _p(rect: QRectF, fx: float, fy: float) -> QPointF:
    """Điểm theo tỉ lệ (0..1) trong rect."""
    return QPointF(rect.left() + fx * rect.width(), rect.top() + fy * rect.height())


def _draw_select(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Con trỏ mũi tên: thân tô đặc cho dễ nhận.
    path = QPainterPath()
    path.moveTo(_p(rect, 0.05, 0.0))
    path.lineTo(_p(rect, 0.05, 0.95))
    path.lineTo(_p(rect, 0.30, 0.70))
    path.lineTo(_p(rect, 0.48, 1.05))
    path.lineTo(_p(rect, 0.62, 0.98))
    path.lineTo(_p(rect, 0.45, 0.63))
    path.lineTo(_p(rect, 0.80, 0.58))
    path.closeSubpath()
    painter.save()
    painter.setBrush(QBrush(color))
    painter.drawPath(path)
    painter.restore()


def _draw_arrow(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Mũi tên chéo từ dưới-trái lên trên-phải.
    start = _p(rect, 0.05, 0.95)
    end = _p(rect, 0.95, 0.05)
    painter.drawLine(start, end)
    # Hai cạnh đầu mũi.
    painter.drawLine(end, _p(rect, 0.55, 0.10))
    painter.drawLine(end, _p(rect, 0.90, 0.50))


def _draw_rect(painter: QPainter, rect: QRectF, color: QColor) -> None:
    painter.drawRoundedRect(rect, rect.width() * 0.12, rect.height() * 0.12)


def _draw_ellipse(painter: QPainter, rect: QRectF, color: QColor) -> None:
    painter.drawEllipse(rect)


def _draw_pen(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Bút: thân chéo + đầu ngòi tam giác.
    tip = _p(rect, 0.08, 0.95)
    body_top = _p(rect, 0.88, 0.12)
    # Hai cạnh thân bút.
    a = _p(rect, 0.20, 0.78)
    b = _p(rect, 0.95, 0.30)
    painter.drawLine(a, b)
    # Ngòi: tam giác nhỏ ở đầu.
    painter.drawLine(a, tip)
    painter.drawLine(_p(rect, 0.32, 0.90), tip)
    # Vạch cắt thân bút (đường nối hai cạnh).
    painter.drawLine(_p(rect, 0.72, 0.16), _p(rect, 0.84, 0.30))
    # phần body_top: nắp bút phía trên
    painter.drawLine(body_top, _p(rect, 0.72, 0.16))
    painter.drawLine(body_top, _p(rect, 0.84, 0.30))


def _draw_text(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Chữ "A" vẽ bằng đường nét (không dùng font).
    apex = _p(rect, 0.5, 0.05)
    left = _p(rect, 0.12, 0.98)
    right = _p(rect, 0.88, 0.98)
    painter.drawLine(apex, left)
    painter.drawLine(apex, right)
    # Thanh ngang giữa.
    painter.drawLine(_p(rect, 0.28, 0.62), _p(rect, 0.72, 0.62))


def _draw_highlight(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Bút dạ: đầu nghiêng + thân, có vạch mực tô đặc ở ngòi.
    # Thân bút (chữ nhật nghiêng).
    body = QPainterPath()
    body.moveTo(_p(rect, 0.30, 0.05))
    body.lineTo(_p(rect, 0.95, 0.05))
    body.lineTo(_p(rect, 0.55, 0.55))
    body.lineTo(_p(rect, 0.10, 0.55))
    body.closeSubpath()
    painter.drawPath(body)
    # Ngòi tô đặc.
    nib = QPainterPath()
    nib.moveTo(_p(rect, 0.10, 0.55))
    nib.lineTo(_p(rect, 0.55, 0.55))
    nib.lineTo(_p(rect, 0.40, 0.80))
    nib.lineTo(_p(rect, 0.18, 0.80))
    nib.closeSubpath()
    painter.save()
    painter.setBrush(QBrush(color))
    painter.drawPath(nib)
    painter.restore()
    # Vệt tô dưới ngòi.
    painter.drawLine(_p(rect, 0.10, 0.95), _p(rect, 0.45, 0.95))


def _draw_blur(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Ô vuông chứa lưới chấm (gợi ý pixel hoá/làm mờ).
    painter.drawRoundedRect(rect, rect.width() * 0.12, rect.height() * 0.12)
    painter.save()
    painter.setBrush(QBrush(color))
    r = rect.width() * 0.05
    for fx in (0.30, 0.50, 0.70):
        for fy in (0.30, 0.50, 0.70):
            c = _p(rect, fx, fy)
            painter.drawEllipse(c, r, r)
    painter.restore()


def _draw_step(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Vòng tròn có chấm tâm (badge số bước).
    painter.drawEllipse(rect)
    painter.save()
    painter.setBrush(QBrush(color))
    c = rect.center()
    r = rect.width() * 0.10
    painter.drawEllipse(c, r, r)
    painter.restore()


def _draw_crop(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Hai góc chữ L lồng nhau (biểu tượng crop).
    # Góc trên-trái: chữ L hướng xuống/phải.
    painter.drawLine(_p(rect, 0.05, 0.25), _p(rect, 0.05, 0.95))
    painter.drawLine(_p(rect, 0.05, 0.95), _p(rect, 0.75, 0.95))
    # Góc dưới-phải: chữ L hướng lên/trái.
    painter.drawLine(_p(rect, 0.95, 0.75), _p(rect, 0.95, 0.05))
    painter.drawLine(_p(rect, 0.95, 0.05), _p(rect, 0.25, 0.05))


def _draw_undo(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Cung tròn ngược chiều kim đồng hồ + mũi tên bên trái.
    span = QRectF(rect.left(), rect.top() + rect.height() * 0.10,
                  rect.width(), rect.height() * 0.90)
    # Cung từ ~150° quét -200° (mở về bên trái).
    painter.drawArc(span, 150 * 16, -210 * 16)
    # Đầu mũi tên ở điểm bắt đầu cung (phía trên-trái).
    tip = _p(rect, 0.16, 0.18)
    painter.drawLine(tip, _p(rect, 0.06, 0.42))
    painter.drawLine(tip, _p(rect, 0.40, 0.30))


def _draw_redo(painter: QPainter, rect: QRectF, color: QColor) -> None:
    span = QRectF(rect.left(), rect.top() + rect.height() * 0.10,
                  rect.width(), rect.height() * 0.90)
    painter.drawArc(span, 30 * 16, 210 * 16)
    tip = _p(rect, 0.84, 0.18)
    painter.drawLine(tip, _p(rect, 0.94, 0.42))
    painter.drawLine(tip, _p(rect, 0.60, 0.30))


def _draw_magnifier(painter: QPainter, rect: QRectF, color: QColor,
                    sign: str | None) -> None:
    # Kính lúp: vòng tròn + cán; sign = '+', '-', hoặc None.
    glass = QRectF(rect.left(), rect.top(),
                   rect.width() * 0.70, rect.height() * 0.70)
    painter.drawEllipse(glass)
    # Cán nối từ mép dưới-phải kính ra góc.
    c = glass.center()
    rad = glass.width() / 2
    edge = QPointF(c.x() + rad * math.cos(math.radians(45)),
                   c.y() + rad * math.sin(math.radians(45)))
    painter.drawLine(edge, _p(rect, 1.0, 1.0))
    gc = glass.center()
    s = glass.width() * 0.22
    if sign in ("+", "-"):
        painter.drawLine(QPointF(gc.x() - s, gc.y()), QPointF(gc.x() + s, gc.y()))
    if sign == "+":
        painter.drawLine(QPointF(gc.x(), gc.y() - s), QPointF(gc.x(), gc.y() + s))


def _draw_zoom_in(painter: QPainter, rect: QRectF, color: QColor) -> None:
    _draw_magnifier(painter, rect, color, "+")


def _draw_zoom_out(painter: QPainter, rect: QRectF, color: QColor) -> None:
    _draw_magnifier(painter, rect, color, "-")


def _draw_zoom_fit(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Khung với 4 mũi tên hướng ra góc (fit to frame).
    painter.drawRoundedRect(rect, rect.width() * 0.10, rect.height() * 0.10)
    cx, cy = rect.center().x(), rect.center().y()
    d = rect.width() * 0.16
    # 4 đường chéo ngắn từ tâm ra các góc.
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        a = QPointF(cx + sx * d * 0.4, cy + sy * d * 0.4)
        b = QPointF(cx + sx * d * 1.6, cy + sy * d * 1.6)
        painter.drawLine(a, b)
        # đầu mũi tên
        painter.drawLine(b, QPointF(b.x() - sx * d * 0.7, b.y()))
        painter.drawLine(b, QPointF(b.x(), b.y() - sy * d * 0.7))


def _draw_zoom_actual(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Khung với chấm tâm (kích thước thật 1:1).
    painter.drawRoundedRect(rect, rect.width() * 0.10, rect.height() * 0.10)
    painter.save()
    painter.setBrush(QBrush(color))
    r = rect.width() * 0.07
    painter.drawEllipse(rect.center(), r, r)
    painter.restore()


def _draw_capture_region(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Khung nét đứt 4 góc (chọn vùng).
    painter.save()
    pen = QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    L = rect.width() * 0.28
    corners = (
        (rect.topLeft(), 1, 1),
        (rect.topRight(), -1, 1),
        (rect.bottomLeft(), 1, -1),
        (rect.bottomRight(), -1, -1),
    )
    for pt, sx, sy in corners:
        painter.drawLine(pt, QPointF(pt.x() + sx * L, pt.y()))
        painter.drawLine(pt, QPointF(pt.x(), pt.y() + sy * L))
    painter.restore()


def _draw_capture_full(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Màn hình: khung + chân đế.
    screen = QRectF(rect.left(), rect.top(),
                    rect.width(), rect.height() * 0.72)
    painter.drawRoundedRect(screen, rect.width() * 0.08, rect.width() * 0.08)
    # Chân đế.
    painter.drawLine(_p(rect, 0.5, 0.72), _p(rect, 0.5, 0.90))
    painter.drawLine(_p(rect, 0.30, 0.98), _p(rect, 0.70, 0.98))


def _draw_video(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Thân camera + ống kính tam giác bên phải.
    body = QRectF(rect.left(), rect.top() + rect.height() * 0.22,
                  rect.width() * 0.62, rect.height() * 0.56)
    painter.drawRoundedRect(body, rect.width() * 0.08, rect.width() * 0.08)
    # Ống kính: tam giác.
    lens = QPainterPath()
    lens.moveTo(QPointF(body.right(), rect.center().y() - rect.height() * 0.12))
    lens.lineTo(_p(rect, 1.0, 0.28))
    lens.lineTo(_p(rect, 1.0, 0.72))
    lens.lineTo(QPointF(body.right(), rect.center().y() + rect.height() * 0.12))
    lens.closeSubpath()
    painter.drawPath(lens)


def _draw_save(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Đĩa mềm (floppy): khung bo góc + khe trượt trên + ô nhãn dưới.
    painter.drawRoundedRect(rect, rect.width() * 0.10, rect.height() * 0.10)
    # Khe trượt phía trên (chữ nhật nhỏ).
    shutter = QRectF(_p(rect, 0.32, 0.05), _p(rect, 0.78, 0.32))
    painter.drawRect(shutter)
    # Ô nhãn phía dưới.
    label = QRectF(_p(rect, 0.22, 0.52), _p(rect, 0.78, 0.95))
    painter.drawRect(label)


def _draw_export(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Khay mở + mũi tên hướng lên (xuất ra ngoài).
    # Khay: đáy hình chữ U.
    painter.drawLine(_p(rect, 0.10, 0.55), _p(rect, 0.10, 0.95))
    painter.drawLine(_p(rect, 0.10, 0.95), _p(rect, 0.90, 0.95))
    painter.drawLine(_p(rect, 0.90, 0.95), _p(rect, 0.90, 0.55))
    # Mũi tên đi lên.
    painter.drawLine(_p(rect, 0.5, 0.70), _p(rect, 0.5, 0.05))
    painter.drawLine(_p(rect, 0.5, 0.05), _p(rect, 0.28, 0.28))
    painter.drawLine(_p(rect, 0.5, 0.05), _p(rect, 0.72, 0.28))


def _draw_copy(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Hai khung chữ nhật chồng lệch nhau.
    back = QRectF(_p(rect, 0.05, 0.05), _p(rect, 0.65, 0.65))
    front = QRectF(_p(rect, 0.35, 0.35), _p(rect, 0.95, 0.95))
    painter.drawRoundedRect(back, rect.width() * 0.06, rect.height() * 0.06)
    painter.save()
    # Front phủ lên: tô nền trong suốt để che phần giao của back.
    painter.setBrush(QBrush(Qt.transparent))
    painter.drawRoundedRect(front, rect.width() * 0.06, rect.height() * 0.06)
    painter.restore()


def _draw_open(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Thư mục mở: thân + nắp gập hình thang.
    # Thân folder.
    painter.drawLine(_p(rect, 0.05, 0.30), _p(rect, 0.05, 0.90))
    painter.drawLine(_p(rect, 0.05, 0.30), _p(rect, 0.40, 0.30))
    painter.drawLine(_p(rect, 0.40, 0.30), _p(rect, 0.50, 0.45))
    painter.drawLine(_p(rect, 0.50, 0.45), _p(rect, 0.95, 0.45))
    # Nắp trước (hình thang mở ra phía trước).
    painter.drawLine(_p(rect, 0.05, 0.90), _p(rect, 0.78, 0.90))
    painter.drawLine(_p(rect, 0.78, 0.90), _p(rect, 0.95, 0.45))


def _draw_stamp(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Ngôi sao line-art (gợi con dấu/nhãn biểu tượng).
    cx, cy = rect.center().x(), rect.center().y()
    outer = rect.width() / 2
    inner = outer * 0.42
    path = QPainterPath()
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = outer if i % 2 == 0 else inner
        p = QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang))
        if i == 0:
            path.moveTo(p)
        else:
            path.lineTo(p)
    path.closeSubpath()
    painter.drawPath(path)


def _draw_spotlight(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Bia ngắm/tiêu điểm: vòng tròn + chấm tâm + 4 vạch hướng tâm.
    inner = rect.adjusted(rect.width() * 0.18, rect.height() * 0.18,
                          -rect.width() * 0.18, -rect.height() * 0.18)
    painter.drawEllipse(inner)
    painter.save()
    painter.setBrush(QBrush(color))
    c = rect.center()
    r = rect.width() * 0.06
    painter.drawEllipse(c, r, r)
    painter.restore()
    cx, cy = c.x(), c.y()
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        a = QPointF(cx + dx * rect.width() * 0.32, cy + dy * rect.height() * 0.32)
        b = QPointF(cx + dx * rect.width() * 0.50, cy + dy * rect.height() * 0.50)
        painter.drawLine(a, b)


def _draw_callout(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Bong bóng thoại: rounded rect chiếm ~70% trên + đuôi tam giác trỏ xuống-trái.
    bubble = QRectF(rect.left(), rect.top(),
                    rect.width(), rect.height() * 0.70)
    painter.drawRoundedRect(bubble, rect.width() * 0.16, rect.height() * 0.16)
    # Đuôi: hai cạnh xiên từ cạnh đáy bong bóng xuống một đỉnh nhọn (outline-only).
    base_y = bubble.bottom()
    painter.drawLine(_p(rect, 0.28, 1.0), QPointF(rect.left() + rect.width() * 0.20, base_y))
    painter.drawLine(_p(rect, 0.28, 1.0), QPointF(rect.left() + rect.width() * 0.42, base_y))


def _draw_search(painter: QPainter, rect: QRectF, color: QColor) -> None:
    # Kính lúp: vòng kính lệch trên-trái + tay cầm chéo xuống-phải.
    glass = QRectF(rect.left(), rect.top(),
                   rect.width() * 0.62, rect.height() * 0.62)
    painter.drawEllipse(glass)
    c = glass.center()
    rad = glass.width() / 2
    edge = QPointF(c.x() + rad * math.cos(math.radians(45)),
                   c.y() + rad * math.sin(math.radians(45)))
    painter.drawLine(edge, _p(rect, 1.0, 1.0))


_DRAWERS = {
    "select": _draw_select,
    "arrow": _draw_arrow,
    "rect": _draw_rect,
    "ellipse": _draw_ellipse,
    "pen": _draw_pen,
    "text": _draw_text,
    "highlight": _draw_highlight,
    "blur": _draw_blur,
    "step": _draw_step,
    "crop": _draw_crop,
    "undo": _draw_undo,
    "redo": _draw_redo,
    "zoom_in": _draw_zoom_in,
    "zoom_out": _draw_zoom_out,
    "zoom_fit": _draw_zoom_fit,
    "zoom_actual": _draw_zoom_actual,
    "capture_region": _draw_capture_region,
    "capture_full": _draw_capture_full,
    "video": _draw_video,
    "save": _draw_save,
    "export": _draw_export,
    "copy": _draw_copy,
    "open": _draw_open,
    "stamp": _draw_stamp,
    "spotlight": _draw_spotlight,
    "callout": _draw_callout,
    "search": _draw_search,
}
