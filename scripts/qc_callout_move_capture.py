"""QC MOVE2 — chứng minh callout HẾT vệt sọc khi di chuyển.

Vệt sọc khi MOVE = Qt chỉ invalidate vùng `boundingRect` của item; nếu nét pen vẽ
TRÀN ra ngoài boundingRect thì pixel ngoài lề không bị xoá → "ghost" dọc đường kéo.
`grab()` luôn full-repaint nên KHÔNG tái hiện được ghost bằng ảnh — thay vào đó ta
verify ROOT CAUSE deterministic: render `paint()` ra ảnh rồi đo bbox pixel thực vẽ,
khẳng định nó NẰM TRỌN trong boundingRect mới (và CHỨNG MINH boundingRect CŨ quá nhỏ).

Bồi thêm: đổi width qua set_border (mutate style) → boundingRect phải nới theo
(prepareGeometryChange có hiệu lực). Và grab ảnh callout viền dày cho mắt người.
"""
import math
import os

import _bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication, QGraphicsTextItem, QStyleOptionGraphicsItem,
)

from app.editor.canvas import CalloutItem

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".ai-workspace", "screens")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
for _f in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
    if os.path.exists(_f):
        fams = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(_f))
        if fams:
            app.setFont(QFont(fams[0], 10))
            break

PAD = 16          # lề ảnh quanh boundingRect (đủ chứa pen overflow để soi)
ALPHA = 16        # ngưỡng coi là pixel có vẽ


def render_paint(co: CalloutItem):
    """Render co.paint() ra QImage cỡ boundingRect + PAD mỗi cạnh.

    Trả (image, br, origin) với origin = điểm item-coord ứng với pixel (0,0).
    """
    br = co.boundingRect()
    w = math.ceil(br.width()) + 2 * PAD
    h = math.ceil(br.height()) + 2 * PAD
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    origin_x = br.left() - PAD
    origin_y = br.top() - PAD
    p = QPainter(img)
    p.translate(-origin_x, -origin_y)   # item-coord -> image-coord
    opt = QStyleOptionGraphicsItem()
    opt.rect = br.toRect()
    co.paint(p, opt, None)
    p.end()
    return img, br, (origin_x, origin_y)


def painted_bbox_item_coords(img: QImage, origin):
    """bbox (item-coord) của mọi pixel có alpha>ALPHA. None nếu trống."""
    minx = miny = 10**9
    maxx = maxy = -10**9
    ox, oy = origin
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > ALPHA:
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
    if maxx < 0:
        return None
    return QRectF(minx + ox, miny + oy, (maxx - minx), (maxy - miny))


def contains(outer: QRectF, inner: QRectF, slack: float = 0.5) -> bool:
    return (inner.left() >= outer.left() - slack
            and inner.top() >= outer.top() - slack
            and inner.right() <= outer.right() + slack
            and inner.bottom() <= outer.bottom() + slack)


def old_bounding_rect(co: CalloutItem) -> QRectF:
    """boundingRect TRƯỚC fix MOVE1: chỉ nới cạnh dưới _TAIL_H (không cộng pen)."""
    return QGraphicsTextItem.boundingRect(co).adjusted(0, 0, 0, CalloutItem._TAIL_H)


fail = 0


def check(cond, msg):
    global fail
    print(("OK: " if cond else "FAIL: ") + msg)
    if not cond:
        fail += 1


# ===== 1. Callout viền dày: paint nằm TRỌN trong boundingRect mới =====
co = CalloutItem("Chú thích dài để bong bóng đủ rộng", QColor("#FFFFFF"),
                 QColor("#FF3B30"), 20, 24)
img, new_br, origin = render_paint(co)
img.save(os.path.join(OUT, "move_01_callout_w20.png"))
pbb = painted_bbox_item_coords(img, origin)
assert pbb is not None, "phải có pixel vẽ"
print(f"  width=20  paint_bbox={pbb}  new_br={new_br}  old_br={old_bounding_rect(co)}")
check(contains(new_br, pbb), "paint pixel NẰM TRỌN trong boundingRect mới → move không để ghost")

# ===== 2. Chứng minh boundingRect CŨ quá nhỏ (bug cũ sẽ để vệt) =====
old_br = old_bounding_rect(co)
overflow = not contains(old_br, pbb, slack=0.5)
check(overflow, "paint pixel TRÀN ra ngoài boundingRect CŨ (xác nhận đúng root cause vệt sọc)")
# Định lượng tràn bao nhiêu px mỗi cạnh để báo cáo.
print(f"  tràn ngoài old_br: left={old_br.left()-pbb.left():.1f} top={old_br.top()-pbb.top():.1f} "
      f"right={pbb.right()-old_br.right():.1f} bottom={pbb.bottom()-old_br.bottom():.1f} (px, >0 = tràn)")

# ===== 3. set_border(width=...) nới boundingRect (prepareGeometryChange) =====
co2 = CalloutItem("Mutate width", QColor("#FFFFFF"), QColor("#1E90FF"), 4, 24)
br_before = QRectF(co2.boundingRect())
co2.set_border(QColor("#1E90FF"), width=24)   # đổi width khi đang ở vị trí cũ
br_after = QRectF(co2.boundingRect())
check(br_after.width() > br_before.width() and br_after.height() > br_before.height(),
      f"đổi width 4→24 nới boundingRect ({br_before.width():.0f}×{br_before.height():.0f} "
      f"→ {br_after.width():.0f}×{br_after.height():.0f})")
img2, nbr2, org2 = render_paint(co2)
img2.save(os.path.join(OUT, "move_02_callout_mutated_w24.png"))
pbb2 = painted_bbox_item_coords(img2, org2)
check(pbb2 is not None and contains(nbr2, pbb2),
      "sau mutate width: paint vẫn nằm trọn boundingRect (kéo sẽ không vệt)")

# ===== 4. Regression: đuôi + viền vẫn vẽ đủ (không bị cắt) =====
# Đuôi nằm ở nửa dưới: phải có pixel vẽ dưới đáy thân bong bóng (super bbox).
super_br = QGraphicsTextItem.boundingRect(co)
has_tail = pbb.bottom() > super_br.bottom() + 1.0
check(has_tail, f"đuôi vẽ dưới thân bong bóng (paint_bottom={pbb.bottom():.0f} > "
                f"body_bottom={super_br.bottom():.0f})")
# Viền trái/phải vẽ ra (paint rộng hơn vùng text thuần do pen).
has_border = pbb.left() < super_br.left() + 0.5 and pbb.right() > super_br.right() - 0.5
check(has_border, "viền pen vẽ quanh thân (paint phủ tới/ra mép thân)")

print("DIR:", OUT)
print("=== CALLOUT MOVE (no-ghost) " + ("OK ===" if fail == 0 else f"FAIL x{fail} ==="))
