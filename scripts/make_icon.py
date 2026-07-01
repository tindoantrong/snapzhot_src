"""Sinh bộ icon đầy đủ cho app từ ảnh nguồn `icon_lon.png`.

Nguồn ưu tiên: <root>/icon_lon.png (1024x1024 RGBA). Nếu không có, dùng lại
<root>/assets/icon_master.png. Dùng Pillow + resampling LANCZOS để thu nhỏ nét.

Xuất ra (đúng cấu trúc chuẩn):
  assets/icon_master.png   : bản gốc 1024 (lưu kèm repo làm master).
  assets/icon.png          : bản 256 (mặc định cho QIcon / cửa sổ / khay).
  assets/icon.ico          : ICO multi-size cho Windows (taskbar + EXE).
  assets/icons/icon_<n>.png: từng size rời để QIcon chọn đúng độ phân giải.

Chạy:  python scripts/make_icon.py
"""
import os
import shutil

import _bootstrap  # noqa: F401  (đặt sys.path + UTF-8)

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
ICONS_DIR = os.path.join(ASSETS, "icons")

# Nguồn icon (theo thứ tự ưu tiên).
SOURCES = [
    os.path.join(ROOT, "icon_lon.png"),
    os.path.join(ASSETS, "icon_master.png"),
]

# Các size PNG rời (phục vụ khay 16/24/32, cửa sổ/taskbar, alt-tab...).
PNG_SIZES = [16, 24, 32, 48, 64, 128, 256, 512]
# Các size nhúng trong file .ico (Windows tự chọn size hợp nhất).
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
MASTER_SIZE = 1024


def load_source() -> Image.Image:
    for p in SOURCES:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            img = Image.open(p).convert("RGBA")
            print(f"Nguồn: {os.path.relpath(p, ROOT)}  ({img.width}x{img.height})")
            return img
    raise SystemExit(
        "LỖI: Không tìm thấy ảnh nguồn (icon_lon.png hoặc assets/icon_master.png)."
    )


def resized(src: Image.Image, size: int) -> Image.Image:
    if src.size == (size, size):
        return src.copy()
    return src.resize((size, size), Image.LANCZOS)


def main() -> int:
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(ICONS_DIR, exist_ok=True)

    src = load_source()

    # --- master 1024 (lưu kèm repo) ---
    master_path = os.path.join(ASSETS, "icon_master.png")
    # Tránh tự ghi đè khi chính nó là nguồn.
    if os.path.abspath(SOURCES[0]) != os.path.abspath(master_path) or not os.path.exists(master_path):
        master = resized(src, MASTER_SIZE) if max(src.size) != MASTER_SIZE else src
        master.save(master_path, "PNG")
    print(f"icon_master.png : {os.path.getsize(master_path)} bytes")

    # --- từng PNG size rời ---
    for s in PNG_SIZES:
        out = os.path.join(ICONS_DIR, f"icon_{s}.png")
        resized(src, s).save(out, "PNG")
    print(f"icons/icon_*.png: {len(PNG_SIZES)} files {PNG_SIZES}")

    # --- icon.png (256, mặc định) ---
    png_path = os.path.join(ASSETS, "icon.png")
    resized(src, 256).save(png_path, "PNG")
    assert os.path.getsize(png_path) > 0, "icon.png rỗng"
    print(f"icon.png        : {os.path.getsize(png_path)} bytes")

    # --- icon.ico (multi-size, Pillow ghi native) ---
    ico_path = os.path.join(ASSETS, "icon.ico")
    base = resized(src, max(ICO_SIZES))
    base.save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    assert os.path.getsize(ico_path) > 0, "icon.ico rỗng"
    print(f"icon.ico        : {os.path.getsize(ico_path)} bytes "
          f"({len(ICO_SIZES)} sizes: {ICO_SIZES})")

    print("=== MAKE ICON OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
