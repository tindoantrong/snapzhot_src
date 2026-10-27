"""QC — nút "Cập nhật ngay" trên banner Thư viện/Editor mở hộp thoại cập nhật
(không tải thẳng trên banner). Offscreen, không gọi mạng.

1. Bấm nút banner Thư viện → mở _UpdateDialog, đang "Đang kiểm tra…", gọi check.
2. Kết quả về → hộp thoại hiện bản mới + nút "Tải về"; banner không có thanh tải.
3. Bấm lại (banner Editor) khi hộp thoại đang mở → chỉ đưa lên, không mở cái mới.
4. Hộp thoại mở lúc auto-check đang chạy → kết quả auto-check vẫn tới hộp thoại.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QProgressBar

app = QApplication([])

from app import updater
from app.app_controller import AppController

c = AppController()
checks = []
c._start_update_check = lambda: checks.append(1)
c._auto_check_for_updates = lambda: None
c.tray.showMessage = lambda *a, **k: None

info = updater.UpdateInfo(
    available=True, current="0.1.41", latest="0.1.42",
    url="https://github.com/tindoantrong/snapzhot_src/releases/latest/download/x.exe",
    notes="ghi chú",
)
c.library_window.update_banner.show_update(info)
assert not c.library_window.update_banner.findChildren(QProgressBar), \
    "banner không còn thanh tải"

# 1
c.library_window.update_banner._action_btn.click()
dlg = c._update_dialog
assert dlg is not None and dlg.isVisible(), "phải mở hộp thoại cập nhật"
assert dlg._mode == "checking" and checks == [1]
print("OK 1: bấm banner -> mở hộp thoại + kiểm tra")

# 2
c._on_update_checked(info)
assert dlg._mode == "available" and dlg.action_btn.isEnabled()
assert dlg._dl_thread is None, "chưa được tự tải khi chưa bấm 'Tải về'"
print("OK 2: hộp thoại hiện bản mới:", dlg.action_btn.text())

# 3
c.editor.update_banner.show_update(info)
c.editor.update_banner._action_btn.click()
assert c._update_dialog is dlg and checks == [1], "không mở/kiểm tra thêm"
print("OK 3: bấm lại khi đang mở -> chỉ đưa lên")

# 4
dlg.close()
app.processEvents()
assert c._update_dialog is None
c._update_thread = object()          # giả: auto-check đang chạy
c._start_update_check = AppController._start_update_check.__get__(c)
c.library_window.update_banner._action_btn.click()
dlg2 = c._update_dialog
assert dlg2._mode == "checking"
c._update_thread = None
c._on_auto_check_result(info)
assert dlg2._mode == "available", dlg2._mode
print("OK 4: auto-check đang chạy -> kết quả vẫn tới hộp thoại")
print("=== BANNER -> UPDATE DIALOG OK ===")
