"""Cửa sổ thư viện: lưới thumbnail các ảnh đã chụp, tìm kiếm, tag, mở editor, xoá."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from ..common import theme
from ..common.update_banner import UpdateBanner
from ..editor.tool_icons import tool_icon
from .library_manager import THUMB_SIZE, Capture, LibraryManager

# Stylesheet Thư viện dạng TEMPLATE, dùng chung bảng token với Editor nên hai
# cửa sổ luôn cùng một theme (xem app/common/theme.py).
LIBRARY_QSS_TPL = """
QMainWindow, QMainWindow > QWidget { background: $bg; }
QToolBar {
    background: $surface;
    border: none;
    padding: 4px;
    spacing: 4px;
}
QToolButton {
    color: $text;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
}
QToolButton:hover {
    background: $elevated;
    border: 1px solid $border;
}
QToolButton:checked {
    background: $accent_fill;
    color: $on_accent;
    border: 1px solid $accent;
}
QToolButton:pressed { background: $accent_pressed; }
QLineEdit {
    background: $elevated;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 6px 10px;
}
QLineEdit:focus { border: 1px solid $accent; }
QPushButton {
    background: $elevated;
    color: $text;
    border: 1px solid $border;
    border-radius: 5px;
    padding: 6px 12px;
}
QPushButton:hover { background: $elevated_hi; }
QPushButton:pressed { background: $pressed; }
QListWidget { background: $bg; border: none; }
QListWidget::item {
    color: $text;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item:selected { background: $accent_fill; color: $on_accent; }
QListWidget::item:hover { background: $elevated; border: 1px solid $border; }
QLabel { color: $text_dim; }
#captureBar { background: $surface; }
#emptyState { background: $void; border-radius: 8px; }
#emptyTitle { color: $text; font-size: 19px; font-weight: bold; }
#emptySub { color: $text_muted; font-size: 13px; }
#emptyState QPushButton {
    background: $accent_fill;
    color: $on_accent;
    border: none;
    border-radius: 6px;
    padding: 9px 16px;
    font-size: 13px;
}
#emptyState QPushButton:hover { background: $accent_fill_hover; }
#emptyState QPushButton:pressed { background: $accent_pressed; }
#emptyState QPushButton#secondary { background: $elevated; border: 1px solid $border; }
#emptyState QPushButton#secondary:hover { background: $elevated_hi; }
"""


class LibraryWindow(QMainWindow):
    # Phát id của capture khi người dùng muốn mở trong editor.
    open_in_editor = Signal(int)
    # Các yêu cầu chụp/quay phát lên controller xử lý.
    request_capture_region = Signal()
    request_capture_fullscreen = Signal()
    request_video = Signal()

    def __init__(self, library: LibraryManager) -> None:
        super().__init__()
        self.library = library
        self.setWindowTitle(f"{APP_NAME} - Thư viện")
        self.resize(840, 600)

        self._build_capture_toolbar()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Banner cập nhật (ẩn mặc định, controller sẽ hiện khi có bản mới).
        self.update_banner = UpdateBanner()
        root.addWidget(self.update_banner)

        # Thanh trên: tìm kiếm + nút làm mới.
        top = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Tìm theo tên hoặc tag...")
        self.search_box.addAction(tool_icon("search"), QLineEdit.LeadingPosition)
        self.search_box.textChanged.connect(self.refresh)
        refresh_btn = QPushButton("Làm mới")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.search_box, 1)
        top.addWidget(refresh_btn)
        root.addLayout(top)

        # Lưới thumbnail.
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setSpacing(12)
        self.list.setMovement(QListWidget.Static)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self._open_selected)
        root.addWidget(self.list, 1)

        # Trạng thái rỗng chuyên nghiệp (mirror empty-state của Editor).
        self.empty_state = QWidget()
        self.empty_state.setObjectName("emptyState")
        es = QVBoxLayout(self.empty_state)
        es.setAlignment(Qt.AlignCenter)
        es.setSpacing(12)
        title = QLabel("Thư viện đang trống")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel(
            "Chụp ảnh hoặc quay video để bắt đầu.\n"
            "Phím tắt: Ctrl+Shift+A (vùng) · Ctrl+Shift+R (quay)."
        )
        sub.setObjectName("emptySub")
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignCenter)
        es.addWidget(title)
        es.addWidget(sub)
        cta = QHBoxLayout()
        cta.setAlignment(Qt.AlignCenter)
        cta.setSpacing(10)
        for text, icon_name, signal, obj in (
            ("Chụp vùng", "capture_region", self.request_capture_region, None),
            ("Chụp toàn màn hình", "capture_full", self.request_capture_fullscreen, None),
            ("Quay video", "video", self.request_video, "secondary"),
        ):
            btn = QPushButton(tool_icon(icon_name), text)
            if obj:
                btn.setObjectName(obj)
            btn.clicked.connect(signal.emit)
            cta.addWidget(btn)
        es.addLayout(cta)
        root.addWidget(self.empty_state, 1)

        # Thanh dưới: thao tác.
        bottom = QHBoxLayout()
        for text, slot in (
            ("Mở trong Editor", self._open_selected),
            ("Sửa tag", self._edit_tags),
            ("Xoá", self._delete_selected),
            ("Xoá toàn bộ", self._delete_all),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bottom.addWidget(b)
        bottom.addStretch(1)
        self.count_label = QLabel()
        bottom.addWidget(self.count_label)
        root.addLayout(bottom)

        # Áp theme tập trung sau khi đã dựng widget; theo dõi để đổi nóng.
        self._apply_theme()
        theme.manager.changed.connect(self._on_theme_changed)

        self.refresh()

    def _build_capture_toolbar(self) -> None:
        """Thanh nút chụp/quay nổi bật ở trên cùng cửa sổ."""
        tb = QToolBar("Chụp & Quay")
        tb.setObjectName("captureBar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.TopToolBarArea, tb)
        for text, icon_name, signal in (
            ("Chụp vùng", "capture_region", self.request_capture_region),
            ("Chụp toàn màn hình", "capture_full", self.request_capture_fullscreen),
            ("Quay video", "video", self.request_video),
        ):
            act = QAction(tool_icon(icon_name), text, self)
            act.triggered.connect(signal.emit)
            tb.addAction(act)

    def _apply_theme(self) -> None:
        """Dựng lại stylesheet theo theme đang dùng."""
        self.setStyleSheet(theme.qss(LIBRARY_QSS_TPL))

    def _on_theme_changed(self, _mode: str) -> None:
        self._apply_theme()
        self.update()

    def refresh(self) -> None:
        """Dựng lại toàn bộ lưới. Tốn ~1ms/ảnh (mỗi thẻ đọc 1 thumbnail từ đĩa)
        nên chỉ dùng khi nội dung đổi nhiều; xoá 1 mục thì dùng
        `remove_capture_row()`."""
        self.list.clear()
        for cap in self.library.list_captures(self.search_box.text().strip()):
            self.list.addItem(self._make_item(cap))
        self._sync_counts()

    def remove_capture_row(self, capture_id: int) -> bool:
        """Gỡ đúng một thẻ khỏi lưới, không dựng lại cả lưới. True nếu có gỡ."""
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == capture_id:
                self.list.takeItem(i)
                self._sync_counts()
                return True
        return False

    def _sync_counts(self) -> None:
        """Cập nhật nhãn đếm + trạng thái rỗng theo DB (query, không đọc ảnh)."""
        captures = self.library.list_captures(self.search_box.text().strip())
        n_img = sum(1 for c in captures if not c.is_video)
        n_vid = len(captures) - n_img
        self.count_label.setText(f"{n_img} ảnh · {n_vid} video")
        empty = len(captures) == 0
        self.empty_state.setVisible(empty)
        self.list.setVisible(not empty)

    def _make_item(self, cap: Capture) -> QListWidgetItem:
        pix = QPixmap(str(cap.thumbnail_path))
        if pix.isNull() and not cap.is_video:
            pix = QPixmap(str(cap.path)).scaled(
                THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        if cap.is_video:
            pix = self._add_play_badge(pix)
        label = cap.created_at.replace("T", " ")
        if cap.is_video:
            label = f"{self._fmt_duration(cap.duration)}  " + label
        if cap.tag_list():
            label += "\n# " + ", ".join(cap.tag_list())
        item = QListWidgetItem(QIcon(pix), label)
        item.setData(Qt.UserRole, cap.id)
        item.setSizeHint(QSize(THUMB_SIZE + 20, THUMB_SIZE + 48))
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        return item

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _add_play_badge(self, pix: QPixmap) -> QPixmap:
        """Vẽ tam giác play lên thumbnail video (nếu thiếu thì nền đen)."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPainter, QPolygonF

        if pix.isNull():
            pix = QPixmap(THUMB_SIZE, THUMB_SIZE)
            pix.fill(QColor("#222222"))
        canvas = QPixmap(pix)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        cx, cy = canvas.width() / 2, canvas.height() / 2
        r = min(canvas.width(), canvas.height()) * 0.18
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r, r)
        tri = QPolygonF([
            QPointF(cx - r * 0.4, cy - r * 0.55),
            QPointF(cx - r * 0.4, cy + r * 0.55),
            QPointF(cx + r * 0.6, cy),
        ])
        painter.setBrush(QColor("white"))
        painter.drawPolygon(tri)
        painter.end()
        return canvas

    def _selected_id(self) -> int | None:
        items = self.list.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _selected_ids(self) -> list[int]:
        return [it.data(Qt.UserRole) for it in self.list.selectedItems()]

    def keyPressEvent(self, event) -> None:
        # Ctrl+C: copy ảnh đang chọn vào clipboard.
        if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            self._copy_selected_image()
            return
        # Phím Delete xoá các mục đang chọn (qua hộp thoại xác nhận).
        if event.key() == Qt.Key_Delete and self.list.selectedItems():
            self._delete_selected()
            return
        super().keyPressEvent(event)

    def _copy_selected_image(self) -> None:
        """Copy ảnh đang chọn vào clipboard hệ thống."""
        from PySide6.QtWidgets import QApplication

        cid = self._selected_id()
        if cid is None:
            return
        cap = self.library.get(cid)
        if cap is None or cap.is_video:
            return
        image = QPixmap(cap.path)
        if image.isNull():
            return
        QApplication.clipboard().setPixmap(image)

    def _open_selected(self, *_) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        cap = self.library.get(cid)
        if cap is None:
            return
        if cap.is_video:
            self._play_video(cap.path)
        else:
            self.open_in_editor.emit(cid)

    def _play_video(self, path: str) -> None:
        """Phát video bằng trình phát nhúng (QtMultimedia).

        Nếu thiếu backend QtMultimedia thì fallback sang trình phát ngoài.
        """
        try:
            from .video_player import VideoPlayerWindow
        except Exception:
            self._play_video_external(path)
            return

        # Giữ một instance tái dùng để tránh rò rỉ nhiều cửa sổ.
        if getattr(self, "_video_player", None) is None:
            self._video_player = VideoPlayerWindow()
        self._video_player.open(path)

    def _play_video_external(self, path: str) -> None:
        """Mở video bằng trình phát mặc định của hệ điều hành (fallback)."""
        import os
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as exc:
            QMessageBox.warning(self, "Không mở được video", str(exc))

    def _edit_tags(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        cap = self.library.get(cid)
        if cap is None:
            return
        text, ok = QInputDialog.getText(
            self, "Sửa tag", "Các tag (cách nhau bằng dấu phẩy):", text=cap.tags
        )
        if ok:
            self.library.set_tags(cid, text)
            self.refresh()

    def _delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        msg = "Xoá mục này khỏi thư viện?" if len(ids) == 1 \
            else f"Xoá {len(ids)} mục đã chọn khỏi thư viện?"
        if QMessageBox.question(self, "Xoá", msg,
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            for cid in ids:
                self.library.delete(cid)
            self.refresh()

    def _delete_all(self) -> None:
        ids = [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]
        if not ids:
            return
        if QMessageBox.question(self, "Xoá toàn bộ",
                                f"Xoá toàn bộ {len(ids)} mục đang hiển thị khỏi thư viện?",
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            for cid in ids:
                self.library.delete(cid)
            self.refresh()
