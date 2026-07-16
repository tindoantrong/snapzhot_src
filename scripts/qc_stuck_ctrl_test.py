#!/usr/bin/env python3
"""qc_stuck_ctrl_test.py — Công cụ chẩn đoán bug "Ctrl phải kẹt" cho SnagTin.

Cách chạy (từ thư mục gốc project):
    python scripts/qc_stuck_ctrl_test.py

Dependency:
  - ctypes  : stdlib, KHÔNG cần cài thêm
  - keyboard: đã cài sẵn cùng app (pip install keyboard)
  - KHÔNG cần pywin32, KHÔNG cần admin

Điều kiện bắt buộc:
  - Windows desktop session INTERACTIVE (không SSH, không piped subprocess)
  - Chạy từ cmd.exe / PowerShell / double-click .py — KHÔNG từ VS Code terminal pipe
  - KHÔNG chạm bàn phím hoặc di chuột trong khoảng 10 giây khi test đang chạy
  - Nên tạm đóng bộ gõ tiếng Việt (Unikey, EVKey, GoTiengViet) + phần mềm
    gaming keyboard / macro tool trước khi chạy — xem lý do ở mục "Re-entrant hook"

CẢNH BÁO: Script giả lập phím thật qua keybd_event. KHÔNG chạm bàn phím lúc chạy.
"""
import _bootstrap  # noqa: F401  (sys.path + UTF-8 — shared với test_hotkey_recovery)

import ctypes
import ctypes.wintypes as _wt
import sys
import time
import traceback as _tb
import threading

# ──────────────────────────── Windows API ────────────────────────────────────
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

VK_CONTROL  = 0x11
VK_RCONTROL = 0xA3
VK_LCONTROL = 0xA2
VK_SHIFT    = 0x10
VK_F        = 0x46
SC_CTRL     = 0x1D
SC_SHIFT    = 0x2A
SC_F        = 0x21

_u32 = ctypes.windll.user32

# ──────────────────────── WH_KEYBOARD_LL hook enum ───────────────────────────
WH_KEYBOARD_LL = 13

class _HOOKINFO(ctypes.Structure):
    _fields_ = [
        ("nSize",   _wt.DWORD),
        ("pt",      ctypes.c_longlong),   # POINT (2 × LONG, tổng 8 byte)
        ("wParam",  _wt.WPARAM),
        ("lParam",  _wt.LPARAM),
    ]

# SetWindowsHookEx / EnumThreadWindows không cần, ta dùng:
# GetNextHook  ← không public; thay bằng iterate qua GetModuleHandle + CreateToolhelp32Snapshot
# Cách đơn giản nhất: dùng NtQuerySystemInformation hoặc đọc handle table.
# NHƯNG đơn giản hơn: dùng EnumWindows để liệt kê process + check hook via undoc API.
#
# Approach thực tế nhất: dùng ctypes.windll.user32.SetWindowsHookExW để đặt hook THỬ,
# rồi dùng CallNextHookEx — không công khai. Ta dùng cách KHÁC:
# Intercept trực tiếp keyboard lib hook và đếm re-entrant calls.

# ──────────────────────── Key injection ──────────────────────────────────────

def _kev(vk: int, scan: int, flags: int) -> None:
    """keybd_event: hoạt động đáng tin hơn SendInput trong piped/restricted session."""
    _u32.keybd_event(vk, scan, flags, 0)


def _lctrl_dn()  -> None: _kev(VK_LCONTROL, SC_CTRL,  0)
def _lctrl_up()  -> None: _kev(VK_LCONTROL, SC_CTRL,  KEYEVENTF_KEYUP)
def _rctrl_dn()  -> None: _kev(VK_RCONTROL, SC_CTRL,  KEYEVENTF_EXTENDEDKEY)
def _rctrl_up()  -> None: _kev(VK_RCONTROL, SC_CTRL,  KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP)
def _shift_dn()  -> None: _kev(VK_SHIFT,    SC_SHIFT, 0)
def _shift_up()  -> None: _kev(VK_SHIFT,    SC_SHIFT, KEYEVENTF_KEYUP)
def _f_dn()      -> None: _kev(VK_F,        SC_F,     0)
def _f_up()      -> None: _kev(VK_F,        SC_F,     KEYEVENTF_KEYUP)


def _force_release_ctrl() -> None:
    """Force-release tất cả Ctrl variant — LUÔN gọi trong finally."""
    _kev(VK_LCONTROL, SC_CTRL, KEYEVENTF_KEYUP)
    _kev(VK_RCONTROL, SC_CTRL, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP)
    _kev(VK_CONTROL,  0,       KEYEVENTF_KEYUP)
    try:
        import keyboard as _kb
        _kb.release('ctrl')
    except Exception:
        pass


def _wait_ctrl_clear(timeout_s: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _is_ctrl_stuck()[0]:
            return True
        time.sleep(0.02)
    return False


# ──────────────────────── Stuck detection ────────────────────────────────────

def _is_ctrl_stuck() -> tuple[bool, str]:
    """(stuck, detail). Kiểm 2 tầng: OS state và keyboard-lib internal state."""
    gaks = _u32.GetAsyncKeyState
    os_c  = bool(gaks(VK_CONTROL)  & 0x8000)
    os_rc = bool(gaks(VK_RCONTROL) & 0x8000)
    os_lc = bool(gaks(VK_LCONTROL) & 0x8000)
    kb_c  = False
    try:
        import keyboard as _kb
        kb_c = bool(_kb.is_pressed('ctrl'))
    except Exception:
        pass
    parts = (
        (["OS:VK_CTRL"]  if os_c  else []) +
        (["OS:VK_RCTRL"] if os_rc else []) +
        (["OS:VK_LCTRL"] if os_lc else []) +
        (["Lib:ctrl"]    if kb_c  else [])
    )
    return (os_c or os_rc or os_lc or kb_c), (",".join(parts) or "clean")


# ──────────────────────── Third-party hook detection ─────────────────────────

class _HookSpy:
    """Patch keyboard._listener.direct_callback để đếm re-entrant ctrl DOWN events.

    "Re-entrant" = sự kiện ctrl DOWN đến từ trong callback của chính nó,
    tức là một WH_KEYBOARD_LL hook khác (phần mềm bên thứ ba) phản ứng với
    ctrl DOWN của chúng ta và inject thêm ctrl DOWN vào OS.

    Dấu hiệu nhận biết: call stack chứa 'low_level_keyboard_handler' 2+ lần.
    """

    def __init__(self) -> None:
        self.ctrl_events: list[tuple] = []    # (event_type, scan_code, name, stack_frames)
        self.reentrant_downs: list[list[str]] = []  # stacks của re-entrant DOWN
        self._orig_dc = None
        self._active  = False

    def install(self, kb_module) -> None:
        lst = kb_module._listener
        KL  = type(lst)
        self._orig_dc = KL.direct_callback
        spy = self

        def _patched_dc(self_lst, event):
            if event.name and 'ctrl' in (event.name or '').lower():
                # Lấy call stack (không dùng traceback.print_stack để tránh I/O trong hook)
                frames = [f.name for f in _tb.extract_stack()]
                spy.ctrl_events.append(
                    (event.event_type, event.scan_code, event.name, frames)
                )
                # Đếm bao nhiêu lần 'low_level_keyboard_handler' xuất hiện trong stack
                hook_depth = frames.count('low_level_keyboard_handler')
                if event.event_type == 'down' and hook_depth >= 2:
                    spy.reentrant_downs.append(frames)
            return spy._orig_dc(self_lst, event)

        KL.direct_callback = _patched_dc
        self._active = True

    def uninstall(self, kb_module) -> None:
        if self._orig_dc and self._active:
            type(kb_module._listener).direct_callback = self._orig_dc
            self._active = False

    def third_party_detected(self) -> bool:
        return len(self.reentrant_downs) > 0

    def summary(self) -> str:
        total = len(self.ctrl_events)
        reent = len(self.reentrant_downs)
        lines = [
            f"  Tổng ctrl events nhận được: {total}",
            f"  Re-entrant ctrl DOWN (từ hook bên thứ ba): {reent}",
        ]
        if self.reentrant_downs:
            # Hiển thị stack ngắn gọn nhất
            sample = self.reentrant_downs[0]
            # Chỉ lấy phần liên quan (từ low_level_keyboard_handler)
            try:
                idx = next(i for i, f in enumerate(sample) if 'low_level' in f)
                short = " → ".join(sample[idx:idx+6])
            except StopIteration:
                short = " → ".join(sample[-6:])
            lines.append(f"  Stack mẫu: {short}")
        return "\n".join(lines)


def _enum_keyboard_hooks() -> list[str]:
    """Liệt kê các process đang có WH_KEYBOARD_LL hook (Windows 7+).

    Dùng NtQuerySystemInformation class 0x14 (SystemHandleInformation) hoặc
    đơn giản hơn: đọc danh sách từ User32 internal. Cách an toàn nhất là
    dùng EnumChildWindows... nhưng thực ra không có public API cho việc này.

    Thay vào đó, ta dùng heuristic: liệt kê tiến trình đang chạy và lọc
    những tiến trình khả nghi (bộ gõ tiếng Việt, gaming keyboard, macro tool).
    """
    suspicious_names = [
        # Bộ gõ tiếng Việt
        "unikey", "evkey", "gotiengviet", "winvnkey", "vietkey", "avim",
        # Gaming keyboard / macro
        "corsair", "logitech", "razer", "steelseries", "asus aura", "hyperx",
        "autohotkey", "ahk", "xmouse", "keypirinha", "hot corners",
        "karabiner", "vial", "qmk",
        # Antivirus / security (có thể hook kbd)
        "mbam", "malwarebytes", "kaspersky", "eset",
        # Accessibility
        "nvda", "jaws", "dragon",
    ]
    found: list[str] = []

    try:
        import ctypes
        import ctypes.wintypes as wt

        TH32CS_SNAPPROCESS = 0x2
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        class _PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize",              wt.DWORD),
                ("cntUsage",            wt.DWORD),
                ("th32ProcessID",       wt.DWORD),
                ("th32DefaultHeapID",   ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID",        wt.DWORD),
                ("cntThreads",          wt.DWORD),
                ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase",      ctypes.c_long),
                ("dwFlags",             wt.DWORD),
                ("szExeFile",           ctypes.c_char * 260),
            ]

        k32 = ctypes.windll.kernel32
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == INVALID_HANDLE_VALUE:
            return found

        pe = _PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(_PROCESSENTRY32)
        if k32.Process32First(snap, ctypes.byref(pe)):
            while True:
                name = pe.szExeFile.decode('utf-8', errors='replace').lower()
                for s in suspicious_names:
                    if s in name:
                        found.append(pe.szExeFile.decode('utf-8', errors='replace'))
                        break
                if not k32.Process32Next(snap, ctypes.byref(pe)):
                    break
        k32.CloseHandle(snap)
    except Exception:
        pass

    return found


# ──────────────────────────── Main diagnostic ────────────────────────────────

def _run_diagnostic(kb) -> tuple[bool, bool, "_HookSpy"]:
    """Chạy chuỗi test. Trả về (ctrl_stuck, third_party_found, spy)."""
    spy = _HookSpy()
    spy.install(kb)

    lst = kb._listener

    # ── Xác nhận cấu hình app ──
    bh_empty   = (len(lst.blocking_hotkeys) == 0)
    listen_ok  = getattr(lst, 'listening_thread',  None) and lst.listening_thread.is_alive()
    proc_ok    = getattr(lst, 'processing_thread', None) and lst.processing_thread.is_alive()
    print(f"  Listener threads: listen={'OK' if listen_ok else 'DEAD'}  "
          f"proc={'OK' if proc_ok else 'DEAD'}")
    print(f"  blocking_hotkeys empty: {bh_empty}"
          + (" [suppress=False OK]" if bh_empty else " [WARN: co suppress=True!]"))

    # ── Pre-check ──
    pre_stuck, pre_detail = _is_ctrl_stuck()
    if pre_stuck:
        print(f"  [WARN] Ctrl pre-stuck khi vào test [{pre_detail}] → force-release...")
        _force_release_ctrl()
        _wait_ctrl_clear(0.5)

    ctrl_stuck_any = False
    RUNS = 5

    # ── CA-1: LCtrl+Shift+F combo (x5) ──
    print(f"\n  Giai doan 1: LCtrl+Shift+F combo × {RUNS}...")
    fired_count = [0]
    # Lưu lại hotkeys hiện có và thêm callback đếm
    orig_ff = []
    try:
        kb.add_hotkey('ctrl+shift+f', lambda: orig_ff.append(1))
    except Exception:
        pass
    time.sleep(0.15)

    for i in range(RUNS):
        _force_release_ctrl()
        _wait_ctrl_clear(0.3)
        time.sleep(0.04)
        orig_ff.clear()

        _lctrl_dn(); time.sleep(0.02)
        _shift_dn(); time.sleep(0.02)
        _f_dn();     time.sleep(0.05)
        _f_up();     time.sleep(0.02)
        _shift_up(); time.sleep(0.02)
        _lctrl_up(); time.sleep(0.18)

        stuck, detail = _is_ctrl_stuck()
        fired = bool(orig_ff)
        marker = "." if not stuck else "F"
        print(f"    Run {i+1}: {'PASS' if not stuck else 'FAIL'} "
              f"stuck={stuck} fired={fired} [{detail}]")
        if stuck:
            ctrl_stuck_any = True
            _force_release_ctrl()
            _wait_ctrl_clear(0.3)

    # ── CA-2: RCtrl bare press (x3) ──
    print(f"\n  Giai doan 2: Right Ctrl bare press × 3...")
    for i in range(3):
        _force_release_ctrl()
        _wait_ctrl_clear(0.3)
        time.sleep(0.04)

        _rctrl_dn(); time.sleep(0.08)
        _rctrl_up(); time.sleep(0.15)

        try:
            kb_stuck = bool(kb.is_pressed('ctrl'))
        except Exception:
            kb_stuck = False
        _, os_detail = _is_ctrl_stuck()
        print(f"    Run {i+1}: {'PASS' if not kb_stuck else 'FAIL'} "
              f"lib_ctrl={kb_stuck} [{os_detail}]")
        if kb_stuck:
            ctrl_stuck_any = True
            _force_release_ctrl()
            _wait_ctrl_clear(0.3)

    spy.uninstall(kb)
    return ctrl_stuck_any, spy.third_party_detected(), spy


def main() -> None:
    SEP = "=" * 68

    print(SEP)
    print("  CONG CU CHAN DOAN: Ctrl BI KET — SnagTin QC Tool")
    print(SEP)
    print()
    print("CANH BAO: Script gia lap phim that qua keybd_event.")
    print("         KHONG cham ban phim hoac di chuot trong ~10 giay!")
    print()
    print("Dieu kien chay dung:")
    print("  - Windows desktop session (khong SSH, khong piped subprocess)")
    print("  - Chay tu cmd.exe / PowerShell, KHONG tu VS Code terminal")
    print("  - Nen dong bo got tieng Viet (Unikey/EVKey/GoTiengViet) truoc khi chay")
    print()

    # ── Platform check ──
    if sys.platform != "win32":
        print("LOI: Chi chay tren Windows.")
        sys.exit(2)

    # ── Import keyboard lib ──
    try:
        import keyboard
    except ImportError:
        print("LOI: pip install keyboard")
        sys.exit(2)

    # ── Enum suspicious processes ──
    print("[1/4] Quet tien trinh co the hook ban phim...")
    suspicious = _enum_keyboard_hooks()
    if suspicious:
        print(f"  CANH BAO: Phat hien {len(suspicious)} tien trinh kha nghi:")
        for p in suspicious:
            print(f"    - {p}")
        print("  Neu ket qua FAIL, hay thoat cac chuong trinh tren roi chay lai.")
    else:
        print("  Khong phat hien tien trinh hook ban phim kha nghi.")

    # ── Setup keyboard listener ──
    print()
    print("[2/4] Khoi dong keyboard listener (giong app)...")
    keyboard.add_hotkey('print screen',  lambda: None)
    keyboard.add_hotkey('ctrl+shift+f',  lambda: None)
    keyboard.add_hotkey('ctrl+shift+r',  lambda: None)
    time.sleep(0.4)
    print("  Done.")

    # ── Run diagnostic ──
    print()
    print("[3/4] Chay kiem tra (5 + 3 = 8 runs)...")
    ctrl_stuck = third_party = False
    spy = None

    try:
        ctrl_stuck, third_party, spy = _run_diagnostic(keyboard)
    finally:
        # ── CLEANUP BẮTBUỘC ──
        print()
        print("[4/4] Cleanup an toan...")
        for _ in range(3):
            _force_release_ctrl()
            time.sleep(0.04)
        try:
            keyboard.remove_all_hotkeys()
            keyboard.unhook_all()
        except Exception:
            pass
        print("  Force-released Ctrl. Xong.")

    # ──────────────────── VERDICT ────────────────────────────────────────────
    # NOTE: voi suppress=False (HK5), direct_callback chay tren processing thread,
    # KHONG phai hook thread → _HookSpy.third_party_detected() luon False.
    # Dung process enumeration lam indicator chinh xac hon.
    env_suspect = third_party or bool(suspicious)

    print()
    print(SEP)

    if not ctrl_stuck:
        # ── PASS ──
        print()
        print("  v Ctrl KHONG ket — app OK")
        print()
        if env_suspect and spy:
            print("  (Ghi chu: phat hien hook ben thu ba nhung Ctrl van clean.)")
            print(spy.summary())
        print(SEP)
        sys.exit(0)

    # ── FAIL ──
    print()
    print("  X Ctrl BI KET")
    print()

    if env_suspect:
        # Case (a): môi trường có hook bên thứ ba / bộ gõ tiếng Việt
        # NOTE: voi suppress=False, re-entrant detection qua call stack KHONG hoat dong
        # (direct_callback chay tren processing thread, khong phai hook thread).
        # Dung process enumeration lam indicator.
        print("  NGUYEN NHAN KHA DI NHAT: Co phan mem hook ban phim KHAC dang can thiep.")
        print()
        if suspicious:
            print("  Tien trinh dang chay co the gay ra:")
            for p in suspicious:
                print(f"    - {p}")
            print()
        if spy and spy.reentrant_downs:
            print("  Phan tich re-entrant (phat hien qua hook thread):")
            print(spy.summary())
            print()
        print("  >>> HANH DONG: THOAT bo got tieng Viet (Unikey/EVKey/GoTiengViet),")
        print("  >>>            gaming keyboard / macro tool, roi chay lai test.")
        print("  >>>            Neu van FAIL sau khi dong het chuong trinh tren -> bao developer.")
    else:
        # Case (b): stuck mà không có hook lạ
        print("  Khong phat hien hook ben thu ba.")
        print()
        print("  >>> LOI NAM TRONG APP. Bao lai developer voi thong tin:")
        if spy:
            print(spy.summary())
        # in _pressed_events hiện tại nếu có
        try:
            pe = {k: v.name for k, v in keyboard._pressed_events.items()}
            print(f"  keyboard._pressed_events: {pe}")
        except Exception:
            pass
        try:
            ms = dict(keyboard._listener.modifier_states)
            print(f"  modifier_states: {ms}")
        except Exception:
            pass

    print(SEP)
    sys.exit(1)


if __name__ == "__main__":
    main()
