"""Test THEME-CONTRAST: chữ của Editor phải đọc được ở CẢ HAI theme.

Nguồn cơn: QLabel trần trong toolbar KHÔNG thừa hưởng màu chữ của QToolButton,
nên nhãn mức zoom "100%" từng bị vẽ đen (#000000) trên nền #33363B — tương phản
1.73:1, chìm hẳn vào nền. Qt style sheet đổ màu QSS vào palette của widget sau
khi polish, nên đọc palette là biết đúng màu sẽ vẽ ra.

Kiểm mọi nhãn CHỮ chính của Editor đạt WCAG AA (>= 4.5:1) so với nền của nó,
chạy lại một lượt cho theme tối và một lượt cho theme sáng.
"""
import os

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QImage, QPalette

app = QApplication([])

from app.common import theme
from app.editor.editor_window import EditorWindow


def _lum(c: QColor) -> float:
    def ch(v: int) -> float:
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def contrast(fg: QColor, bg: QColor) -> float:
    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def main() -> int:
    w = EditorWindow()
    img = QImage(120, 80, QImage.Format_RGB32)
    img.fill(QColor("#3366cc"))
    w.load_image(img)
    w.show()
    app.processEvents()

    # (nhãn, token nền phía sau nó, mô tả)
    cases = [
        (w.zoom_label, "surface", 'mức zoom "100%" trên thanh Zoom'),
        (w.status_zoom, "surface_alt", "mức zoom ở thanh trạng thái"),
        (w.status_size, "surface_alt", "kích thước ảnh ở thanh trạng thái"),
        (w.status_hint, "surface_alt", "gợi ý công cụ ở thanh trạng thái"),
        (w._recent_title_label, "surface", 'tiêu đề "Ảnh gần đây · N"'),
        (w._recent_empty, "bg", 'dòng "Chưa có ảnh gần đây"'),
        (w._props_title_label, "surface", "tiêu đề panel Thuộc tính"),
        (w.width_label, "bg", "độ dày nét trong panel Thuộc tính"),
    ]

    worst = None
    for mode in ("dark", "light"):
        theme.manager.set_mode(mode)
        app.processEvents()
        for label, bg_role, desc in cases:
            fg = label.palette().color(QPalette.WindowText)
            bg = QColor(theme.color(bg_role))
            ratio = contrast(fg, bg)
            assert ratio >= 4.5, (
                f"[{mode}] {desc}: chữ {fg.name()} trên nền {bg.name()} chỉ "
                f"{ratio:.2f}:1 (cần >= 4.5) — chìm vào nền"
            )
            if worst is None or ratio < worst[0]:
                worst = (ratio, f"[{mode}] {desc}")

        # Nút ẩn/hiện dải ảnh cũng là chữ, kiểm luôn.
        fg = w._recent_toggle_btn.palette().color(QPalette.ButtonText)
        ratio = contrast(fg, QColor(theme.color("surface")))
        assert ratio >= 4.5, f'[{mode}] nút "Ẩn/Hiện": {fg.name()} chỉ {ratio:.2f}:1'

        # Icon line-art cũng phải nổi trên nền toolbar.
        ratio = contrast(QColor(theme.color("icon")),
                         QColor(theme.color("surface")))
        assert ratio >= 4.5, f"[{mode}] icon toolbar chỉ {ratio:.2f}:1"

    theme.manager.set_mode("dark")
    print(f"=== TEXT CONTRAST OK (dark + light) === "
          f"(thấp nhất {worst[0]:.2f}:1 — {worst[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
