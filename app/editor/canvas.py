"""Canvas vẽ chú thích dựa trên QGraphicsView/QGraphicsScene.

- Ảnh nền là một QGraphicsPixmapItem ở dưới cùng.
- Các chú thích là QGraphicsItem vector vẽ chồng lên (mũi tên, chữ nhật, ellipse,
  text, nét tự do, badge số bước). Riêng "blur" được nướng vào ảnh nền.
- Công cụ "select" cho phép chọn/di chuyển/xoá item đã vẽ.
- Mọi thao tác đi qua QUndoStack để hoàn tác/làm lại nhiều bước.

ToolState giữ thuộc tính hiện hành (màu, độ dày) do panel Tool Properties điều khiển.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QTextCursor,
    QTransform,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QStyle,
    QStyleOptionGraphicsItem,
)

from .commands import (
    AddItemCommand,
    BlurCommand,
    CropCommand,
    DeleteItemsCommand,
    MoveItemCommand,
    ResizeItemCommand,
    StyleCommand,
    _make_shadow_effect,
)


class Tool(Enum):
    SELECT = auto()
    ARROW = auto()
    RECT = auto()
    ELLIPSE = auto()
    PEN = auto()
    TEXT = auto()
    BLUR = auto()
    HIGHLIGHT = auto()
    STEP = auto()
    CROP = auto()
    STAMP = auto()
    SPOTLIGHT = auto()
    CALLOUT = auto()


@dataclass
class ToolState:
    tool: Tool = Tool.ARROW
    color: QColor = field(default_factory=lambda: QColor("#FF3B30"))
    width: int = 6
    font_size: int = 24
    step_number: int = 1   # số bước kế tiếp cho công cụ STEP
    stamp_name: str = "star"   # biểu tượng kế tiếp cho công cụ STAMP


class StepItem(QGraphicsItem):
    """Badge số bước: vòng tròn tô màu, viền trắng, số ở giữa."""

    def __init__(self, number: int, color: QColor, diameter: float) -> None:
        super().__init__()
        self._number = number
        self._color = QColor(color)
        self._d = diameter
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def set_color(self, color: QColor) -> None:
        """Đổi màu badge (dùng cho sửa style item đã chọn)."""
        self._color = QColor(color)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._d, self._d)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        border = max(1.0, self._d * 0.07)
        painter.setBrush(QBrush(self._color))
        painter.setPen(QPen(Qt.white, border))
        inner = self.boundingRect().adjusted(border, border, -border, -border)
        painter.drawEllipse(inner)
        painter.setPen(QPen(Qt.white))
        font = QFont()
        font.setBold(True)
        font.setPointSizeF(self._d * 0.45)
        painter.setFont(font)
        painter.drawText(self.boundingRect(), Qt.AlignCenter, str(self._number))


# Tên các biểu tượng Stamp hỗ trợ (vẽ vector trong StampItem.paint).
STAMP_NAMES = ["check", "cross", "star", "heart", "exclaim", "pin"]


class StampItem(QGraphicsItem):
    """Biểu tượng vector (check/cross/star/heart/exclaim/pin) tô đặc theo màu.

    Mirror StepItem: chọn/di chuyển/resize (transform) như mọi annotation,
    đổi màu qua set_color. Glyph vẽ runtime nên scale theo size + đồng bộ màu.
    """

    def __init__(self, name: str, color: QColor, size: float) -> None:
        super().__init__()
        self._name = name
        self._color = QColor(color)
        self._size = size
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def set_color(self, color: QColor) -> None:
        """Đổi màu biểu tượng (dùng cho sửa style item đã chọn)."""
        self._color = QColor(color)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._size, self._size)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        m = self._size * 0.12
        r = self.boundingRect().adjusted(m, m, -m, -m)
        painter.setBrush(QBrush(self._color))
        # Viền trắng mảnh giúp biểu tượng tách nền.
        painter.setPen(QPen(Qt.white, max(1.0, self._size * 0.04)))
        _paint_stamp_glyph(painter, self._name, r)


def _stamp_pt(r: QRectF, fx: float, fy: float) -> QPointF:
    """Điểm theo tỉ lệ (0..1) trong rect r."""
    return QPointF(r.left() + fx * r.width(), r.top() + fy * r.height())


def _paint_stamp_glyph(painter: QPainter, name: str, r: QRectF) -> None:
    """Vẽ glyph tô đặc theo `name` trong rect r (painter đã set pen/brush)."""
    if name == "check":
        path = QPainterPath()
        path.moveTo(_stamp_pt(r, 0.10, 0.55))
        path.lineTo(_stamp_pt(r, 0.22, 0.42))
        path.lineTo(_stamp_pt(r, 0.42, 0.66))
        path.lineTo(_stamp_pt(r, 0.82, 0.18))
        path.lineTo(_stamp_pt(r, 0.94, 0.30))
        path.lineTo(_stamp_pt(r, 0.42, 0.90))
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "cross":
        path = QPainterPath()
        pts = [
            (0.18, 0.06), (0.50, 0.38), (0.82, 0.06), (0.94, 0.18),
            (0.62, 0.50), (0.94, 0.82), (0.82, 0.94), (0.50, 0.62),
            (0.18, 0.94), (0.06, 0.82), (0.38, 0.50), (0.06, 0.18),
        ]
        path.moveTo(_stamp_pt(r, *pts[0]))
        for fx, fy in pts[1:]:
            path.lineTo(_stamp_pt(r, fx, fy))
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "star":
        path = QPainterPath()
        cx, cy = r.center().x(), r.center().y()
        outer = r.width() / 2
        inner = outer * 0.42
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
    elif name == "heart":
        path = QPainterPath()
        path.moveTo(_stamp_pt(r, 0.50, 0.92))
        path.cubicTo(_stamp_pt(r, 0.05, 0.55), _stamp_pt(r, 0.10, 0.10),
                     _stamp_pt(r, 0.50, 0.32))
        path.cubicTo(_stamp_pt(r, 0.90, 0.10), _stamp_pt(r, 0.95, 0.55),
                     _stamp_pt(r, 0.50, 0.92))
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "exclaim":
        # Thân dấu chấm than (hình thang) + chấm tròn dưới.
        body = QPainterPath()
        body.moveTo(_stamp_pt(r, 0.38, 0.06))
        body.lineTo(_stamp_pt(r, 0.62, 0.06))
        body.lineTo(_stamp_pt(r, 0.56, 0.62))
        body.lineTo(_stamp_pt(r, 0.44, 0.62))
        body.closeSubpath()
        painter.drawPath(body)
        dot = QRectF(_stamp_pt(r, 0.40, 0.76), _stamp_pt(r, 0.60, 0.96))
        painter.drawEllipse(dot)
    elif name == "pin":
        # Ghim bản đồ: giọt nước + lỗ tròn ở giữa.
        path = QPainterPath()
        path.moveTo(_stamp_pt(r, 0.50, 0.98))
        path.cubicTo(_stamp_pt(r, 0.05, 0.55), _stamp_pt(r, 0.12, 0.05),
                     _stamp_pt(r, 0.50, 0.05))
        path.cubicTo(_stamp_pt(r, 0.88, 0.05), _stamp_pt(r, 0.95, 0.55),
                     _stamp_pt(r, 0.50, 0.98))
        path.closeSubpath()
        # Lỗ tròn: trừ khỏi giọt nước bằng fillRule.
        hole = QPainterPath()
        hole.addEllipse(_stamp_pt(r, 0.36, 0.20), r.width() * 0.14, r.width() * 0.14)
        painter.drawPath(path.subtracted(hole))
    else:
        # Mặc định: ngôi sao nếu tên lạ → tránh vẽ rỗng.
        painter.drawEllipse(r)


class SpotlightItem(QGraphicsItem):
    """Overlay tiêu điểm: phủ tối toàn ảnh trừ một vùng (hole) giữ sáng.

    zValue=-500 → nằm TRÊN ảnh nền (-1000) nhưng DƯỚI chú thích (0), nên chỉ làm
    tối ảnh, chú thích vẫn rõ. Non-selectable/non-movable: tự vắng mặt khỏi
    selection/style/delete pipeline; undo qua AddItemCommand.
    """

    def __init__(self, scene_rect: QRectF, hole: QRectF, alpha: int = 140) -> None:
        super().__init__()
        self._scene_rect = QRectF(scene_rect)
        self._hole = QRectF(hole)
        self._alpha = alpha
        self.setZValue(-500)
        self.setPos(0, 0)

    def boundingRect(self) -> QRectF:
        return QRectF(self._scene_rect)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRect(self._scene_rect)
        path.addRect(self._hole)
        # OddEvenFill: vùng hole (rect lồng trong) bị trừ → trong suốt, ngoài tối.
        path.setFillRule(Qt.OddEvenFill)
        painter.setPen(QPen(Qt.NoPen))
        painter.fillPath(path, QColor(0, 0, 0, self._alpha))


def _make_arrow(start: QPointF, end: QPointF, color: QColor, width: int) -> QPolygonF:
    """Tạo polygon hình mũi tên từ start đến end."""
    line_len = math.hypot(end.x() - start.x(), end.y() - start.y())
    if line_len < 1:
        return QPolygonF([start, end])
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    head = max(12.0, width * 3.0)          # chiều dài đầu mũi tên
    half = max(5.0, width * 1.6)           # nửa bề rộng thân
    bx = end.x() - head * math.cos(angle)
    by = end.y() - head * math.sin(angle)
    nx, ny = -math.sin(angle), math.cos(angle)  # vector pháp tuyến
    pts = [
        QPointF(start.x() + nx * half * 0.4, start.y() + ny * half * 0.4),
        QPointF(bx + nx * half * 0.4, by + ny * half * 0.4),
        QPointF(bx + nx * head * 0.5, by + ny * head * 0.5),
        QPointF(end.x(), end.y()),
        QPointF(bx - nx * head * 0.5, by - ny * head * 0.5),
        QPointF(bx - nx * half * 0.4, by - ny * half * 0.4),
        QPointF(start.x() - nx * half * 0.4, start.y() - ny * half * 0.4),
    ]
    return QPolygonF(pts)


class ArrowItem(QGraphicsPolygonItem):
    """Mũi tên tô đặc, LƯU 2 đầu mút (local) + độ dày để dựng lại khi đổi nét.

    Hình mũi tên được "nướng" theo độ dày lúc vẽ, nên muốn đổi độ dày phải dựng
    lại polygon từ start/end. Lưu sẵn các tham số gốc để mutate_item_style và
    StyleCommand đổi màu/độ dày mà vẫn hoàn tác được.
    """

    def __init__(self, start: QPointF, end: QPointF,
                 color: QColor, width: int) -> None:
        super().__init__()
        self._start = QPointF(start)
        self._end = QPointF(end)
        self._width = int(width)
        self._color = QColor(color)
        self._rebuild()

    def _rebuild(self) -> None:
        self.setPolygon(_make_arrow(self._start, self._end, self._color, self._width))
        self.setPen(QPen(self._color, 1))
        self.setBrush(QBrush(self._color))

    def set_style(self, color: QColor | None = None,
                  width: int | None = None) -> None:
        """Đổi màu và/hoặc độ dày tại chỗ (dựng lại hình theo độ dày mới)."""
        if color is not None:
            self._color = QColor(color)
        if width is not None:
            self._width = int(width)
        self._rebuild()

    def set_points(self, start: QPointF, end: QPointF) -> None:
        """Đặt lại 2 đầu mút và dựng lại hình (dùng cho preview lúc kéo)."""
        self._start = QPointF(start)
        self._end = QPointF(end)
        self._rebuild()


class CalloutItem(QGraphicsTextItem):
    """Callout / speech bubble: chữ trong bong bóng bo góc + đuôi nhọn trỏ xuống.

    Subclass QGraphicsTextItem để tái dùng nguyên pipeline soạn-thảo-text (con trỏ,
    chọn vùng, gõ tiếng Việt…). paint() tự vẽ bong bóng + đuôi DƯỚI chữ, rồi gọi
    super().paint() để vẽ chữ lên trên. boundingRect mở rộng cạnh dưới để chứa đuôi.
    """

    _TAIL_H = 18.0   # chiều cao phần đuôi nằm dưới khung chữ

    def __init__(self, text: str, fill: QColor, border: QColor,
                 width: int, font_size: int) -> None:
        super().__init__(text)
        self._fill = QColor(fill)
        self._border = QColor(border)
        self._width = int(width)
        self.document().setDocumentMargin(10)   # padding chữ thụt vào trong bong bóng
        font = QFont()
        font.setPointSize(int(font_size))
        self.setFont(font)
        self.setDefaultTextColor(self._border)  # chữ cùng màu viền

    def set_fill(self, color: QColor) -> None:
        """Đổi màu nền bong bóng (dùng cho mutate style)."""
        self._fill = QColor(color)
        self.update()

    def set_border(self, color: QColor, width: int | None = None) -> None:
        """Đổi màu viền (+ độ dày nếu truyền) của bong bóng."""
        self._border = QColor(color)
        if width is not None:
            self.prepareGeometryChange()   # boundingRect đổi theo _width
            self._width = int(width)
        self.update()

    def enter_edit(self) -> None:
        """Vào chế độ soạn chữ: bật text-control, lấy focus, chọn hết để gõ đè."""
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus()
        cursor = self.textCursor()
        cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)

    def focusOutEvent(self, event) -> None:
        """Rời focus → thoát soạn chữ, trở thành object thường (chọn/move/resize)."""
        super().focusOutEvent(event)
        if self.textInteractionFlags() != Qt.NoTextInteraction:
            self.setTextInteractionFlags(Qt.NoTextInteraction)
            # Bỏ vùng chọn con trỏ text để không vẽ highlight khi đã thoát soạn.
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
            self.update()

    def keyPressEvent(self, event) -> None:
        """Escape khi đang soạn → thoát soạn (kích hoạt focusOut)."""
        if (event.key() == Qt.Key_Escape
                and self.textInteractionFlags() != Qt.NoTextInteraction):
            self.clearFocus()
            event.accept()
            return
        super().keyPressEvent(event)

    def boundingRect(self) -> QRectF:
        # Nới đủ phủ phần đuôi + nửa bề rộng pen viền (tránh nét tràn ngoài lề
        # không bị xoá khi di chuyển → để lại vệt sọc). +1px chống làm tròn AA.
        m = self._width / 2.0 + 1.0
        return super().boundingRect().adjusted(-m, -m, m, self._TAIL_H + m)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        bubble = super().boundingRect()
        # Gộp bong bóng + đuôi thành MỘT path liền mạch (viền không bị line cắt ngang miệng).
        path = QPainterPath()
        path.addRoundedRect(bubble, 10, 10)
        base_y = bubble.bottom()
        x0 = bubble.left() + bubble.width() * 0.22
        tail = QPainterPath()
        tail.moveTo(x0, base_y)
        tail.lineTo(x0 + 22.0, base_y)
        tail.lineTo(x0 + 4.0, base_y + self._TAIL_H)
        tail.closeSubpath()
        path = path.united(tail)
        pen = QPen(self._border, self._width)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        painter.setBrush(QBrush(self._fill))
        painter.setPen(pen)
        painter.drawPath(path)
        # Vẽ chữ lên trên, BỎ khung selection mặc định của QGraphicsTextItem.
        opt = QStyleOptionGraphicsItem(option)
        opt.state &= ~QStyle.State_Selected
        super().paint(painter, opt, widget)


def capture_item_style(item: QGraphicsItem) -> dict:
    """Chụp style hiện tại của item thành snapshot (chỉ khoá có ý nghĩa).

    Snapshot này dùng cho StyleCommand: undo/redo chỉ cần áp lại đúng snapshot.
    """
    snap: dict = {}
    # Opacity/shadow là universal — chụp trước mọi nhánh early-return.
    snap["opacity"] = item.opacity()
    snap["shadow"] = item.graphicsEffect() is not None
    if isinstance(item, CalloutItem):
        snap["callout_fill"] = QColor(item._fill)
        snap["callout_border"] = QColor(item._border)
        snap["callout_width"] = item._width
        snap["font"] = QFont(item.font())
        snap["text_color"] = QColor(item.defaultTextColor())
        return snap
    if isinstance(item, QGraphicsTextItem):
        snap["text_color"] = QColor(item.defaultTextColor())
        snap["font"] = QFont(item.font())
        return snap
    if isinstance(item, StepItem):
        snap["step_color"] = QColor(item._color)
        return snap
    if isinstance(item, StampItem):
        snap["stamp_color"] = QColor(item._color)
        return snap
    if isinstance(item, ArrowItem):
        # Polygon mã hoá độ dày; lưu kèm width để khôi phục đúng base cho lần sau.
        snap["arrow_polygon"] = QPolygonF(item.polygon())
        snap["arrow_width"] = item._width
        snap["pen"] = QPen(item.pen())
        snap["brush"] = QBrush(item.brush())
        return snap
    if hasattr(item, "pen"):
        snap["pen"] = QPen(item.pen())
    if hasattr(item, "brush"):
        snap["brush"] = QBrush(item.brush())
    return snap


def mutate_item_style(item: QGraphicsItem, color: QColor | None = None,
                      width: int | None = None,
                      font_size: int | None = None,
                      opacity: float | None = None,
                      shadow: bool | None = None,
                      fill: QColor | None = None,
                      fill_enabled: bool | None = None) -> None:
    """Áp màu/độ dày/cỡ chữ/độ trong suốt/đổ bóng lên item tại chỗ.

    - Opacity/shadow là universal (mọi loại item) → áp trước các nhánh isinstance.
    - Text: đổi màu chữ + cỡ chữ (pointSize); bỏ qua width (không có nét viền).
    - StepItem: chỉ đổi màu badge.
    - ArrowItem (mũi tên): đổi màu VÀ độ dày — dựng lại hình từ 2 đầu mút đã lưu.
    - Polygon tô đặc khác (nếu có): chỉ đổi màu pen/brush.
    - Còn lại (rect/ellipse/line/path): đổi màu + độ dày của pen (nếu có nét);
      nếu có vùng tô (highlight) thì đổi màu tô nhưng GIỮ NGUYÊN alpha.
    """
    # Universal: áp cho mọi item bất kể loại.
    if opacity is not None:
        item.setOpacity(opacity)
    if shadow is not None:
        item.setGraphicsEffect(_make_shadow_effect() if shadow else None)
    if isinstance(item, CalloutItem):
        # color → viền + chữ; width → độ dày viền; font_size → cỡ chữ;
        # fill/fill_enabled → màu nền bong bóng.
        if color is not None:
            item.set_border(QColor(color), item._width)
            item.setDefaultTextColor(QColor(color))
        if width is not None:
            item.set_border(item._border, int(width))
        if font_size is not None:
            f = item.font()
            f.setPointSize(int(font_size))
            item.setFont(f)
        if fill is not None:
            item.set_fill(QColor(fill))
        elif fill_enabled is True:
            item.set_fill(QColor(item._fill))
        elif fill_enabled is False:
            item.set_fill(QColor(Qt.transparent))
        return
    if isinstance(item, QGraphicsTextItem):
        if color is not None:
            item.setDefaultTextColor(QColor(color))
        if font_size is not None:
            f = item.font()
            f.setPointSize(int(font_size))
            item.setFont(f)
        return
    if isinstance(item, StepItem):
        if color is not None:
            item.set_color(QColor(color))
        return
    if isinstance(item, StampItem):
        if color is not None:
            item.set_color(QColor(color))
        return
    if isinstance(item, ArrowItem):
        # Mũi tên: đổi cả màu lẫn độ dày bằng cách dựng lại hình từ 2 đầu mút.
        item.set_style(color=color, width=width)
        return
    if isinstance(item, QGraphicsPolygonItem):
        if color is not None:
            pen = item.pen()
            pen.setColor(QColor(color))
            item.setPen(pen)
            brush = item.brush()
            if brush.style() != Qt.NoBrush:
                brush.setColor(QColor(color))
                item.setBrush(brush)
        return
    # rect / ellipse / line / path
    if hasattr(item, "pen"):
        pen = item.pen()
        if pen.style() != Qt.NoPen:
            if color is not None:
                pen.setColor(QColor(color))
            if width is not None:
                pen.setWidth(int(width))
            item.setPen(pen)
    # `color` chỉ recolor brush khi item KHÔNG có viền (ca highlight: NoPen + brush).
    # Shape có viền dùng `color` cho viền; nền điều khiển riêng qua fill/fill_enabled.
    if (hasattr(item, "brush") and color is not None
            and item.pen().style() == Qt.NoPen):
        brush = item.brush()
        if brush.style() != Qt.NoBrush:
            c = QColor(color)
            c.setAlpha(brush.color().alpha())  # giữ độ trong suốt của highlight
            brush.setColor(c)
            item.setBrush(brush)
    # Fill: chỉ cho rect/ellipse CÓ viền (loại trừ highlight NoPen, line, path).
    if (isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
            and item.pen().style() != Qt.NoPen):
        if fill_enabled is False:
            item.setBrush(QBrush(Qt.NoBrush))
        elif fill_enabled is True or fill is not None:
            base = QColor(fill) if fill is not None else (
                item.brush().color() if item.brush().style() != Qt.NoBrush
                else QColor(item.pen().color()))
            item.setBrush(QBrush(base))


def item_style_props(item: QGraphicsItem) -> dict:
    """Mô tả nhóm thuộc tính panel nên hiện + giá trị hiện tại cho item đã chọn.

    Trả dict: ``groups`` (list khoá panel: "color"/"width"/"font") và
    ``color``/``width``/``font_size`` (giá trị hiện tại hoặc None). Phản chiếu
    đúng những thuộc tính mà mutate_item_style có thể đổi cho từng loại item, để
    panel (Slice 2) hiện đúng nhóm và đồng bộ giá trị.
    """
    # Opacity/shadow áp cho mọi item → luôn ở cuối list groups + kèm giá trị.
    extra = ["opacity", "shadow"]
    op = item.opacity()
    sh = item.graphicsEffect() is not None
    if isinstance(item, CalloutItem):
        return {"groups": ["color", "width", "fill", "font"] + extra,
                "color": QColor(item._border),
                "width": item._width,
                "font_size": item.font().pointSize(),
                "opacity": op, "shadow": sh,
                "fill_enabled": True, "fill_color": QColor(item._fill)}
    if isinstance(item, QGraphicsTextItem):
        return {"groups": ["color", "font"] + extra,
                "color": QColor(item.defaultTextColor()),
                "width": None,
                "font_size": item.font().pointSize(),
                "opacity": op, "shadow": sh,
                "fill_enabled": False, "fill_color": None}
    if isinstance(item, StepItem):
        return {"groups": ["color"] + extra, "color": QColor(item._color),
                "width": None, "font_size": None,
                "opacity": op, "shadow": sh,
                "fill_enabled": False, "fill_color": None}
    if isinstance(item, StampItem):
        return {"groups": ["color"] + extra, "color": QColor(item._color),
                "width": None, "font_size": None,
                "opacity": op, "shadow": sh,
                "fill_enabled": False, "fill_color": None}
    if isinstance(item, ArrowItem):
        # Mũi tên: hiện cả màu lẫn độ dày (dựng lại hình theo width mới).
        return {"groups": ["color", "width"] + extra,
                "color": QColor(item.pen().color()),
                "width": item._width, "font_size": None,
                "opacity": op, "shadow": sh,
                "fill_enabled": False, "fill_color": None}
    if isinstance(item, QGraphicsPolygonItem):
        # Polygon tô đặc khác: chỉ đổi được màu.
        return {"groups": ["color"] + extra, "color": QColor(item.pen().color()),
                "width": None, "font_size": None,
                "opacity": op, "shadow": sh,
                "fill_enabled": False, "fill_color": None}
    # rect / ellipse / line / path
    groups: list[str] = []
    color: QColor | None = None
    width: int | None = None
    if hasattr(item, "pen") and item.pen().style() != Qt.NoPen:
        groups.extend(["color", "width"])
        color = QColor(item.pen().color())
        width = item.pen().width()
    if hasattr(item, "brush") and item.brush().style() != Qt.NoBrush:
        # Highlight (NoPen + brush tô): chỉ hiện màu, lấy từ brush nếu pen rỗng.
        if "color" not in groups:
            groups.insert(0, "color")
        if color is None:
            color = QColor(item.brush().color())
    # Fill chỉ áp cho rect/ellipse CÓ viền (loại trừ highlight NoPen, line, path).
    fill_enabled = False
    fill_color: QColor | None = None
    if (isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
            and item.pen().style() != Qt.NoPen):
        groups.append("fill")
        fill_enabled = item.brush().style() != Qt.NoBrush
        fill_color = QColor(item.brush().color()) if fill_enabled else None
    return {"groups": groups + extra, "color": color, "width": width,
            "font_size": None, "opacity": op, "shadow": sh,
            "fill_enabled": fill_enabled, "fill_color": fill_color}


# Chỉ số 8 handle quanh khung bao của item (theo chiều kim đồng hồ từ góc trên-trái).
HANDLE_TL, HANDLE_T, HANDLE_TR, HANDLE_R, HANDLE_BR, HANDLE_B, HANDLE_BL, HANDLE_L = range(8)

# Con trỏ gợi ý hướng kéo cho từng handle.
HANDLE_CURSORS = {
    HANDLE_TL: Qt.SizeFDiagCursor, HANDLE_BR: Qt.SizeFDiagCursor,
    HANDLE_TR: Qt.SizeBDiagCursor, HANDLE_BL: Qt.SizeBDiagCursor,
    HANDLE_T: Qt.SizeVerCursor, HANDLE_B: Qt.SizeVerCursor,
    HANDLE_L: Qt.SizeHorCursor, HANDLE_R: Qt.SizeHorCursor,
}


def rect_for_handle(index: int, base: QRectF, cursor: QPointF,
                    min_size: float = 8.0, keep_aspect: bool = False,
                    from_center: bool = False) -> QRectF:
    """Tính khung bao mới khi kéo handle `index` tới điểm `cursor`.

    Hàm thuần (không phụ thuộc trạng thái) để test headless:
    - Mặc định: cạnh đối diện handle đứng yên (anchor), cạnh/góc kéo bám con trỏ;
      handle cạnh giữa chỉ đổi một chiều.
    - keep_aspect (Shift): giữ nguyên tỉ lệ của `base`.
    - from_center (Alt): scale đối xứng quanh tâm của `base`.
    Luôn clamp kích thước tối thiểu để tránh lật/biến mất.
    """
    move_left = index in (HANDLE_TL, HANDLE_L, HANDLE_BL)
    move_right = index in (HANDLE_TR, HANDLE_R, HANDLE_BR)
    move_top = index in (HANDLE_TL, HANDLE_T, HANDLE_TR)
    move_bottom = index in (HANDLE_BL, HANDLE_B, HANDLE_BR)
    moves_x = move_left or move_right
    moves_y = move_top or move_bottom

    cx, cy = base.center().x(), base.center().y()

    # --- chiều rộng / cao mong muốn (chưa neo) ---
    if not moves_x:
        w = base.width()
    elif from_center:
        w = 2.0 * (cursor.x() - cx) if move_right else 2.0 * (cx - cursor.x())
    else:
        w = cursor.x() - base.left() if move_right else base.right() - cursor.x()

    if not moves_y:
        h = base.height()
    elif from_center:
        h = 2.0 * (cursor.y() - cy) if move_bottom else 2.0 * (cy - cursor.y())
    else:
        h = cursor.y() - base.top() if move_bottom else base.bottom() - cursor.y()

    w = max(w, min_size)
    h = max(h, min_size)

    # --- giữ tỉ lệ ---
    derived_x = derived_y = False
    if keep_aspect and base.width() > 0 and base.height() > 0:
        ratio = base.width() / base.height()
        if moves_x and moves_y:                 # góc: lấy hộp lớn hơn
            if w / ratio >= h:
                h = w / ratio
            else:
                w = h * ratio
        elif moves_x:                           # cạnh dọc: suy ra chiều cao
            h = w / ratio
            derived_y = True
        elif moves_y:                           # cạnh ngang: suy ra chiều rộng
            w = h * ratio
            derived_x = True
        w = max(w, min_size)
        h = max(h, min_size)

    # --- neo lại theo handle (hoặc đối xứng quanh tâm) ---
    if not moves_x and not derived_x:
        left = base.left()
    elif from_center or derived_x:
        left = cx - w / 2.0
    elif move_right:
        left = base.left()
    else:                                        # move_left
        left = base.right() - w

    if not moves_y and not derived_y:
        top = base.top()
    elif from_center or derived_y:
        top = cy - h / 2.0
    elif move_bottom:
        top = base.top()
    else:                                        # move_top
        top = base.bottom() - h

    r = QRectF()
    r.setCoords(left, top, left + w, top + h)
    return r.normalized()


def transform_for_resize(old_local: QTransform, pos: QPointF,
                         old_rect: QRectF, new_rect: QRectF) -> QTransform:
    """Trả về QTransform cục bộ mới để khung bao (scene) đi từ old_rect → new_rect.

    Toán: D là phép scale+tịnh tiến trong toạ độ scene đưa old_rect khít new_rect.
    sceneTransform mới = old_full * D, với old_full = old_local * T(pos). Giữ pos
    cố định nên local mới = old_local * T(pos) * D * T(-pos). Hàm thuần, test được.
    """
    if old_rect.width() == 0 or old_rect.height() == 0:
        return QTransform(old_local)
    sx = new_rect.width() / old_rect.width()
    sy = new_rect.height() / old_rect.height()
    d = QTransform()
    d.translate(new_rect.left(), new_rect.top())
    d.scale(sx, sy)
    d.translate(-old_rect.left(), -old_rect.top())
    tp = QTransform.fromTranslate(pos.x(), pos.y())
    tpi = QTransform.fromTranslate(-pos.x(), -pos.y())
    return old_local * tp * d * tpi


class ResizeHandle(QGraphicsRectItem):
    """Ô vuông nhỏ ở mép item để kéo resize; giữ kích thước cố định khi zoom."""

    def __init__(self, index: int) -> None:
        super().__init__(-4.0, -4.0, 8.0, 8.0)
        self.index = index
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(QColor("#1E90FF"), 1.5))
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setZValue(10_000)
        # View tự bắt chuột trên handle qua hit-test; handle không nhận chuột.
        self.setAcceptedMouseButtons(Qt.NoButton)
        # Cursor gán thẳng lên item → Qt hiển thị đúng khi hover, không bị
        # QGraphicsView.mouseMoveEvent ghi đè.
        self.setCursor(HANDLE_CURSORS[index])


class Canvas(QGraphicsView):
    # Phát số bước kế tiếp khi đặt badge mới hoặc nạp ảnh (để panel đồng bộ).
    step_number_changed = Signal(int)
    # Phát mức zoom hiện tại theo phần trăm (vd 120.0) khi thay đổi.
    zoom_changed = Signal(float)
    # Phát (rộng, cao) khung bao khi đang kéo resize → status bar đọc trực tiếp.
    resize_preview = Signal(float, float)
    # Phát khi kết thúc kéo resize → status bar khôi phục gợi ý công cụ.
    resize_finished = Signal()
    # Phát khi tập chọn thay đổi → panel đồng bộ nhóm thuộc tính theo item đang chọn.
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)

        self.state = ToolState()
        self.undo_stack = QUndoStack(self)
        self._bg_item: QGraphicsPixmapItem | None = None
        self._temp_item: QGraphicsItem | None = None
        self._start: QPointF | None = None
        self._pen_path: QPainterPath | None = None
        self._move_origins: dict[QGraphicsItem, QPointF] = {}
        # True trong lúc kéo chọn/di chuyển item (kể cả direct-select ở công cụ vẽ),
        # để mouseRelease chốt MoveItemCommand thay vì kết thúc một nét vẽ.
        self._select_drag = False
        # Khi True, resize cửa sổ sẽ tự fit ảnh vào khung. Zoom thủ công tắt cờ này.
        self._auto_fit = True

        # --- resize handle ---
        self._handles: list[ResizeHandle] = []
        self._resize_target: QGraphicsItem | None = None   # item đang có handle
        self._resize_item: QGraphicsItem | None = None      # item đang được kéo
        self._active_handle: int | None = None
        self._resize_origin_rect: QRectF | None = None
        self._resize_old_transform: QTransform | None = None
        self._scene.selectionChanged.connect(self._update_handles)
        self._scene.selectionChanged.connect(self.selection_changed)

    # ---------- ảnh nền ----------
    def load_image(self, image: QImage) -> None:
        self._scene.clear()
        # scene.clear() đã huỷ các handle cũ → quên tham chiếu để khỏi truy cập rác.
        self._handles = []
        self._resize_target = None
        self._resize_item = None
        self.undo_stack.clear()
        self.state.step_number = 1
        self._auto_fit = True
        self.resetTransform()
        self._bg_item = QGraphicsPixmapItem(QPixmap.fromImage(image))
        self._bg_item.setZValue(-1000)
        self._scene.addItem(self._bg_item)
        self._scene.setSceneRect(QRectF(image.rect()))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self.step_number_changed.emit(self.state.step_number)
        self._emit_zoom()

    def has_image(self) -> bool:
        return self._bg_item is not None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._bg_item is not None and self._auto_fit:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
            self._emit_zoom()

    # ---------- zoom ----------
    def _emit_zoom(self) -> None:
        self.zoom_changed.emit(self.transform().m11() * 100.0)

    def zoom_in(self) -> None:
        self._manual_zoom(1.25)

    def zoom_out(self) -> None:
        self._manual_zoom(0.8)

    def _manual_zoom(self, factor: float) -> None:
        if self._bg_item is None:
            return
        self._auto_fit = False
        self.scale(factor, factor)
        self._emit_zoom()

    def zoom_fit(self) -> None:
        self._auto_fit = True
        if self._bg_item is not None:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._emit_zoom()

    def zoom_actual(self) -> None:
        if self._bg_item is None:
            return
        self._auto_fit = False
        self.resetTransform()
        self._emit_zoom()

    def wheelEvent(self, event) -> None:
        # Ctrl + lăn chuột = zoom tại con trỏ.
        if event.modifiers() & Qt.ControlModifier and self._bg_item is not None:
            self._auto_fit = False
            anchor = self.transformationAnchor()
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(factor, factor)
            self.setTransformationAnchor(anchor)
            self._emit_zoom()
            event.accept()
        else:
            super().wheelEvent(event)

    # ---------- xuất ảnh ----------
    def render_to_image(self) -> QImage:
        """Gộp ảnh nền + mọi chú thích thành QImage để lưu."""
        rect = self._scene.sceneRect()
        image = QImage(int(rect.width()), int(rect.height()),
                       QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self._scene.clearSelection()
        self._scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        return image

    # ---------- chuột vẽ ----------
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or not self.has_image():
            return super().mousePressEvent(event)

        # Click ra ngoài một Callout/Text đang soạn → thoát soạn (commit) trước khi xử tiếp.
        fi = self._scene.focusItem()
        if (isinstance(fi, QGraphicsTextItem)
                and fi.textInteractionFlags() != Qt.NoTextInteraction
                and self._annotation_at(event.position().toPoint()) is not fi):
            fi.clearFocus()

        # 1. Trúng một resize handle (ở BẤT KỲ công cụ nào) → bắt đầu kéo resize.
        idx = self._handle_at(event.position().toPoint())
        if idx is not None and self._resize_target is not None:
            self._begin_resize(idx)
            event.accept()
            return

        # 2. Direct-select: ở công cụ Chọn, hoặc khi nhấn TRÚNG NÉT một chú thích
        #    (kiểu Figma/PPT) ở công cụ vẽ → chọn + di chuyển thay vì vẽ.
        is_select = (self.state.tool == Tool.SELECT
                     or self._annotation_at(event.position().toPoint()) is not None)
        if is_select:
            super().mousePressEvent(event)
            # Ghi lại vị trí trước khi kéo để dựng MoveItemCommand khi nhả chuột.
            self._move_origins = {
                it: it.pos() for it in self._scene.selectedItems()
                if it is not self._bg_item
            }
            self._select_drag = True
            return

        # 3. Vẽ trên vùng trống → bỏ chọn item cũ (ẩn handle) rồi bắt đầu vẽ.
        self._scene.clearSelection()
        self._start = self.mapToScene(event.position().toPoint())

        if self.state.tool == Tool.TEXT:
            self._add_text(self._start)
            return
        if self.state.tool == Tool.STEP:
            self._add_step(self._start)
            return
        if self.state.tool == Tool.STAMP:
            self._add_stamp(self._start)
            return

        pen = QPen(self.state.color, self.state.width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        t = self.state.tool

        if t == Tool.RECT:
            self._temp_item = QGraphicsRectItem(QRectF(self._start, self._start))
            self._temp_item.setPen(pen)
        elif t == Tool.ELLIPSE:
            self._temp_item = QGraphicsEllipseItem(QRectF(self._start, self._start))
            self._temp_item.setPen(pen)
        elif t == Tool.ARROW:
            # Preview là ArrowItem thật (có đầu mũi tên), cập nhật theo chuột.
            self._temp_item = ArrowItem(
                self._start, self._start, self.state.color, self.state.width
            )
        elif t in (Tool.BLUR, Tool.HIGHLIGHT, Tool.CROP, Tool.SPOTLIGHT,
                   Tool.CALLOUT):
            self._temp_item = QGraphicsRectItem(QRectF(self._start, self._start))
            self._temp_item.setPen(QPen(QColor("#1E90FF"), 1, Qt.DashLine))
        elif t == Tool.PEN:
            self._pen_path = QPainterPath(self._start)
            self._temp_item = QGraphicsPathItem(self._pen_path)
            self._temp_item.setPen(pen)

        if self._temp_item is not None:
            self._scene.addItem(self._temp_item)

    def mouseMoveEvent(self, event) -> None:
        # Đang kéo resize: cập nhật trực tiếp, không đụng luồng vẽ/di chuyển.
        if self._resize_item is not None:
            mods = event.modifiers()
            self._resize_to(
                self.mapToScene(event.position().toPoint()),
                keep_aspect=bool(mods & Qt.ShiftModifier),
                from_center=bool(mods & Qt.AltModifier),
            )
            event.accept()
            return
        if self._start is None or self._temp_item is None:
            super().mouseMoveEvent(event)
            # Khi kéo item (direct-select hoặc công cụ Chọn), handle phải bám theo.
            # _position_handles tự bỏ qua nếu không có target nên gọi vô điều kiện.
            self._position_handles()
            return
        cur = self.mapToScene(event.position().toPoint())
        t = self.state.tool
        if t in (Tool.RECT, Tool.ELLIPSE, Tool.BLUR, Tool.HIGHLIGHT, Tool.CROP,
                 Tool.SPOTLIGHT, Tool.CALLOUT):
            self._temp_item.setRect(QRectF(self._start, cur).normalized())
        elif t == Tool.ARROW:
            self._temp_item.set_points(self._start, cur)
        elif t == Tool.PEN and self._pen_path is not None:
            self._pen_path.lineTo(cur)
            self._temp_item.setPath(self._pen_path)

    def mouseReleaseEvent(self, event) -> None:
        # Kết thúc kéo resize: chốt 1 ResizeItemCommand để undo/redo.
        if self._resize_item is not None:
            self._commit_resize()
            event.accept()
            return
        if self._select_drag:
            super().mouseReleaseEvent(event)
            self._commit_moves()
            self._position_handles()
            self._select_drag = False
            return

        if self._start is None or self._temp_item is None:
            return super().mouseReleaseEvent(event)

        cur = self.mapToScene(event.position().toPoint())
        t = self.state.tool

        if t == Tool.ARROW:
            # Chốt đúng đầu mút cuối rồi đưa luôn item preview vào undo stack.
            self._temp_item.set_points(self._start, cur)
            self._finalize(self._temp_item)
        elif t == Tool.HIGHLIGHT:
            rect = QRectF(self._start, cur).normalized()
            self._scene.removeItem(self._temp_item)
            item = QGraphicsRectItem(rect)
            hl = QColor(self.state.color)
            hl.setAlpha(90)
            item.setBrush(QBrush(hl))
            item.setPen(QPen(Qt.NoPen))
            self._finalize(item)
        elif t == Tool.BLUR:
            rect = QRectF(self._start, cur).normalized()
            self._scene.removeItem(self._temp_item)
            self._apply_blur(rect)
        elif t == Tool.CROP:
            rect = QRectF(self._start, cur).normalized()
            self._scene.removeItem(self._temp_item)
            self._apply_crop(rect)
        elif t == Tool.SPOTLIGHT:
            rect = QRectF(self._start, cur).normalized()
            self._scene.removeItem(self._temp_item)
            self._add_spotlight(rect)
        elif t == Tool.CALLOUT:
            rect = QRectF(self._start, cur).normalized()
            self._scene.removeItem(self._temp_item)
            # click/kéo quá nhỏ → không tạo callout, để click dùng cho chọn object
            # (giống Rect). Chỉ kéo đủ lớn mới tạo bong bóng.
            if (rect.width() >= self._CALLOUT_MIN_DRAG
                    and rect.height() >= self._CALLOUT_MIN_DRAG):
                self._add_callout(rect)
        else:
            self._finalize(self._temp_item)

        self._temp_item = None
        self._start = None
        self._pen_path = None

    def mouseDoubleClickEvent(self, event) -> None:
        # Double-click một Callout → vào soạn chữ (mọi công cụ).
        if self.has_image():
            hit = self._annotation_at(event.position().toPoint())
            if isinstance(hit, CalloutItem):
                hit.enter_edit()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    # ---------- tạo item qua undo stack ----------
    def _finalize(self, item: QGraphicsItem) -> None:
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.ItemIsMovable, True)
        # Gỡ khỏi scene trước rồi để AddItemCommand.redo() thêm lại -> undo nhất quán.
        if item.scene() is not None:
            self._scene.removeItem(item)
        self.undo_stack.push(AddItemCommand(self._scene, item))

    def _add_text(self, pos: QPointF) -> None:
        item = QGraphicsTextItem("Nhập chữ...")
        font = QFont()
        font.setPointSize(self.state.font_size)
        item.setFont(font)
        item.setDefaultTextColor(self.state.color)
        item.setPos(pos)
        item.setTextInteractionFlags(Qt.TextEditorInteraction)
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.ItemIsMovable, True)
        self._scene.addItem(item)
        # item đã ở scene; AddItemCommand.redo() lần đầu là no-op, undo gỡ ra.
        self.undo_stack.push(AddItemCommand(self._scene, item, "Thêm chữ"))
        item.setFocus()
        self._start = None
        self._temp_item = None

    # Kéo nhỏ hơn ngưỡng này (px) coi như click → KHÔNG tạo callout (để click dùng
    # cho chọn object, giống Rect). Gate ở mouseReleaseEvent nhánh CALLOUT.
    _CALLOUT_MIN_DRAG = 20.0

    def _add_callout(self, rect: QRectF) -> None:
        item = CalloutItem("Nhập chú thích...", QColor("#FFFFFF"),
                           self.state.color, self.state.width, self.state.font_size)
        item.setPos(rect.topLeft())
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        item.setFlag(QGraphicsItem.ItemIsMovable, True)
        self._scene.addItem(item)
        # Scale-fit callout vào rect đã kéo (bong bóng + chữ co theo) bằng transform
        # (giống kéo handle) để khung bao khít rect đã kéo.
        old_rect = item.sceneBoundingRect()
        if old_rect.width() > 0 and old_rect.height() > 0:
            item.setTransform(transform_for_resize(
                QTransform(item.transform()), item.pos(), old_rect, rect))
        # item đã ở scene; AddItemCommand.redo() lần đầu là no-op, undo gỡ ra.
        self.undo_stack.push(AddItemCommand(self._scene, item, "Thêm callout"))
        # Vào soạn chữ ngay để gõ liền; click ra ngoài/Escape → object thường.
        item.enter_edit()
        self._start = None
        self._temp_item = None

    def _add_step(self, pos: QPointF) -> None:
        diameter = max(28.0, self.state.width * 5.0)
        item = StepItem(self.state.step_number, self.state.color, diameter)
        item.setPos(pos.x() - diameter / 2, pos.y() - diameter / 2)
        self.undo_stack.push(AddItemCommand(self._scene, item, "Thêm số bước"))
        self.state.step_number += 1
        self.step_number_changed.emit(self.state.step_number)
        self._start = None
        self._temp_item = None

    def _add_stamp(self, pos: QPointF) -> None:
        size = 48.0
        item = StampItem(self.state.stamp_name, self.state.color, size)
        item.setPos(pos.x() - size / 2, pos.y() - size / 2)
        self.undo_stack.push(AddItemCommand(self._scene, item, "Thêm stamp"))
        self._start = None
        self._temp_item = None

    def _add_spotlight(self, rect: QRectF) -> None:
        if self._bg_item is None:
            return
        scene_rect = QRectF(self._scene.sceneRect())
        hole = rect.intersected(scene_rect)
        # Vùng giữ sáng quá nhỏ → bỏ qua (tránh overlay phủ kín vô nghĩa).
        if hole.width() < 2 or hole.height() < 2:
            self._start = None
            self._temp_item = None
            return
        spot = SpotlightItem(scene_rect, hole)
        self.undo_stack.push(AddItemCommand(self._scene, spot, "Tiêu điểm"))
        self._start = None
        self._temp_item = None

    def _apply_blur(self, rect: QRectF) -> None:
        """Nướng vùng làm mờ vào ảnh nền qua BlurCommand (undo được)."""
        if self._bg_item is None:
            return
        r = rect.intersected(self._scene.sceneRect()).toRect()
        if r.width() < 2 or r.height() < 2:
            return
        base = self._bg_item.pixmap().toImage().convertToFormat(QImage.Format_ARGB32)
        old_sub = base.copy(r)
        small = old_sub.scaled(
            max(1, r.width() // 12), max(1, r.height() // 12),
            Qt.IgnoreAspectRatio, Qt.FastTransformation,
        )
        new_sub = small.scaled(r.width(), r.height(),
                               Qt.IgnoreAspectRatio, Qt.FastTransformation)
        self.undo_stack.push(BlurCommand(self._bg_item, r, old_sub, new_sub))

    def _apply_crop(self, rect: QRectF) -> None:
        """Cắt ảnh theo vùng chọn qua CropCommand (undo được), rồi fit lại."""
        if self._bg_item is None:
            return
        r = rect.intersected(self._scene.sceneRect()).toRect()
        if r.width() < 2 or r.height() < 2:
            return
        self.undo_stack.push(CropCommand(self._scene, self._bg_item, r))
        self.zoom_fit()

    def _commit_moves(self) -> None:
        moved = [
            (it, old, it.pos())
            for it, old in self._move_origins.items()
            if it.pos() != old
        ]
        self._move_origins = {}
        if not moved:
            return
        self.undo_stack.beginMacro("Di chuyển")
        for it, old, new in moved:
            self.undo_stack.push(MoveItemCommand(it, old, new))
        self.undo_stack.endMacro()

    # ---------- sửa style item đã chọn ----------
    def selected_annotation(self) -> QGraphicsItem | None:
        """Trả item chú thích nếu ĐÚNG 1 cái được chọn (bỏ nền + handle), else None."""
        sel = [
            it for it in self._scene.selectedItems()
            if it is not self._bg_item and not isinstance(it, ResizeHandle)
        ]
        return sel[0] if len(sel) == 1 else None

    def apply_style_to_selection(self, color: QColor | None = None,
                                 width: int | None = None,
                                 font_size: int | None = None,
                                 opacity: float | None = None,
                                 shadow: bool | None = None,
                                 fill: QColor | None = None,
                                 fill_enabled: bool | None = None) -> bool:
        """Áp style (màu/độ dày/cỡ chữ/độ trong suốt/đổ bóng/tô nền) lên item chọn.

        Chỉ áp cho item phù hợp (text nhận màu + cỡ chữ, hình nhận màu + độ dày…).
        Opacity/shadow áp cho mọi loại item; fill chỉ cho rect/ellipse có viền. Gọi
        an toàn khi chưa có item nào được chọn (panel bắn slot lúc khởi tạo): trả
        False và không tạo command nếu không có thay đổi thật.
        """
        if (color is None and width is None and font_size is None
                and opacity is None and shadow is None
                and fill is None and fill_enabled is None):
            return False
        targets = [
            it for it in self._scene.selectedItems()
            if it is not self._bg_item and not isinstance(it, ResizeHandle)
        ]
        if not targets:
            return False
        changes: list[tuple[QGraphicsItem, dict, dict]] = []
        for it in targets:
            old = capture_item_style(it)
            mutate_item_style(it, color=color, width=width, font_size=font_size,
                              opacity=opacity, shadow=shadow,
                              fill=fill, fill_enabled=fill_enabled)
            new = capture_item_style(it)
            if new != old:
                changes.append((it, old, new))
        if not changes:
            return False
        self.undo_stack.push(StyleCommand(changes))
        self._position_handles()
        return True

    # ---------- resize handle ----------
    def refresh_handles(self) -> None:
        """Cho EditorWindow gọi khi đổi công cụ (ẩn handle nếu rời công cụ Chọn)."""
        self._update_handles()

    def _ensure_handles(self) -> None:
        if self._handles:
            return
        for i in range(8):
            h = ResizeHandle(i)
            h.setVisible(False)
            self._scene.addItem(h)
            self._handles.append(h)

    def _annotation_at(self, view_pos) -> QGraphicsItem | None:
        """Item chú thích (bỏ nền + handle) ngay dưới con trỏ, theo shape().

        Dùng cho direct-select: nhấn TRÚNG NÉT một object là chọn được, ở bất kỳ
        công cụ nào. items() trả theo thứ tự xếp chồng (trên xuống) và hit-test
        bằng shape() nên chỉ trúng khi con trỏ nằm trên nét/vùng tô của item.
        """
        for it in self.items(view_pos):
            if it is self._bg_item or isinstance(it, (ResizeHandle, SpotlightItem)):
                continue
            if it.flags() & QGraphicsItem.ItemIsSelectable:
                return it
        return None

    def _update_handles(self) -> None:
        """Hiện 8 handle khi đúng 1 item (khác nền) được chọn — mọi công cụ."""
        sel = [it for it in self._scene.selectedItems() if it is not self._bg_item]
        if len(sel) == 1:
            self._resize_target = sel[0]
            self._ensure_handles()
            for h in self._handles:
                h.setVisible(True)
            self._position_handles()
        else:
            self._resize_target = None
            for h in self._handles:
                h.setVisible(False)

    def _position_handles(self) -> None:
        if self._resize_target is None or not self._handles:
            return
        r = self._resize_target.sceneBoundingRect()
        cx, cy = r.center().x(), r.center().y()
        pts = [
            r.topLeft(), QPointF(cx, r.top()), r.topRight(),
            QPointF(r.right(), cy), r.bottomRight(),
            QPointF(cx, r.bottom()), r.bottomLeft(), QPointF(r.left(), cy),
        ]
        for h, p in zip(self._handles, pts):
            h.setPos(p)

    def _handle_at(self, view_pos) -> int | None:
        """Tìm handle dưới con trỏ (xét theo toạ độ view nên ổn định mọi mức zoom)."""
        for h in self._handles:
            if not h.isVisible():
                continue
            hp = self.mapFromScene(h.pos())
            if abs(hp.x() - view_pos.x()) <= 6 and abs(hp.y() - view_pos.y()) <= 6:
                return h.index
        return None

    def _begin_resize(self, index: int) -> None:
        item = self._resize_target
        if item is None:
            return
        self._resize_item = item
        self._active_handle = index
        self._resize_origin_rect = item.sceneBoundingRect()
        self._resize_old_transform = QTransform(item.transform())

    def _resize_to(self, cursor_scene: QPointF, keep_aspect: bool = False,
                   from_center: bool = False) -> None:
        """Áp resize trực tiếp khi đang kéo (chưa push command)."""
        if (self._resize_item is None or self._active_handle is None
                or self._resize_origin_rect is None
                or self._resize_old_transform is None):
            return
        new_rect = rect_for_handle(
            self._active_handle, self._resize_origin_rect, cursor_scene,
            keep_aspect=keep_aspect, from_center=from_center,
        )
        new_t = transform_for_resize(
            self._resize_old_transform, self._resize_item.pos(),
            self._resize_origin_rect, new_rect,
        )
        self._resize_item.setTransform(new_t)
        self._position_handles()
        self.resize_preview.emit(new_rect.width(), new_rect.height())

    def _commit_resize(self) -> None:
        item = self._resize_item
        old_t = self._resize_old_transform
        self._resize_item = None
        self._active_handle = None
        self._resize_origin_rect = None
        self._resize_old_transform = None
        if item is None or old_t is None:
            return
        new_t = item.transform()
        if new_t != old_t:
            self.undo_stack.push(ResizeItemCommand(item, old_t, new_t))
        self._position_handles()
        self.resize_finished.emit()

    # ---------- xoá / phím tắt ----------
    _ARROW_DELTA = {
        Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
        Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1),
    }

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Đang gõ trong text item → để text item nhận phím (xoá ký tự),
            # không xoá cả object.
            focus = self._scene.focusItem()
            if (isinstance(focus, QGraphicsTextItem)
                    and focus.textInteractionFlags() & Qt.TextEditorInteraction):
                return super().keyPressEvent(event)
            items = [it for it in self._scene.selectedItems() if it is not self._bg_item]
            if items:
                self.undo_stack.push(DeleteItemsCommand(self._scene, items))
            return
        if event.key() in self._ARROW_DELTA:
            # Đang gõ trong text item → để text item nhận phím (di chuyển con trỏ).
            if isinstance(self._scene.focusItem(), QGraphicsTextItem):
                return super().keyPressEvent(event)
            items = [it for it in self._scene.selectedItems()
                     if it is not self._bg_item]
            if not items:
                return super().keyPressEvent(event)
            step = 10 if event.modifiers() & Qt.ShiftModifier else 1
            ux, uy = self._ARROW_DELTA[event.key()]
            dx, dy = ux * step, uy * step
            self.undo_stack.beginMacro("Di chuyển")
            for it in items:
                old = QPointF(it.pos())
                self.undo_stack.push(
                    MoveItemCommand(it, old, QPointF(old.x() + dx, old.y() + dy))
                )
            self.undo_stack.endMacro()
            self._position_handles()
            event.accept()
            return
        super().keyPressEvent(event)
