"""Banner thông báo có phiên bản mới, nhúng vào đầu cửa sổ Library / Editor.

Widget tự ẩn khi chưa có update. Khi controller gọi ``show_update(info)``
với ``info.available=True``, banner hiện lên với nút "Cập nhật ngay".
Nhấn nút → phát ``update_requested`` → controller mở hộp thoại "Kiểm tra cập
nhật" (tải + cài đặt chỉ làm ở đó, không tải thẳng trên banner).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from .. import updater

_BANNER_QSS = """
#updateBanner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1A3A5C, stop:1 #1E4D7A);
    border-bottom: 1px solid #1E90FF;
    padding: 6px 12px;
}
#updateBanner QLabel {
    color: #E8E8E8;
    font-size: 12px;
}
#updateBanner #bannerMsg {
    color: #FFFFFF;
    font-size: 13px;
}
#updateBanner QPushButton {
    background: #1E90FF;
    color: #FFFFFF;
    border: none;
    border-radius: 5px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: bold;
}
#updateBanner QPushButton:hover { background: #3AA0FF; }
#updateBanner QPushButton:pressed { background: #187BDD; }
#updateBanner QPushButton:disabled { background: #2F3136; color: #7A7D82; }
#updateBanner QPushButton#dismissBtn {
    background: transparent;
    color: #9AA0A6;
    padding: 2px 6px;
    font-size: 14px;
    font-weight: normal;
}
#updateBanner QPushButton#dismissBtn:hover { color: #FFFFFF; }
"""


class UpdateBanner(QWidget):
    """Banner nằm ngang ở đầu cửa sổ, thông báo có version mới."""

    update_requested = Signal()  # nhấn "Cập nhật ngay" → mở hộp thoại cập nhật

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.setStyleSheet(_BANNER_QSS)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self._icon_label = QLabel("🔄")
        self._icon_label.setFixedWidth(20)
        layout.addWidget(self._icon_label)

        self._msg = QLabel("")
        self._msg.setObjectName("bannerMsg")
        self._msg.setWordWrap(False)
        layout.addWidget(self._msg, 1)

        self._action_btn = QPushButton("Cập nhật ngay")
        self._action_btn.clicked.connect(self.update_requested.emit)
        layout.addWidget(self._action_btn)

        self._dismiss_btn = QPushButton("✕")
        self._dismiss_btn.setObjectName("dismissBtn")
        self._dismiss_btn.setFixedSize(24, 24)
        self._dismiss_btn.setToolTip("Bỏ qua")
        self._dismiss_btn.clicked.connect(self.hide)
        layout.addWidget(self._dismiss_btn)

        self.hide()

    def show_update(self, info: updater.UpdateInfo) -> None:
        """Hiện banner nếu có bản mới, ẩn nếu không."""
        if not info.available:
            self.hide()
            return
        self._msg.setText(
            f"Phiên bản mới {info.latest} đã sẵn sàng!"
        )
        self._dismiss_btn.show()
        self.show()
