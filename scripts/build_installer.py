"""Build pipeline đóng gói SnagTin thành Setup.exe.

Các bước (theo thứ tự):
  1. make_icon  : sinh assets/icon.ico từ nguồn (bỏ qua nếu đã có icon.ico).
  2. PyInstaller: build bản onedir → dist/SnagTin/ (SnagTin.exe + _internal/).
  3. dọn        : xoá onefile cũ dist/SnagTin.exe (216MB, lỗi thời) nếu còn.
  4. Inno Setup : ISCC.exe biên dịch installer/SnagTin.iss → dist/SnagTin-Setup-<ver>.exe.

PHỤ THUỘC: bước 4 cần Inno Setup (ISCC.exe) cài sẵn trên máy build. Nếu chưa có,
script dừng SAU bước 3 và in hướng dẫn cài Inno Setup (tải free tại jrsoftware.org).

Chạy:
  python scripts/build_installer.py                 # full pipeline
  python scripts/build_installer.py --skip-icon     # bỏ qua make_icon
  python scripts/build_installer.py --skip-build    # dùng dist/SnagTin/ sẵn có
  python scripts/build_installer.py --iss-only      # chỉ chạy bước 4 (ISCC)
"""
import argparse
import os
import shutil
import subprocess
import sys

import _bootstrap  # noqa: F401  (sys.path + UTF-8)

from app import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
ONEDIR = os.path.join(DIST, "SnagTin")
ONEFILE_OLD = os.path.join(DIST, "SnagTin.exe")
SPEC = os.path.join(ROOT, "SnagTin.spec")
ISS = os.path.join(ROOT, "installer", "SnagTin.iss")
ICON_ICO = os.path.join(ROOT, "assets", "icon.ico")

# Vị trí ISCC.exe thường gặp (Inno Setup 6).
# Gồm cả bản cài per-user (AppData\Local\Programs) — kiểu cài mặc định khi
# không có quyền admin, không nằm trong Program Files.
_LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
ISCC_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    os.path.join(_LOCALAPPDATA, "Programs", "Inno Setup 6", "ISCC.exe"),
    os.path.join(_LOCALAPPDATA, "Programs", "Inno Setup 5", "ISCC.exe"),
]


def run(cmd, **kw) -> None:
    print(">>", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def find_iscc() -> str | None:
    for p in ISCC_CANDIDATES:
        if os.path.exists(p):
            return p
    found = shutil.which("ISCC")
    return found


def step_icon() -> None:
    if os.path.exists(ICON_ICO) and os.path.getsize(ICON_ICO) > 0:
        print(f"[icon] đã có {os.path.relpath(ICON_ICO, ROOT)} — bỏ qua make_icon.")
        return
    print("[icon] sinh icon...")
    run([sys.executable, os.path.join("scripts", "make_icon.py")])


def step_build() -> None:
    print("[build] PyInstaller onedir...")
    run([sys.executable, "-m", "PyInstaller", SPEC, "--noconfirm", "--clean"])


def step_cleanup_onefile() -> None:
    if os.path.exists(ONEFILE_OLD):
        size_mb = os.path.getsize(ONEFILE_OLD) / (1024 * 1024)
        os.remove(ONEFILE_OLD)
        print(f"[clean] đã xoá onefile cũ dist/SnagTin.exe ({size_mb:.0f}MB).")
    else:
        print("[clean] không thấy onefile cũ — bỏ qua.")


def step_iss(iscc: str) -> None:
    exe = os.path.join(ONEDIR, "SnagTin.exe")
    if not os.path.exists(exe):
        sys.exit(f"LỖI: thiếu {os.path.relpath(exe, ROOT)} — chạy bước build trước "
                 "(bỏ --skip-build).")
    print(f"[iss] biên dịch installer với ISCC: {iscc}")
    run([iscc, f"/DMyAppVersion={__version__}", ISS])
    out = os.path.join(DIST, f"SnagTin-Setup-{__version__}.exe")
    if os.path.exists(out):
        size_mb = os.path.getsize(out) / (1024 * 1024)
        print(f"=== INSTALLER OK: {os.path.relpath(out, ROOT)} ({size_mb:.0f}MB) ===")
    else:
        print("=== ISCC chạy xong nhưng KHÔNG thấy Setup.exe — kiểm tra log trên. ===")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build SnagTin Setup.exe")
    ap.add_argument("--skip-icon", action="store_true", help="bỏ qua make_icon")
    ap.add_argument("--skip-build", action="store_true", help="dùng dist/SnagTin/ sẵn có")
    ap.add_argument("--iss-only", action="store_true", help="chỉ chạy bước ISCC")
    args = ap.parse_args()

    print(f"=== BUILD INSTALLER SnagTin v{__version__} ===")

    if not args.iss_only:
        if not args.skip_icon:
            step_icon()
        if not args.skip_build:
            step_build()
        step_cleanup_onefile()

    iscc = find_iscc()
    if iscc is None:
        print()
        print("!! CHƯA CÀI INNO SETUP — không tìm thấy ISCC.exe.")
        print("   Bản onedir đã sẵn ở dist/SnagTin/. Để xuất Setup.exe:")
        print("   1) Tải Inno Setup (free) tại https://jrsoftware.org/isdl.php và cài.")
        print("   2) Chạy lại:  python scripts/build_installer.py --iss-only")
        print(f"   (hoặc trực tiếp:  ISCC /DMyAppVersion={__version__} installer\\SnagTin.iss )")
        return 2

    step_iss(iscc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
