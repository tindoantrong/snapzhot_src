"""Kiểm wiring hộp thoại cập nhật (UPD2) — offscreen, không cần mạng.

Test trực tiếp `_UpdateDialog` qua 5 trạng thái + nút "Tải về" mở URL, và luồng
nền của AppController (`_start_update_check`) qua monkeypatch
`updater.check_for_updates` (giả lập có-bản-mới / mới-nhất / lỗi).
"""
import os
import sys
import types

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# Mock `keyboard` để AppController.__init__ không phụ thuộc lib/quyền admin.
class _FakeKeyboard(types.ModuleType):
    def __init__(self):
        super().__init__("keyboard")

    def add_hotkey(self, *a, **k):
        return ("h", 1)

    def remove_hotkey(self, *a, **k):
        pass

    def remove_all_hotkeys(self, *a, **k):
        pass


sys.modules["keyboard"] = _FakeKeyboard()

from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from app import __version__, updater
from app.app_controller import AppController, _UpdateDialog


def _info(**kw):
    base = dict(available=False, current=__version__, latest="", url="", notes="", error=None)
    base.update(kw)
    return updater.UpdateInfo(**base)


# ---------- 1. _UpdateDialog: 5 trạng thái ----------
dlg = _UpdateDialog(__version__)
assert dlg._mode == "idle", "khởi tạo phải ở idle"
assert __version__ in dlg.status.text(), "idle hiện version hiện tại"
assert dlg.action_btn.isEnabled() and dlg.action_btn.text() == "Kiểm tra cập nhật"
print("OK: idle")

dlg.show_checking()
assert dlg._mode == "checking"
assert dlg.action_btn.isEnabled() is False, "đang kiểm tra phải disable nút"
assert "kiểm tra" in dlg.status.text().lower()
print("OK: đang kiểm tra")

dlg.show_result(_info(available=True, latest="9.9.9", url="https://dl/x", notes="Ghi chú"))
assert dlg._mode == "available"
assert "9.9.9" in dlg.status.text()
assert dlg.notes.isVisibleTo(dlg) and dlg.notes.toPlainText() == "Ghi chú"
assert dlg.action_btn.text() == "Tải về" and dlg.action_btn.isEnabled()
assert dlg._download_url == "https://dl/x"
print("OK: có bản mới (notes + Tải về)")

# url rỗng -> nút Tải về disable
dlg.show_result(_info(available=True, latest="9.9.9", url="", notes=""))
assert dlg.action_btn.text() == "Tải về" and dlg.action_btn.isEnabled() is False
assert dlg.action_btn.toolTip(), "phải có tooltip giải thích thiếu URL"
print("OK: có bản mới nhưng thiếu URL -> disable")

dlg.show_result(_info(available=False, latest=__version__))
assert dlg._mode == "latest"
assert "mới nhất" in dlg.status.text().lower()
print("OK: đã mới nhất")

dlg.show_result(_info(error="Không kết nối được tới máy chủ cập nhật."))
assert dlg._mode == "error"
assert dlg.status.text() == "Không kết nối được tới máy chủ cập nhật."
assert dlg.action_btn.text() == "Thử lại" and dlg.action_btn.isEnabled()
print("OK: lỗi -> Thử lại")

# Nút "Tải về" gọi QDesktopServices.openUrl
opened = {}
_orig_open = QDesktopServices.openUrl
QDesktopServices.openUrl = lambda url: opened.setdefault("url", url.toString()) or True
try:
    dlg.show_result(_info(available=True, latest="9.9.9", url="https://dl/y", notes=""))
    dlg.action_btn.click()  # _on_action -> openUrl vì mode == available
finally:
    QDesktopServices.openUrl = _orig_open
assert opened.get("url") == "https://dl/y", "Tải về phải mở đúng URL"
print("OK: nút Tải về mở URL")

# check_requested phát khi bấm ở trạng thái idle/lỗi
fired = []
dlg.show_idle()
dlg.check_requested.connect(lambda: fired.append(True))
dlg.action_btn.click()
assert fired and dlg._mode == "checking", "idle bấm -> phát check + chuyển checking"
print("OK: check_requested wiring")
dlg.close()


# ---------- 2. AppController: luồng nền + cập nhật dialog ----------
ctrl = AppController()

# Patch CỐ ĐỊNH (không restore giữa các ca) để tránh race: worker chạy ở luồng nền,
# nếu khôi phục về hàm thật trước khi worker đọc attribute → gọi nhầm hàm mạng 8s.
import time

_fake = {}
updater.check_for_updates = lambda current, url, timeout=8.0: _fake["info"]


def _run_check(fake_info):
    """Đặt kết quả giả, mở dialog, bấm nút kiểm tra (đúng luồng thật:
    _on_action -> show_checking + check_requested -> _start_update_check luồng nền),
    chờ kết quả về GUI."""
    _fake["info"] = fake_info
    ctrl._open_update_dialog()
    d = ctrl._update_dialog
    assert d is not None, "dialog phải được giữ ref (tránh GC)"
    d.action_btn.click()  # idle -> checking + phát check_requested -> luồng nền
    assert d._mode == "checking", "bấm nút phải chuyển sang đang kiểm tra ngay (GUI không đơ)"
    deadline = time.time() + 5
    while d._mode == "checking" and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    return d


d = _run_check(_info(available=True, latest="2.0.0", url="https://dl/z", notes="Mới"))
assert d._mode == "available" and d.action_btn.text() == "Tải về", "luồng nền -> available"
ctrl._update_dialog.close()
app.processEvents()
assert ctrl._update_dialog is None, "đóng dialog -> clear ref"
print("OK: AppController luồng nền (có bản mới)")

d = _run_check(_info(available=False, latest=__version__))
assert d._mode == "latest"
ctrl._update_dialog.close()
app.processEvents()
print("OK: AppController luồng nền (đã mới nhất)")

d = _run_check(_info(error="Dữ liệu cập nhật không hợp lệ."))
assert d._mode == "error" and "Thử lại" == d.action_btn.text()
ctrl._update_dialog.close()
app.processEvents()
print("OK: AppController luồng nền (lỗi)")

# menu tray có action "Kiểm tra cập nhật…" và nhãn version
labels = [a.text() for a in ctrl.tray.contextMenu().actions()]
assert any("Kiểm tra cập nhật" in t for t in labels), "tray phải có 'Kiểm tra cập nhật…'"
assert any(__version__ in t for t in labels), "tray phải có nhãn version"
print("OK: tray menu có mục cập nhật + nhãn version")

ctrl.shutdown()
print("=== UPDATE DIALOG OK ===")
