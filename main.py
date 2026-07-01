"""Điểm khởi động SnagTin.

Chạy:  python main.py
App nằm ở khay hệ thống (system tray). Phím tắt mặc định:
    Ctrl+Shift+A : chụp vùng chọn
    Ctrl+Shift+F : chụp toàn màn hình
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app import APP_NAME
from app.app_controller import AppController


def main() -> int:
    # Đặt AppUserModelID để taskbar Windows dùng icon app thay vì python.exe.
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "snapzhot.app")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    from app.common.assets import app_icon
    app.setWindowIcon(app_icon())
    # Không thoát khi đóng cửa sổ cuối - app sống ở khay hệ thống.
    app.setQuitOnLastWindowClosed(False)

    from PySide6.QtWidgets import QSystemTrayIcon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, APP_NAME,
                            "Không tìm thấy khay hệ thống. App vẫn chạy được "
                            "nhưng bạn cần mở cửa sổ thủ công.")

    controller = AppController()
    controller.install_global_hotkeys()
    controller.show_library()  # mở thư viện lần đầu cho dễ thấy

    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
