"""Sinh latest.json (manifest autoupdate) từ __version__ và gọi build_installer.

Đảm bảo latest.json KHÔNG bao giờ lệch khỏi app/__version__ — hằng số version
chỉ nằm ở app/__init__.py, mọi artifact đều sinh từ đó.

Chạy:
  python scripts/make_release.py                        # sinh manifest + full build
  python scripts/make_release.py --skip-build           # chỉ sinh manifest, không build
  python scripts/make_release.py --iss-only             # manifest + chỉ bước ISCC
  python scripts/make_release.py --notes "Bản vá lỗi"  # ghi đè notes manifest
"""
import argparse
import json
import os
import subprocess
import sys

import _bootstrap  # noqa: F401  (sys.path + UTF-8)

from app import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(ROOT, "latest.json")
_REPO = "tindoantrong/snapzhot_src"


# ---------------------------------------------------------------------------
# Hàm THUẦN (dễ test, không side-effect)
# ---------------------------------------------------------------------------

def build_manifest(version: str, notes: str) -> dict:
    """Trả về dict manifest autoupdate. Hàm thuần — không đọc/ghi file."""
    return {
        "version": version,
        "url": (
            f"https://github.com/{_REPO}/releases/latest/download/"
            f"SnagTin-Setup-{version}.exe"
        ),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Hàm ghi file
# ---------------------------------------------------------------------------

def write_manifest(path: str, notes_override: str | None = None) -> dict:
    """Sinh manifest từ __version__ và ghi ra ``path``.

    - notes: giữ nguyên từ file cũ nếu tồn tại, TRỪ KHI ``notes_override`` được truyền.
    - Trả về dict đã ghi (để caller kiểm tra / log).
    """
    # Đọc notes cũ nếu có
    old_notes = ""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f)
            old_notes = str(old.get("notes", "")).strip()
        except Exception:
            pass

    notes = notes_override if notes_override is not None else old_notes
    manifest = build_manifest(__version__, notes)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return manifest


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"Sinh latest.json và (tuỳ chọn) build installer SnagTin v{__version__}"
    )
    ap.add_argument("--skip-build", action="store_true",
                    help="chỉ sinh manifest, không gọi build_installer")
    ap.add_argument("--iss-only", action="store_true",
                    help="manifest + truyền --iss-only xuống build_installer")
    ap.add_argument("--notes", metavar="TEXT", default=None,
                    help="ghi đè notes trong manifest (mặc định: giữ notes cũ)")
    args = ap.parse_args()

    print(f"=== MAKE RELEASE SnagTin v{__version__} ===")

    # (a) Sinh manifest
    manifest = write_manifest(MANIFEST_PATH, notes_override=args.notes)
    rel = os.path.relpath(MANIFEST_PATH, ROOT)
    print(f"[manifest] đã ghi {rel}:")
    print(f"           version = {manifest['version']}")
    print(f"           url     = {manifest['url']}")
    print(f"           notes   = {manifest['notes']!r}")

    # (b) Build installer (trừ khi --skip-build)
    if not args.skip_build:
        cmd = [sys.executable, os.path.join("scripts", "build_installer.py")]
        if args.iss_only:
            cmd.append("--iss-only")
        print()
        print(f"[build] Gọi: {' '.join(cmd)}")
        ret = subprocess.run(cmd, cwd=ROOT).returncode
        if ret != 0:
            print(f"\nLỖI: build_installer trả về code {ret}.")
            return ret
    else:
        print("\n[build] --skip-build: bỏ qua bước build installer.")

    # (c) Checklist release
    ver = __version__
    setup_exe = f"dist/SnagTin-Setup-{ver}.exe"
    print()
    print("=" * 60)
    print("CHECKLIST RELEASE — 2 artifact cần upload:")
    print(f"  1) {setup_exe}")
    print(f"  2) latest.json")
    print()
    print(f"Repo đích: https://github.com/{_REPO}")
    print()
    print("Các bước upload thủ công (gh CLI chưa cài):")
    print(f"  1) Vào github.com/{_REPO}/releases/new")
    print(f"  2) Tạo tag: v{ver}  |  Tiêu đề: SnagTin v{ver}")
    print(f"  3) Đính kèm: {setup_exe}")
    print( "  4) Đính kèm: latest.json  (vào cùng release)")
    print( "  5) Nhấn Publish release")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
