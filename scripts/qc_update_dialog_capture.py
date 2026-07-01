"""QC UPD2 — eyes-test hộp thoại cập nhật (`_UpdateDialog`) offscreen + GRAB PNG.

KHÔNG cần mạng: monkeypatch `updater.check_for_updates` qua holder. Grab ảnh mỗi
trạng thái vào .ai-workspace/screens/upd_*.png, sample pixel kiểm theme tối, và
xác nhận luồng bất đồng bộ (AppController + QThread) không gọi check trên GUI.
"""
import os
import sys
import time
import types

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices
from PySide6.QtWidgets import QApplication

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)


# Mock keyboard để AppController.__init__ chạy không cần lib/admin.
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

app = QApplication.instance() or QApplication([])

# Nạp font Windows để chữ Việt không tofu (artifact offscreen).
_fam = None
for _f in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
    if os.path.exists(_f):
        fams = QFontDatabase.applicationFontFamilies(
            QFontDatabase.addApplicationFont(_f))
        if fams and _fam is None:
            _fam = fams[0]
if _fam:
    app.setFont(QFont(_fam, 10))

from app import __version__, updater
from app.app_controller import AppController, _UpdateDialog

LOG = []


def _info(**kw):
    base = dict(available=False, current=__version__, latest="", url="",
                notes="", error=None)
    base.update(kw)
    return updater.UpdateInfo(**base)


def grab(dlg, name):
    dlg.resize(dlg.sizeHint())
    dlg.show()
    app.processEvents()
    dlg.grab().save(os.path.join(OUT, name))
    return dlg.grab().toImage()


def sample_bg(img):
    """Vài điểm nền (trên QLabel trong suốt → trả nền QDialog)."""
    w, h = img.width(), img.height()
    pts = [(w - 12, 14), (12, 60), (w - 12, 60)]
    return [img.pixelColor(x, y).name() for x, y in pts]


# ===== PART A: 6 trạng thái dialog (standalone) =====
print("# PART A — trạng thái dialog")

# 1. Idle
d = _UpdateDialog(__version__)
img = grab(d, "upd_01_idle.png")
bg = sample_bg(img)
assert d.status.text() == f"Phiên bản hiện tại: {__version__}", d.status.text()
assert d.action_btn.text() == "Kiểm tra cập nhật" and d.action_btn.isEnabled()
LOG.append(("idle", "Phiên bản hiện tại + nút Kiểm tra cập nhật", bg))
print(f"  upd_01_idle: status={d.status.text()!r} bg={bg}")

# 2. Đang kiểm tra
d.show_checking()
grab(d, "upd_02_checking.png")
assert d.action_btn.isEnabled() is False, "đang kiểm tra phải disable nút"
assert "kiểm tra" in d.status.text().lower()
LOG.append(("checking", "nút disable + 'Đang kiểm tra…'", None))
print(f"  upd_02_checking: status={d.status.text()!r} btn_enabled={d.action_btn.isEnabled()}")

# 3. Có bản mới (+ notes + Tải về)
d.show_result(_info(available=True, latest="1.5.0", url="https://example.com/dl",
                    notes="• Sửa lỗi callout\n• Thêm cập nhật tự động"))
img = grab(d, "upd_03_available.png")
# sample nút primary "Tải về"
from PySide6.QtCore import QPoint
# Sample LỆCH khỏi chữ (padding ngang 16px) → vùng fill xanh thuần, tránh blend chữ trắng.
br = d.action_btn.rect()
gp = d.action_btn.mapTo(d, QPoint(6, br.height() // 2))
btn_color = img.pixelColor(gp.x(), gp.y()).name()
assert d.action_btn.text() == "Tải về" and d.action_btn.isEnabled()
assert d.notes.isVisibleTo(d) and "callout" in d.notes.toPlainText()
assert "1.5.0" in d.status.text()
LOG.append(("available", f"latest 1.5.0 + notes + Tải về (nút={btn_color})", None))
print(f"  upd_03_available: btn={d.action_btn.text()!r} primary_pixel={btn_color} notes_shown={d.notes.isVisibleTo(d)}")

# 3b. Có bản mới nhưng URL rỗng → disable + tooltip + nút hóa XÁM (UPD3)
d.show_result(_info(available=True, latest="1.5.0", url="", notes=""))
img = grab(d, "upd_04_available_no_url.png")
br = d.action_btn.rect()
gp = d.action_btn.mapTo(d, QPoint(6, br.height() // 2))
dis_color = img.pixelColor(gp.x(), gp.y()).name()
assert d.action_btn.text() == "Tải về" and d.action_btn.isEnabled() is False
assert d.action_btn.toolTip() == "Manifest không có liên kết tải về.", d.action_btn.toolTip()
assert dis_color == "#2f3136", f"nút primary disabled phải hóa xám #2f3136, gặp {dis_color}"
LOG.append(("available_no_url", f"Tải về disable + tooltip + xám {dis_color}", None))
print(f"  upd_04_no_url: btn_enabled={d.action_btn.isEnabled()} disabled_pixel={dis_color} tooltip={d.action_btn.toolTip()!r}")

# 4. Đã mới nhất
d.show_result(_info(available=False, latest=__version__))
grab(d, "upd_05_latest.png")
assert d._mode == "latest" and "mới nhất" in d.status.text().lower()
assert d.action_btn.text() == "Kiểm tra lại"
LOG.append(("latest", "Bạn đang dùng phiên bản mới nhất + Kiểm tra lại", None))
print(f"  upd_05_latest: status={d.status.text()!r} btn={d.action_btn.text()!r}")

# 5. Lỗi mạng
d.show_result(_info(error="Không kết nối được tới máy chủ cập nhật. Vui lòng kiểm tra mạng."))
grab(d, "upd_06_error.png")
assert d._mode == "error" and d.action_btn.text() == "Thử lại"
assert "Không kết nối" in d.status.text()
LOG.append(("error", "thông điệp tiếng Việt + Thử lại", None))
print(f"  upd_06_error: status={d.status.text()!r} btn={d.action_btn.text()!r}")

# Theme: nền #2b2d31 + nút primary #1e90ff
all_bg = sample_bg(grab(d, "upd_06_error.png"))
assert all(c == "#2b2d31" for c in all_bg), f"nền phải #2b2d31, gặp {all_bg}"
assert btn_color == "#1e90ff", f"nút primary phải #1e90ff, gặp {btn_color}"
print(f"  THEME: bg={all_bg} primary={btn_color}")
d.close()

# 6. Nút "Tải về" gọi QDesktopServices.openUrl đúng URL
opened = {}
_orig = QDesktopServices.openUrl
QDesktopServices.openUrl = lambda u: opened.setdefault("url", u.toString()) or True
try:
    d2 = _UpdateDialog(__version__)
    d2.show_result(_info(available=True, latest="2.0.0", url="https://example.com/get", notes=""))
    d2.action_btn.click()
    d2.close()
finally:
    QDesktopServices.openUrl = _orig
assert opened.get("url") == "https://example.com/get", opened
print(f"  OK Tải về → openUrl({opened['url']})")


# ===== PART B: luồng bất đồng bộ qua AppController =====
print("# PART B — luồng nền (không đơ GUI)")
ctrl = AppController()

_fake = {}
# CỐ ĐỊNH (không restore giữa ca) tránh race với worker luồng nền.
updater.check_for_updates = lambda current, url, timeout=8.0: _fake["info"]

# verify check_for_updates KHÔNG bị gọi trực tiếp trên GUI: dùng cờ thread.
_called_from = {}
_base_check = lambda current, url, timeout=8.0: _fake["info"]


def _tracking_check(current, url, timeout=8.0):
    import threading
    _called_from["thread"] = threading.current_thread().name
    return _fake["info"]


updater.check_for_updates = _tracking_check


def run_async(info):
    _fake["info"] = info
    ctrl._open_update_dialog()
    dd = ctrl._update_dialog
    dd.action_btn.click()  # idle→checking + phát check_requested→_start_update_check (QThread)
    assert dd._mode == "checking", "bấm nút phải sang 'đang kiểm tra' NGAY (GUI không đơ)"
    deadline = time.time() + 5
    while dd._mode == "checking" and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    return dd

import threading
_main = threading.current_thread().name

dd = run_async(_info(available=True, latest="3.1.0", url="https://example.com/v3", notes="Bản lớn"))
assert dd._mode == "available" and dd.action_btn.text() == "Tải về"
assert _called_from.get("thread") and _called_from["thread"] != _main, \
    f"check_for_updates phải chạy LUỒNG NỀN (got {_called_from.get('thread')} vs main {_main})"
print(f"  OK async (có bản mới) — check chạy thread={_called_from['thread']!r} (main={_main!r})")
ctrl._update_dialog.close(); app.processEvents()
assert ctrl._update_dialog is None, "đóng dialog → clear ref"

dd = run_async(_info(available=False, latest=__version__))
assert dd._mode == "latest"
print("  OK async (đã mới nhất)")
ctrl._update_dialog.close(); app.processEvents()

dd = run_async(_info(error="Dữ liệu cập nhật không hợp lệ."))
assert dd._mode == "error"
print("  OK async (lỗi)")
ctrl._update_dialog.close(); app.processEvents()

# Tray menu: nhãn version (disabled) + mục "Kiểm tra cập nhật…"
acts = ctrl.tray.contextMenu().actions()
ver_act = next((a for a in acts if __version__ in a.text()), None)
upd_act = next((a for a in acts if "Kiểm tra cập nhật" in a.text()), None)
assert ver_act is not None and ver_act.isEnabled() is False, "nhãn version phải disabled"
assert upd_act is not None and upd_act.isEnabled(), "mục Kiểm tra cập nhật phải có + enabled"
print(f"  TRAY: version_label={ver_act.text()!r} (disabled) + {upd_act.text()!r}")

ctrl.shutdown()
print("=== UPDATE DIALOG QC OK ===")
