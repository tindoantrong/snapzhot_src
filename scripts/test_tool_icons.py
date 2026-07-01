"""Test bộ icon line-art (offscreen): mỗi tên vẽ ra QIcon hợp lệ + đúng size."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8 để chạy thẳng từ thư mục gốc)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize

app = QApplication([])

from app.editor.tool_icons import tool_icon, _DRAWERS, _CACHE

NAMES = list(_DRAWERS.keys())
assert NAMES, "phải có ít nhất một icon"

SIZE = 26
for name in NAMES:
    icon = tool_icon(name, size=SIZE)
    assert not icon.isNull(), f"icon '{name}' bị null"
    pm = icon.pixmap(SIZE, SIZE)
    assert pm.size() == QSize(SIZE, SIZE), (
        f"icon '{name}' size sai: {pm.size()} != {QSize(SIZE, SIZE)}"
    )
    # Pixmap phải có ít nhất vài pixel khác trong suốt (đã vẽ gì đó).
    img = pm.toImage()
    painted = any(
        img.pixelColor(x, y).alpha() > 0
        for x in range(0, SIZE, 2)
        for y in range(0, SIZE, 2)
    )
    assert painted, f"icon '{name}' rỗng (không vẽ gì)"
print(f"OK: {len(NAMES)} icon vẽ hợp lệ:", ", ".join(NAMES))

# --- P1-fix: 4 icon mới phải có mặt và hợp lệ ---
for name in ("save", "export", "copy", "open"):
    assert name in _DRAWERS, f"thiếu icon mới '{name}'"
    icon = tool_icon(name, size=SIZE)
    assert not icon.isNull(), f"icon mới '{name}' bị null"
    assert icon.pixmap(SIZE, SIZE).size() == QSize(SIZE, SIZE), f"'{name}' size sai"
print("OK: 4 icon mới (save/export/copy/open) hợp lệ")

# --- C2: icon callout phải có mặt, không null, đúng size ---
assert "callout" in _DRAWERS, "thiếu icon 'callout'"
co = tool_icon("callout", size=SIZE)
assert not co.isNull(), "icon 'callout' bị null"
assert co.pixmap(SIZE, SIZE).size() == QSize(SIZE, SIZE), "'callout' size sai"
print("OK: icon callout hợp lệ")

# --- Cache: gọi lại trả về cùng object ---
a = tool_icon("arrow", size=SIZE)
b = tool_icon("arrow", size=SIZE)
assert a is b, "cache phải trả về cùng QIcon cho khoá giống nhau"
print("OK: cache hoạt động (cùng object)")

# --- Màu/size khác nhau là khoá khác nhau ---
c = tool_icon("arrow", color="#FF0000", size=SIZE)
assert c is not a, "màu khác phải là icon khác"
d = tool_icon("arrow", size=40)
assert d is not a, "size khác phải là icon khác"
assert ("arrow", "#FF0000", SIZE) in _CACHE
print("OK: phân biệt khoá theo (name, color, size)")

# --- Tên không tồn tại: không crash, trả pixmap trong suốt ---
empty = tool_icon("khong_ton_tai", size=SIZE)
assert not empty.isNull()
print("OK: tên lạ không crash")

print("=== TOOL ICONS OK ===")
