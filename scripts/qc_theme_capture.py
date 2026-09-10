"""QC harness THEME: đổi giao diện sáng/tối toàn app.

Dựng EditorWindow + LibraryWindow THẬT offscreen; kiểm:
  - Nút Theme nằm bên PHẢI nút ô caro, cùng hàng tác vụ trên cùng.
  - Đang tối → icon mặt trời, tooltip "Chuyển sang giao diện sáng"; đang sáng
    → mặt trăng, "Chuyển sang giao diện tối".
  - Bấm một lần đổi ngay: stylesheet Editor + Thư viện + nền app đều đổi.
  - Icon line-art tự đảo màu (sáng trên nền tối, tối trên nền sáng).
  - Nền VÙNG ẢNH (nút ô caro) KHÔNG đổi theo theme.
  - Chữ ở cả hai theme đạt tương phản WCAG AA.
KHÔNG sửa app/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase

from app.common import theme
from app.editor.editor_window import EditorWindow
from app.editor.tool_icons import tool_icon
from app.library.library_manager import LibraryManager
from app.library.library_window import LibraryWindow
from launch_editor_demo import make_recent_thumbs, make_sample_image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
_fam = None
for _f in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
    if os.path.exists(_f):
        fams = QFontDatabase.applicationFontFamilies(
            QFontDatabase.addApplicationFont(_f))
        if fams and _fam is None:
            _fam = fams[0]
if _fam:
    app.setFont(QFont(_fam, 10))
theme.apply_to_app(app)

LOG = []


def pump(n=8):
    for _ in range(n):
        app.processEvents()


def shot(widget, name):
    pump()
    widget.grab().save(os.path.join(OUT, name))
    LOG.append(name)


def _lum(c: QColor) -> float:
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(QColor(a)), _lum(QColor(b))), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def icon_color(name="save", size=26) -> str:
    """Màu thực sự vẽ ra của icon line-art (pixel đậm nhất khác trong suốt)."""
    img = tool_icon(name, size=size).pixmap(QSize(size, size)).toImage()
    best, best_a = None, 0
    for y in range(size):
        for x in range(size):
            c = img.pixelColor(x, y)
            if c.alpha() > best_a:
                best, best_a = c, c.alpha()
    return best.name() if best else "?"


w = EditorWindow()
w.load_image(make_sample_image(1280, 800), capture_id=3)
_b = make_recent_thumbs()
w.set_recent_captures([dict(_b[i % len(_b)], id=i + 1) for i in range(12)])
w.resize(1280, 820)
w.show()

lib = LibraryWindow(LibraryManager())
lib.resize(900, 620)
lib.show()
pump()

print("=" * 68)
print("THEME: đổi giao diện sáng/tối toàn app")
print("=" * 68)

cap_tb = {t.objectName(): t for t in w.findChildren(QToolBar)}["captureBar"]
bg_btn = cap_tb.widgetForAction(w._bg_cycle_action)
th_btn = cap_tb.widgetForAction(w._theme_action)

# ---------- [1] Vị trí nút Theme ----------
print("\n[1] Vị trí nút Theme:")
bg_x = bg_btn.mapTo(w, bg_btn.rect().center()).x()
th_x = th_btn.mapTo(w, th_btn.rect().center()).x()
print(f"    ô caro x={bg_x} | theme x={th_x} → theme ở BÊN PHẢI ô caro = {th_x > bg_x}")
print(f"    cùng hàng (tâm y {bg_btn.mapTo(w, bg_btn.rect().center()).y()} == "
      f"{th_btn.mapTo(w, th_btn.rect().center()).y()}) = "
      f"{bg_btn.mapTo(w, bg_btn.rect().center()).y() == th_btn.mapTo(w, th_btn.rect().center()).y()}")
print(f"    cách mép phải cửa sổ {w.width() - th_btn.mapTo(w, th_btn.rect().topRight()).x()}px")

# ---------- [2] Trạng thái TỐI ----------
print("\n[2] Đang giao diện TỐI:")
print(f"    theme.mode={theme.mode()!r} | tooltip={w._theme_action.toolTip()!r}")
print(f"    nền cửa sổ={theme.color('bg')} chữ={theme.color('text')} "
      f"icon={icon_color()} (token {theme.color('icon')})")
canvas_dark = w.canvas.backgroundBrush().color().name().upper()
qss_dark = w.styleSheet()
shot(w, "theme_01_editor_dark.png")
shot(lib, "theme_02_library_dark.png")

# ---------- [3] Bấm một lần → SÁNG ----------
w._theme_action.trigger()
pump()
print("\n[3] Bấm nút Theme → giao diện SÁNG (không khởi động lại):")
print(f"    theme.mode={theme.mode()!r} | tooltip={w._theme_action.toolTip()!r}")
print(f"    nền cửa sổ={theme.color('bg')} chữ={theme.color('text')} "
      f"icon={icon_color()} (token {theme.color('icon')})")
print(f"    stylesheet Editor đổi = {w.styleSheet() != qss_dark}")
print(f"    stylesheet Thư viện có màu sáng = {theme.color('surface') in lib.styleSheet()}")
print(f"    stylesheet nền app (hộp thoại) đổi theo = "
      f"{theme.color('bg') in app.styleSheet()}")
canvas_light = w.canvas.backgroundBrush().color().name().upper()
print(f"    NỀN VÙNG ẢNH giữ nguyên {canvas_dark} → {canvas_light} = "
      f"{canvas_dark == canvas_light}")
shot(w, "theme_03_editor_light.png")
shot(lib, "theme_04_library_light.png")

# ---------- [4] Tương phản hai theme ----------
print("\n[4] Tương phản chữ/icon (WCAG AA >= 4.5):")
for m in ("dark", "light"):
    theme.manager.set_mode(m)
    pump(2)
    t = theme.manager.tokens()
    rows = [
        ("chữ trên nền cửa sổ", t["text"], t["bg"]),
        ("chữ trên toolbar", t["text"], t["surface"]),
        ("chữ mờ trên thanh trạng thái", t["text_dim"], t["surface_alt"]),
        ("chữ phụ trên nền cửa sổ", t["text_muted"], t["bg"]),
        ("icon trên toolbar", t["icon"], t["surface"]),
        ("chữ trên mảng nhấn (accent_fill)", t["on_accent"], t["accent_fill"]),
        ("viền nhấn trên nền cửa sổ (>=3:1)", t["accent"], t["bg"]),
    ]
    print(f"    [{m}]")
    for nhan, fg, bg in rows:
        r = contrast(fg, bg)
        nguong = 3.0 if ">=3:1" in nhan else 4.5
        flag = "OK " if r >= nguong else "THẤP"
        print(f"      {flag} {nhan}: {fg} / {bg} = {r:.2f}:1")

# ---------- [5] Cận cảnh 2 icon ----------
theme.manager.set_mode("dark")
pump()
from PySide6.QtGui import QPainter, QPixmap
prev = QPixmap(460, 120)
prev.fill(QColor(theme.color("surface")))
p = QPainter(prev)
p.setFont(QFont(_fam or "Arial", 10))
for i, (key, nhan) in enumerate((("bg_cycle", "o caro - nen vung anh"),
                                 ("theme_sun", "mat troi - sang"),
                                 ("theme_moon", "mat trang - toi"))):
    x = 20 + i * 150
    tool_icon(key, size=64).paint(p, QRect(x + 20, 14, 64, 64))
    p.setPen(QColor(theme.color("text")))
    p.drawText(QRect(x, 88, 150, 20), Qt.AlignHCenter, nhan)
p.end()
prev.save(os.path.join(OUT, "theme_05_icons.png"))
LOG.append("theme_05_icons.png")

print("\nSAVED:")
for n in LOG:
    print("   ", n)
print("DIR:", OUT)
