"""QC harness REC-COLLAPSE: thu gọn dải "Ảnh gần đây" thành thanh tiêu đề 32px.

Dựng EditorWindow THẬT offscreen + ảnh + 12 thumbnail; kiểm:
  - Mở: "Ảnh gần đây · 12" bên trái, nút "▾ Ẩn" bên phải, ngay trên dải thumb.
  - Bấm nút HOẶC bấm thanh tiêu đề đều đổi trạng thái.
  - Thu gọn: chỉ còn thanh ~32px, canvas nở xuống, nút đổi thành "▴ Hiện".
  - set_recent_captures() (chụp ảnh mới) KHÔNG tự bung dải đang ẩn.
  - Bung lại: ảnh đang mở vẫn giữ viền xanh (item selected).
  - Rỗng: nhãn "· 0", mở ra hiện dòng "Chưa có ảnh gần đây".
KHÔNG sửa app/.
"""
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent

from app.editor.editor_window import EditorWindow
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

LOG = []


def pump(n=5):
    for _ in range(n):
        app.processEvents()


def shot_window(name):
    pump()
    w.grab().save(os.path.join(OUT, name))
    LOG.append(name)


def shot_rect(rect, name):
    pump()
    w.grab(rect).save(os.path.join(OUT, name))
    LOG.append(name)


def click_titlebar():
    """Giả lập nhấp chuột trái vào giữa thanh tiêu đề (không trúng nút)."""
    tb = w._recent_titlebar
    pos = QPointF(40, tb.height() / 2)
    glob = QPointF(tb.mapToGlobal(QPoint(40, tb.height() // 2)))
    for etype in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        app.sendEvent(tb, QMouseEvent(etype, pos, glob, Qt.LeftButton,
                                      Qt.LeftButton, Qt.NoModifier))
    pump()


w = EditorWindow()
w.load_image(make_sample_image(1280, 800), capture_id=3)
# Nhân đôi bộ mẫu cho đủ 12 thẻ — copy từng dict, KHÔNG dùng list*2 (nhân đôi
# tham chiếu thì gán id sau đó sẽ đè lên chính nó).
_base = make_recent_thumbs()
recents = [dict(_base[i % len(_base)], id=i + 1) for i in range(12)]
w.set_recent_captures(recents)
w.resize(1180, 760)
w.show()
pump()

print("=" * 66)
print("REC-COLLAPSE: dải 'Ảnh gần đây' thu gọn thành thanh tiêu đề ở đáy")
print("=" * 66)

dock = w.recent_dock
tb = w._recent_titlebar
btn = w._recent_toggle_btn

# ---------- [1] Trạng thái MỞ ----------
print("\n[1] Dải MỞ:")
print(f"    nhãn={w._recent_title_label.text()!r} | nút={btn.text()!r} "
      f"tooltip={btn.toolTip()!r}")
print(f"    thanh tiêu đề cao={tb.height()}px (mong 32)")
lbl_x = w._recent_title_label.mapTo(dock, w._recent_title_label.rect().center()).x()
btn_x = btn.mapTo(dock, btn.rect().center()).x()
print(f"    nhãn TRÁI, nút PHẢI (x {lbl_x} < {btn_x}) = {lbl_x < btn_x}")
btn_top = btn.mapTo(w, btn.rect().center()).y()
strip_top = w.recent_strip.mapTo(w, QPoint(0, 0)).y()
print(f"    nút nằm NGAY TRÊN dải thumbnail (y {btn_top} < {strip_top}) = "
      f"{btn_top < strip_top}")
print(f"    dock cao={dock.height()} | canvas vp cao={w.canvas.viewport().height()}")

vp_open = w.canvas.viewport().height()
shot_window("reccol_01_window_open.png")
shot_rect(dock.geometry(), "reccol_02_titlebar_open.png")

# ---------- [2] Bấm NÚT → thu gọn ----------
btn.click()
pump()
print("\n[2] Bấm nút '▾ Ẩn' → THU GỌN:")
print(f"    expanded={w.is_recent_expanded()} | thân cao={w._recent_body.height()}px "
      f"(khuất hẳn={w._recent_body.height() == 0}) | thân tắt tương tác="
      f"{not w._recent_body.isEnabled()}")
print(f"    dock CÒN hiện = {dock.isVisible()} | dock cao={dock.height()}px (mong 32)")
print(f"    nút={btn.text()!r} tooltip={btn.toolTip()!r}")
print(f"    canvas vp {vp_open} → {w.canvas.viewport().height()} "
      f"(nới rộng={w.canvas.viewport().height() > vp_open})")
shot_window("reccol_03_window_collapsed.png")
shot_rect(QRect(0, w.height() - 90, w.width(), 90), "reccol_04_bar_closeup.png")

# ---------- [3] Chụp ảnh mới KHÔNG tự bung ----------
w.set_recent_captures([dict(recents[0], id=99)] + recents)
pump()
print("\n[3] set_recent_captures() khi đang ẩn (mô phỏng chụp ảnh mới):")
print(f"    vẫn thu gọn = {not w.is_recent_expanded()} | nhãn={w._recent_title_label.text()!r}")

# ---------- [4] Bấm THANH TIÊU ĐỀ → bung lại ----------
click_titlebar()
print("\n[4] Bấm thanh tiêu đề → BUNG LẠI:")
print(f"    expanded={w.is_recent_expanded()} | dock cao={dock.height()}")
print(f"    canvas vp trở lại {w.canvas.viewport().height()} "
      f"(khớp lúc đầu={w.canvas.viewport().height() == vp_open})")
sel = [w.recent_strip.item(i).data(Qt.UserRole)
       for i in range(w.recent_strip.count()) if w.recent_strip.item(i).isSelected()]
print(f"    ảnh đang mở (capture_id=3) giữ viền xanh: selected={sel} "
      f"= {sel == [3]}")
shot_window("reccol_05_window_reopen_highlight.png")

# ---------- [5] Tín hiệu lưu cấu hình ----------
seen = []
w.recent_expanded_changed.connect(seen.append)
btn.click(); pump()
click_titlebar()
print("\n[5] recent_expanded_changed (controller ghi vào config):")
print(f"    chuỗi tín hiệu={seen} (mong [False, True])")
w.set_recent_expanded(False)
pump()
print(f"    set_recent_expanded() khôi phục KHÔNG phát tín hiệu = {seen == [False, True]}"
      f" | expanded={w.is_recent_expanded()}")

# ---------- [6] Rỗng ----------
w.set_recent_expanded(True)
w.set_recent_captures([])
pump()
print("\n[6] Không có ảnh nào:")
print(f"    nhãn={w._recent_title_label.text()!r} | dock còn hiện={dock.isVisible()}")
print(f"    dòng rỗng hiện={w._recent_empty.isVisible()} "
      f"text={w._recent_empty.text()!r} | dải ẩn={not w.recent_strip.isVisible()}")
shot_rect(QRect(0, w.height() - 170, w.width(), 170), "reccol_06_empty.png")

print("\nSAVED:")
for n in LOG:
    print("   ", n)
print("DIR:", OUT)
