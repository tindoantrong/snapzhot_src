"""test_hotkey_recovery.py — kiểm chứng cơ chế khôi phục hotkey (headless).

Không cần nhấn phím thật / QApplication. Test trực tiếp keyboard._listener internals.
Logic trong các hàm helper mirror đúng logic AppController:
  _restart_proc()   ↔  AppController._restart_processing_thread()
  _emit_safe_impl() ↔  AppController._emit_safe()

Ghi chú: CA2 và CA3-3b (test _restart_listen / listening_thread recovery) đã
chuyển sang SKIP — cơ chế hard-restart listening_thread (_hard_restart_keyboard_listener,
HK4) đã bị bỏ khỏi AppController theo quyết định USER 2026-07-17.

Exit code 0 = tất cả PASS, exit code 1 = có FAIL.
"""
import _bootstrap  # noqa: F401  (sys.path + UTF-8)

import ctypes
import logging
import queue as _queue_mod
import sys
import threading
import time

logging.basicConfig(level=logging.WARNING,
                    format="%(levelname)s %(name)s: %(message)s")
_log = logging.getLogger("test_hotkey_recovery")

_PASS = 0
_FAIL = 0


def check(cond: bool, label: str) -> bool:
    global _PASS, _FAIL
    if cond:
        print(f"  PASS  {label}")
        _PASS += 1
    else:
        print(f"  FAIL  {label}")
        _FAIL += 1
    return bool(cond)


def skip(label: str) -> None:
    print(f"  SKIP  {label}")


# ---------------------------------------------------------------------------
# Helper: mirror AppController._restart_processing_thread
# ---------------------------------------------------------------------------
def _restart_proc(lst) -> tuple[bool, str]:
    """Guard + drain + start new processing_thread. Returns (ok, info)."""
    old = getattr(lst, "processing_thread", None)
    if old is not None and old.is_alive():
        return False, "ABORT: old processing_thread còn sống"
    drained = 0
    try:
        while True:
            lst.queue.get_nowait()
            lst.queue.task_done()
            drained += 1
    except _queue_mod.Empty:
        pass
    except Exception as ex:
        return False, f"drain error: {ex}"
    t = threading.Thread(target=lst.process, daemon=True)
    lst.processing_thread = t
    t.start()
    return True, f"drained={drained}"


# ---------------------------------------------------------------------------
# Helper: _restart_listen — HK4 ĐÃ GỠ, chỉ giữ lại để CA2/CA3-3b tham chiếu
# (không còn mirror AppController vì _hard_restart_keyboard_listener đã xóa)
# ---------------------------------------------------------------------------
def _restart_listen(lst) -> tuple[bool, str]:
    """Guard + start new listening_thread (cơ chế HK4, không còn trong AppController)."""
    old = getattr(lst, "listening_thread", None)
    if old is not None and old.is_alive():
        return False, "ABORT: old listening_thread còn sống"
    t = threading.Thread(target=lst.listen, daemon=True)
    lst.listening_thread = t
    t.start()
    return True, "ok"


# ---------------------------------------------------------------------------
# Helper: mirror AppController._emit_safe
# ---------------------------------------------------------------------------
def _emit_safe_impl(signal) -> None:
    try:
        signal.emit()
    except Exception:
        _log.exception("[test] signal.emit() ném exception — đã chặn")


# ---------------------------------------------------------------------------
# Import keyboard + start listener
# ---------------------------------------------------------------------------
try:
    import keyboard
except ImportError:
    print("FATAL: thư viện keyboard không cài — dừng test.")
    sys.exit(1)

lst = keyboard._listener

# Start listener (cả 2 thread: listening + processing)
_dummy_hook = keyboard.hook(lambda e: None)
time.sleep(0.4)

# Kiểm tra trạng thái ban đầu
_lt_init = getattr(lst, "listening_thread", None)
_pt_init = getattr(lst, "processing_thread", None)
_lt_alive_init = _lt_init is not None and _lt_init.is_alive()
_pt_alive_init = _pt_init is not None and _pt_init.is_alive()
print(f"[setup] listening_thread={'alive' if _lt_alive_init else 'DEAD'}"
      f"  processing_thread={'alive' if _pt_alive_init else 'DEAD'}")

# ===========================================================================
# CA 1: processing_thread chết → khôi phục + xử lý event
# ===========================================================================
print("\n=== CA 1: processing_thread chết → khôi phục ===")

if not _pt_alive_init:
    skip("CA1 bỏ qua: processing_thread không sống ngay từ đầu")
    _FAIL += 1
else:
    orig_proc = lst.processing_thread
    check(orig_proc.is_alive(), "1.0  processing_thread đang sống trước khi kill")

    # Đăng ký handler đếm — persist qua restart (lst.handlers không bị xoá)
    counter = 0
    def _counting_handler(event):
        global counter
        counter += 1
        return False  # không chặn event

    keyboard.hook(_counting_handler)

    # ---- Giả lập chết: inject object không có scan_code ----
    # pre_process_event() tại dòng:
    #   for key_hook in self.nonblocking_keys[event.scan_code]:
    # → AttributeError: 'object' has no attribute 'scan_code'
    # → propagate lên process() (không có try/except) → thread chết.
    class _BadEvent:
        pass  # không có scan_code, name, v.v.

    lst.queue.put(_BadEvent())

    # Poll chờ thread chết (tối đa 3 s)
    deadline = time.time() + 3.0
    while time.time() < deadline and orig_proc.is_alive():
        time.sleep(0.05)

    if not check(not orig_proc.is_alive(),
                 "1.1  processing_thread đã chết sau khi inject bad event"):
        # Nếu thread không chết (bộ thư viện khác nhau?) → thử tiếp
        print("       (có thể phiên bản keyboard không match — tiếp tục)")

    # ---- Khôi phục ----
    ok1, info1 = _restart_proc(lst)
    check(ok1, f"1.2  _restart_proc trả True ({info1})")
    time.sleep(0.2)

    new_proc = lst.processing_thread
    check(new_proc is not orig_proc,
          "1.3  processing_thread là object mới (không phải old thread)")
    check(new_proc is not None and new_proc.is_alive(),
          "1.4  processing_thread mới đang sống")

    # ---- Chứng minh thread mới drain queue + gọi handler ----
    counter_before = counter

    # Tạo event hợp lệ để put vào queue
    _evt = None
    try:
        _evt = keyboard.KeyboardEvent(
            event_type=keyboard.KEY_DOWN,
            scan_code=57,   # Space
            name="space",
            is_keypad=False,
        )
    except Exception:
        pass
    if _evt is None:
        # Fallback: struct tối giản khớp pre_process_event
        class _MinEvent:
            scan_code = 57
            name = "space"
            event_type = "down"
            is_keypad = False
            device = None
            modifiers = None
            time = None
        _evt = _MinEvent()

    lst.queue.put(_evt)
    time.sleep(0.4)  # cho processing_thread kịp drain

    check(counter > counter_before,
          f"1.5  handler được gọi sau restart (counter {counter_before}→{counter})")

# ===========================================================================
# CA 2: listening_thread recovery — SKIP (HK4 đã gỡ khỏi AppController)
# ===========================================================================
print("\n=== CA 2: listening_thread recovery [SKIP — HK4 removed] ===")
skip("2.0  listening_thread chết → khôi phục [HK4 (_hard_restart_keyboard_listener) đã bỏ]")
skip("2.1-2.4  [HK4 removed — listening_thread restart không còn trong AppController]")

# ===========================================================================
# CA 3: Guard chống thread trùng
# ===========================================================================
print("\n=== CA 3: Guard chống thread trùng ===")

# 3a: processing_thread còn sống → _restart_proc phải abort
_pt_now = lst.processing_thread
if _pt_now is None or not _pt_now.is_alive():
    skip("3a bỏ qua: processing_thread không sống hiện tại")
else:
    thread_ref_before = lst.processing_thread
    ok3a, info3a = _restart_proc(lst)
    check(not ok3a,
          f"3a  guard abort khi processing_thread còn sống (ok={ok3a}, '{info3a}')")
    check(lst.processing_thread is thread_ref_before,
          "3a  processing_thread KHÔNG bị thay thế")

# 3b: listening_thread guard — SKIP (HK4 đã gỡ, _restart_listen không còn dùng trong app)
skip("3b  guard abort listening_thread [HK4 removed — _restart_listen không còn trong AppController]")

# ===========================================================================
# CA 4: _emit_safe nuốt exception, không propagate
# ===========================================================================
print("\n=== CA 4: _emit_safe nuốt exception ===")

class _BrokenSignal:
    def emit(self):
        raise RuntimeError("intentional test exception in emit()")

class _GoodSignal:
    called = False
    def emit(self):
        _GoodSignal.called = True

# _emit_safe không được propagate exception
propagated = False
try:
    _emit_safe_impl(_BrokenSignal())
except Exception:
    propagated = True
check(not propagated, "4.1  _emit_safe nuốt RuntimeError từ broken signal — không propagate")

# _emit_safe vẫn gọi emit() trên signal bình thường
_emit_safe_impl(_GoodSignal())
check(_GoodSignal.called, "4.2  _emit_safe gọi emit() trên signal bình thường")

# ===========================================================================
# CA 5: stuck modifier clear algorithm — headless, standalone.
#        Logic này từng nằm trong _hard_restart_keyboard_listener (HK3-FIX);
#        HK4 đã gỡ nhưng thuật toán clear vẫn hợp lệ và được test riêng qua
#        _hk3_clear_stuck_modifiers. Không cần OS hook thật, không cần bàn phím.
# ===========================================================================
print("\n=== CA 5: stuck modifier clear algorithm (headless) ===")


class _FakeKeyEvent:
    """Event object tối giản khớp giao diện keyboard.KeyboardEvent."""
    def __init__(self, name: str, scan_code: int):
        self.name = name
        self.scan_code = scan_code
        self.event_type = "down"
        self.is_keypad = False
        self.device = None
        self.modifiers = None
        self.time = None


def _hk3_clear_stuck_modifiers(kb_mod, lst_mod) -> list[int]:
    """Thuật toán clear stuck-modifier (trích từ HK3-FIX, standalone).

    Tách thành hàm để test gọi trực tiếp mà không cần restart OS hook.
    Trả về danh sách scan_code đã xóa (để assert).
    """
    stale = []
    with kb_mod._pressed_events_lock:
        stale = [
            sc for sc, ev in list(kb_mod._pressed_events.items())
            if getattr(ev, "name", "") in kb_mod.all_modifiers
        ]
        for sc in stale:
            kb_mod._pressed_events.pop(sc, None)
    lst_mod.modifier_states.clear()
    return stale


try:
    # -- Lấy scan_code thực của ctrl, shift, a từ keyboard lib --
    def _first_sc(key_name: str, fallback: int) -> int:
        try:
            codes = keyboard.key_to_scan_codes(key_name, error_if_missing=False)
            return codes[0] if codes else fallback
        except Exception:
            return fallback

    ctrl_sc  = _first_sc("ctrl",  29)   # thường = 29 (left ctrl)
    shift_sc = _first_sc("shift", 42)   # thường = 42 (left shift)
    a_sc     = _first_sc("a",     30)   # thường = 30

    # Đảm bảo 3 scan_code không trùng (tránh inject chồng nhau)
    if len({ctrl_sc, shift_sc, a_sc}) != 3:
        skip("CA5: 3 scan_code không phân biệt — bỏ qua")
    else:
        # -- Inject 2 modifier stuck + 1 phím thường --
        with keyboard._pressed_events_lock:
            keyboard._pressed_events[ctrl_sc]  = _FakeKeyEvent("ctrl",  ctrl_sc)
            keyboard._pressed_events[shift_sc] = _FakeKeyEvent("shift", shift_sc)
            keyboard._pressed_events[a_sc]     = _FakeKeyEvent("a",     a_sc)

        keyboard._listener.modifier_states = {"ctrl": "allowed", "shift": "free"}

        # Xác nhận trạng thái "stuck" đã inject thành công
        check(keyboard.is_pressed("ctrl"),
              "5.0  ctrl inject → is_pressed('ctrl') = True (giả lập stuck)")
        check(keyboard.is_pressed("shift"),
              "5.0b shift inject → is_pressed('shift') = True")

        # -- Chạy đúng đoạn clear-stuck-modifier của HK3-FIX --
        cleared = _hk3_clear_stuck_modifiers(keyboard, keyboard._listener)

        # -- Assert kết quả --
        check(not keyboard.is_pressed("ctrl"),
              "5.1  is_pressed('ctrl') = False sau clear (stuck modifier đã giải phóng)")
        check(not keyboard.is_pressed("shift"),
              "5.2  is_pressed('shift') = False sau clear")
        check(a_sc in keyboard._pressed_events,
              "5.3  phím 'a' (non-modifier) VẪN còn trong _pressed_events")
        check(keyboard._listener.modifier_states == {},
              "5.4  modifier_states rỗng hoàn toàn sau clear")
        check(len(cleared) == 2,
              f"5.5  đúng 2 modifier scan_code bị xóa (ctrl+shift) — got {len(cleared)}")
        check(ctrl_sc in cleared and shift_sc in cleared,
              f"5.6  ctrl_sc={ctrl_sc} và shift_sc={shift_sc} đều nằm trong cleared={cleared}")

        # -- Dọn phím 'a' còn lại (không để dơ state cho test khác) --
        with keyboard._pressed_events_lock:
            keyboard._pressed_events.pop(a_sc, None)

        check(a_sc not in keyboard._pressed_events,
              "5.7  cleanup: 'a' đã dọn sau test (state sạch)")

except Exception as _ca5_err:
    _FAIL += 1
    print(f"  FAIL  CA5 lỗi không mong muốn: {_ca5_err!r}")


# ===========================================================================
# Dọn dẹp + summary
# ===========================================================================
print()
try:
    keyboard.unhook_all()
except Exception:
    pass

print(f"=== KẾT QUẢ: {_PASS} PASS, {_FAIL} FAIL ===")
if _FAIL == 0:
    print("=== TẤT CẢ CA PASS — cơ chế khôi phục v3 hoạt động đúng ===")
    sys.exit(0)
else:
    print("=== CÓ CA FAIL — xem chi tiết ở trên ===")
    sys.exit(1)
