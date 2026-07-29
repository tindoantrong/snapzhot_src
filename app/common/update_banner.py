"""Banner thông báo có phiên bản mới, nhúng vào đầu cửa sổ Library / Editor.

Widget tự ẩn khi chưa có update. Khi controller gọi ``show_update(info)``
với ``info.available=True``, banner hiện lên với nút "Cập nhật ngay".
Nhấn nút → tải installer ở luồng nền → chạy installer → thoát app.
"""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)

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
#updateBanner QProgressBar {
    background: #1E1F22;
    border: 1px solid #3A3D42;
    border-radius: 3px;
    text-align: center;
    color: #C8C8C8;
    font-size: 10px;
    max-height: 14px;
}
#updateBanner QProgressBar::chunk { background: #1E90FF; border-radius: 2px; }
"""


class _BannerDownloadWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    @Slot()
    def run(self) -> None:
        try:
            path = updater.download_update(
                self._url,
                progress_cb=lambda dl, total: self.progress.emit(dl, total),
            )
            self.finished.emit(path)
        except Exception as exc:
            self.error.emit(str(exc) or "Lỗi không xác định khi tải cập nhật.")


class UpdateBanner(QWidget):
    """Banner nằm ngang ở đầu cửa sổ, thông báo có version mới."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.setStyleSheet(_BANNER_QSS)
        self._download_url = ""
        self._downloaded_path = ""
        self._dl_thread: QThread | None = None

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

        self._progress = QProgressBar()
        self._progress.setFixedWidth(160)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._action_btn = QPushButton("Cập nhật ngay")
        self._action_btn.clicked.connect(self._on_action)
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
        self._download_url = info.url
        self._downloaded_path = ""
        self._msg.setText(
            f"Phiên bản mới {info.latest} đã sẵn sàng!"
        )
        self._action_btn.setText("Cập nhật ngay")
        self._action_btn.setEnabled(updater.is_safe_update_url(info.url))
        self._progress.hide()
        self._dismiss_btn.show()
        self.show()

    def _on_action(self) -> None:
        if self._downloaded_path:
            self._run_installer()
            return
        if not self._download_url:
            return
        if not updater.is_safe_update_url(self._download_url):
            QMessageBox.warning(
                self, "URL không hợp lệ",
                "URL cập nhật không an toàn, đã bị chặn.",
            )
            return
        self._start_download()

    def _start_download(self) -> None:
        if self._dl_thread is not None:
            return
        self._action_btn.setEnabled(False)
        self._action_btn.setText("Đang tải…")
        self._dismiss_btn.hide()
        self._progress.setRange(0, 0)
        self._progress.show()

        thread = QThread(self)
        worker = _BannerDownloadWorker(self._download_url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_thread)
        self._dl_thread = thread
        thread.start()

    @Slot(int, int)
    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(downloaded)
            mb = downloaded / (1024 * 1024)
            mb_t = total / (1024 * 1024)
            self._msg.setText(f"Đang tải cập nhật… {mb:.1f}/{mb_t:.1f} MB")
        else:
            self._progress.setRange(0, 0)

    @Slot(str)
    def _on_finished(self, path: str) -> None:
        self._downloaded_path = path
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._msg.setText("Tải xong! Đang mở trình cài đặt…")
        self._action_btn.setText("Cài đặt")
        self._action_btn.setEnabled(True)
        # Auto-install after short delay.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self._run_installer)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._msg.setText(f"Lỗi tải cập nhật: {msg}")
        self._action_btn.setText("Thử lại")
        self._action_btn.setEnabled(True)
        self._dismiss_btn.show()
        self._progress.hide()
        self._downloaded_path = ""

    def _clear_thread(self) -> None:
        self._dl_thread = None

    def _run_installer(self) -> None:
        path = self._downloaded_path
        if not path or not os.path.isfile(path):
            self._msg.setText("Không tìm thấy file cài đặt.")
            return
        try:
            subprocess.Popen(
                [path],
                creationflags=subprocess.DETACHED_PROCESS,
            )
        except OSError as exc:
            QMessageBox.warning(self, "Lỗi", f"Không thể chạy trình cài đặt:\n{exc}")
            return
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.quit()
