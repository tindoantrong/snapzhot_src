"""Test THEME: bảng token, template QSS và tín hiệu đổi giao diện sáng/tối.

Bắt các lỗi im lặng của kiểu "theme hoá bằng template":
  - hai bảng token lệch khoá → substitute nổ KeyError giữa lúc chạy;
  - còn sót mã hex trong template → chỗ đó kẹt màu theme cũ;
  - icon không đảo màu → chìm vào nền ở theme kia;
  - nền vùng ảnh bị kéo theo theme (phải độc lập, nhớ riêng).
"""
import os
import re

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication([])

from app.common import theme
from app.common.config import DEFAULTS
from app.common.shortcuts_dialog import ShortcutsDialog, _DIALOG_QSS_TPL
from app.editor.editor_window import EDITOR_QSS_TPL, EditorWindow
from app.editor.tool_icons import tool_icon
from app.library.library_window import LIBRARY_QSS_TPL

TEMPLATES = {
    "app": theme.APP_QSS_TPL,
    "editor": EDITOR_QSS_TPL,
    "library": LIBRARY_QSS_TPL,
    "shortcuts": _DIALOG_QSS_TPL,
}


def icon_hex(name="save", size=26) -> str:
    img = tool_icon(name, size=size).pixmap(QSize(size, size)).toImage()
    best, best_a = None, 0
    for y in range(size):
        for x in range(size):
            c = img.pixelColor(x, y)
            if c.alpha() > best_a:
                best, best_a = c, c.alpha()
    return best.name().upper()


def main() -> int:
    # --- 1. hai theme cùng bộ khoá ---
    assert set(theme.DARK) == set(theme.LIGHT), (
        "token lệch giữa dark/light: "
        f"{set(theme.DARK) ^ set(theme.LIGHT)}"
    )

    # --- 2. mọi template substitute được ở CẢ HAI theme, không sót hex ---
    for mode in ("dark", "light"):
        theme.manager.set_mode(mode)
        for name, tpl in TEMPLATES.items():
            out = theme.qss(tpl)          # thiếu token là KeyError ngay đây
            assert "$" not in out, f"[{mode}] template {name} còn $token chưa thay"
        # Template phải là template thật: không được nhúng mã hex chết.
        for name, tpl in TEMPLATES.items():
            leftovers = set(re.findall(r"#[0-9A-Fa-f]{6}\b", tpl))
            # #FFFFFF trong toast là màu chữ trên nền đen cố định — cho phép.
            leftovers -= {"#FFFFFF"}
            assert not leftovers, f"template {name} còn mã hex chết: {sorted(leftovers)}"

    # --- 3. đổi mode phát tín hiệu đúng một lần, không phát khi trùng ---
    theme.manager.set_mode("dark")
    seen = []
    theme.manager.changed.connect(seen.append)
    theme.manager.set_mode("dark")
    assert seen == [], "đặt lại đúng theme đang dùng thì KHÔNG được phát tín hiệu"
    assert theme.manager.toggle() == "light"
    assert theme.manager.toggle() == "dark"
    assert seen == ["light", "dark"], seen
    theme.manager.changed.disconnect(seen.append)

    # --- 4. icon đảo màu theo theme ---
    theme.manager.set_mode("dark")
    dark_icon = icon_hex()
    theme.manager.set_mode("light")
    light_icon = icon_hex()
    assert dark_icon != light_icon, "icon phải đổi màu theo theme"
    assert dark_icon == theme.DARK["icon"].upper(), dark_icon
    assert light_icon == theme.LIGHT["icon"].upper(), light_icon

    # --- 5. nền VÙNG ẢNH độc lập với theme + nhớ riêng ---
    theme.manager.set_mode("dark")
    w = EditorWindow()
    w.set_canvas_bg_index(1)                       # Trắng
    before = w.canvas.backgroundBrush().color().name()
    theme.manager.set_mode("light")
    app.processEvents()
    assert w.canvas.backgroundBrush().color().name() == before, (
        "đổi theme KHÔNG được đụng vào nền vùng ảnh"
    )
    assert w.canvas_bg_index() == 1
    emitted = []
    w.canvas_bg_changed.connect(emitted.append)
    w._cycle_canvas_bg()
    assert emitted == [2], emitted        # Trắng → Đen
    assert w.canvas_bg_index() == 2

    def _lum(c: QColor) -> float:
        def ch(v):
            v /= 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())

    # --- 5b. chữ trong hộp thoại phải đọc được ở CẢ HAI theme ---
    # Bẫy thật đã sập một lần: tiêu đề để màu "chữ trên nền nhấn" (trắng), sang
    # theme sáng thành trắng-trên-trắng, mất tiêu đề.
    def _lum(c: QColor) -> float:
        def ch(v):
            v /= 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())

    for mode in ("dark", "light"):
        theme.manager.set_mode(mode)
        dlg = ShortcutsDialog()
        dlg.show()
        app.processEvents()
        bg = QColor(theme.color("bg"))
        for lb in dlg.findChildren(QLabel):
            if not lb.text().strip():
                continue
            fg = lb.palette().color(QPalette.WindowText)
            hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
            ratio = (hi + 0.05) / (lo + 0.05)
            assert ratio >= 4.5, (
                f"[{mode}] hộp thoại phím tắt: {lb.objectName() or lb.text()[:20]!r} "
                f"chữ {fg.name()} trên nền {bg.name()} chỉ {ratio:.2f}:1"
            )
        dlg.close()

    # --- 5c. hai vai trò của màu nhấn phải đạt chuẩn ở CẢ HAI theme ---
    # accent_fill là mảng đặc có chữ đè → chuẩn chữ (4.5:1).
    # accent là viền/vòng focus → chuẩn thành phần giao diện (3:1) so với nền.
    for mode in ("dark", "light"):
        theme.manager.set_mode(mode)
        t = theme.manager.tokens()

        def _c(a, b):
            hi, lo = sorted((_lum(QColor(a)), _lum(QColor(b))), reverse=True)
            return (hi + 0.05) / (lo + 0.05)

        r = _c(t["on_accent"], t["accent_fill"])
        assert r >= 4.5, f"[{mode}] chữ trên mảng nhấn chỉ {r:.2f}:1"
        r = _c(t["accent"], t["bg"])
        assert r >= 3.0, f"[{mode}] viền nhấn trên nền cửa sổ chỉ {r:.2f}:1"
        r = _c(t["accent"], t["surface"])
        assert r >= 3.0, f"[{mode}] viền nhấn trên toolbar chỉ {r:.2f}:1"

    # --- 6. cấu hình có khoá để nhớ qua các phiên ---
    assert DEFAULTS["theme"] in ("dark", "light")
    assert DEFAULTS["canvas_bg"] == 0

    theme.manager.set_mode("dark")
    print("=== THEME OK === (token khớp, 4 template sạch, icon đảo màu, "
          "nền vùng ảnh độc lập)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
