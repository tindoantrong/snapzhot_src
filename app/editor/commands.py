"""Các lệnh Undo/Redo cho canvas, dựa trên QUndoCommand của Qt.

Mỗi thao tác vẽ/sửa được bọc trong một command để QUndoStack quản lý
hoàn tác/làm lại nhiều bước. Lưu ý: khi push vào stack, Qt gọi redo() ngay,
nên các command được viết sao cho redo() lần đầu trùng với trạng thái hiện tại
(idempotent) — ví dụ item đã nằm sẵn trong scene thì redo() không thêm lại.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QTransform, QUndoCommand
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
)


def _make_shadow_effect() -> QGraphicsDropShadowEffect:
    """Tạo MỚI một effect đổ bóng mềm.

    QGraphicsEffect chỉ gắn được 1 item tại một thời điểm, nên mỗi lần áp shadow
    (redo/undo nhiều lần) phải dựng một effect mới để tránh dùng lại instance đã
    bị gỡ khỏi item khác.
    """
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(12)
    eff.setOffset(4, 4)
    eff.setColor(QColor(0, 0, 0, 160))
    return eff


class AddItemCommand(QUndoCommand):
    """Thêm một item chú thích vào scene (undo = gỡ ra)."""

    def __init__(self, scene: QGraphicsScene, item: QGraphicsItem,
                 text: str = "Thêm đối tượng") -> None:
        super().__init__(text)
        self._scene = scene
        self._item = item

    def redo(self) -> None:
        if self._item.scene() is None:
            self._scene.addItem(self._item)

    def undo(self) -> None:
        self._scene.removeItem(self._item)


class DeleteItemsCommand(QUndoCommand):
    """Xoá nhiều item đang chọn (undo = thêm lại)."""

    def __init__(self, scene: QGraphicsScene,
                 items: list[QGraphicsItem]) -> None:
        super().__init__("Xoá đối tượng")
        self._scene = scene
        self._items = list(items)

    def redo(self) -> None:
        for it in self._items:
            if it.scene() is not None:
                self._scene.removeItem(it)

    def undo(self) -> None:
        for it in self._items:
            if it.scene() is None:
                self._scene.addItem(it)


class MoveItemCommand(QUndoCommand):
    """Di chuyển một item (đã ở vị trí mới khi command được tạo)."""

    def __init__(self, item: QGraphicsItem,
                 old_pos: QPointF, new_pos: QPointF) -> None:
        super().__init__("Di chuyển")
        self._item = item
        self._old = QPointF(old_pos)
        self._new = QPointF(new_pos)

    def redo(self) -> None:
        self._item.setPos(self._new)

    def undo(self) -> None:
        self._item.setPos(self._old)


class ResizeItemCommand(QUndoCommand):
    """Đổi kích thước (scale) một item bằng cách thay QTransform cục bộ.

    Resize được hiện thực qua transform chứ không sửa hình học gốc của item,
    nên áp dụng đồng nhất cho mọi loại item (rect, ellipse, arrow, text, step…).
    pos() giữ nguyên; undo/redo chỉ cần đặt lại transform.
    """

    def __init__(self, item: QGraphicsItem,
                 old_transform: QTransform, new_transform: QTransform) -> None:
        super().__init__("Đổi kích thước")
        self._item = item
        self._old = QTransform(old_transform)
        self._new = QTransform(new_transform)

    def redo(self) -> None:
        self._item.setTransform(self._new)

    def undo(self) -> None:
        self._item.setTransform(self._old)


def _apply_style_snapshot(item: QGraphicsItem, snap: dict) -> None:
    """Áp một snapshot style lên item (chỉ các khoá có trong snap).

    Duck-typing theo từng loại item: pen/brush cho hình vector, text_color/font
    cho text, step_color cho badge số bước. Snapshot do canvas dựng ra nên ở đây
    chỉ cần gọi đúng setter tương ứng với từng khoá có mặt.
    """
    if "arrow_polygon" in snap:
        # Mũi tên: khôi phục hình (đã mã hoá độ dày) + width gốc đã lưu trên item.
        item.setPolygon(snap["arrow_polygon"])
    if "arrow_width" in snap:
        item._width = snap["arrow_width"]
    if "pen" in snap:
        item.setPen(snap["pen"])
    if "brush" in snap:
        item.setBrush(snap["brush"])
    if "opacity" in snap:
        item.setOpacity(snap["opacity"])
    if "shadow" in snap:
        item.setGraphicsEffect(_make_shadow_effect() if snap["shadow"] else None)
    if "text_color" in snap:
        item.setDefaultTextColor(snap["text_color"])
    if "font" in snap:
        item.setFont(snap["font"])
    if "step_color" in snap:
        item.set_color(snap["step_color"])
    if "stamp_color" in snap:
        item.set_color(snap["stamp_color"])
    if "callout_fill" in snap:
        item.set_fill(snap["callout_fill"])
    if "callout_border" in snap:
        # callout_width đi kèm trong cùng snapshot (cùng do capture_item_style dựng).
        item.set_border(snap["callout_border"], snap.get("callout_width"))


class StyleCommand(QUndoCommand):
    """Đổi style (màu/độ dày/cỡ chữ) của một hay nhiều item, hoàn tác được.

    Mỗi phần tử trong `changes` là (item, old_snap, new_snap) với snapshot là dict
    khoá thuộc tính (pen/brush/text_color/font/step_color). Khi push, Qt gọi redo()
    ngay; item đã ở trạng thái mới khi command được tạo nên redo() lần đầu trùng
    trạng thái hiện tại (idempotent).
    """

    def __init__(self, changes: list[tuple[QGraphicsItem, dict, dict]],
                 text: str = "Đổi style") -> None:
        super().__init__(text)
        self._changes = list(changes)

    def redo(self) -> None:
        for item, _old, new in self._changes:
            _apply_style_snapshot(item, new)

    def undo(self) -> None:
        for item, old, _new in self._changes:
            _apply_style_snapshot(item, old)


class BlurCommand(QUndoCommand):
    """Làm mờ một vùng đã được nướng vào ảnh nền.

    Lưu ảnh con của vùng đó trước (old) và sau (new) để khôi phục pixel.
    """

    def __init__(self, bg_item: QGraphicsPixmapItem, rect: QRect,
                 old_sub: QImage, new_sub: QImage) -> None:
        super().__init__("Làm mờ")
        self._bg = bg_item
        self._top_left: QPoint = rect.topLeft()
        self._old = old_sub
        self._new = new_sub

    def _paint(self, sub: QImage) -> None:
        img = self._bg.pixmap().toImage().convertToFormat(QImage.Format_ARGB32)
        painter = QPainter(img)
        painter.drawImage(self._top_left, sub)
        painter.end()
        self._bg.setPixmap(QPixmap.fromImage(img))

    def redo(self) -> None:
        self._paint(self._new)

    def undo(self) -> None:
        self._paint(self._old)


class CropCommand(QUndoCommand):
    """Cắt ảnh theo một vùng chữ nhật, giữ nguyên chú thích (kiểu Snagit).

    - Cắt pixmap nền theo rect.
    - Dời mọi item chú thích đi -rect.topLeft() để giữ vị trí tương đối.
    - Đặt lại sceneRect về kích thước vùng cắt (gốc 0,0).

    Lưu state cũ (pixmap, sceneRect) để undo khôi phục; vị trí item được khôi
    phục bằng cách dời ngược lại offset.
    """

    def __init__(self, scene: QGraphicsScene, bg_item: QGraphicsPixmapItem,
                 rect: QRect) -> None:
        super().__init__("Cắt ảnh")
        self._scene = scene
        self._bg = bg_item
        self._rect = QRect(rect)
        self._offset = QPointF(rect.topLeft())
        self._old_pixmap = QPixmap(bg_item.pixmap())
        self._new_pixmap = self._old_pixmap.copy(self._rect)
        self._old_scene_rect = QRectF(scene.sceneRect())
        self._new_scene_rect = QRectF(0, 0, rect.width(), rect.height())
        # Các item chú thích cần dời (mọi item trừ ảnh nền và các handle resize).
        self._items = [
            it for it in scene.items()
            if it is not bg_item
            and not (it.flags() & QGraphicsItem.ItemIgnoresTransformations)
        ]

    def redo(self) -> None:
        self._bg.setPixmap(self._new_pixmap)
        self._bg.setPos(0, 0)
        for it in self._items:
            it.moveBy(-self._offset.x(), -self._offset.y())
        self._scene.setSceneRect(self._new_scene_rect)

    def undo(self) -> None:
        self._bg.setPixmap(self._old_pixmap)
        self._bg.setPos(0, 0)
        for it in self._items:
            it.moveBy(self._offset.x(), self._offset.y())
        self._scene.setSceneRect(self._old_scene_rect)
