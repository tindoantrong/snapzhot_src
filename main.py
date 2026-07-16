"""Điểm khởi động SnagTin.

Chạy:  python main.py
App nằm ở khay hệ thống (system tray). Phím tắt mặc định:
    Ctrl+Shift+A : chụp vùng chọn
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

    # Tạo mutex để installer nhận biết app đang chạy.
    # Phải trùng khít với AppMutex= trong installer/SnagTin.iss.
    # Dùng namespace Global\ để installer (chạy với quyền admin) cũng thấy được
    # mutex tạo bởi tiến trình user thường (Local namespace).
    if sys.platform == "win32":
        import ctypes
        _INSTALLER_MUTEX_NAME = "Global\\SnagTinAppMutex"
        try:
            _h_mutex = ctypes.windll.kernel32.CreateMutexW(None, False,
                                                            _INSTALLER_MUTEX_NAME)
            app._installer_mutex = _h_mutex  # giữ handle suốt vòng đời process
        except Exception:
            pass

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
