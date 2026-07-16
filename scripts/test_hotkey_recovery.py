"""test_hotkey_recovery.py — kiểm chứng cơ chế khôi phục hotkey v3 (headless).

Không cần nhấn phím thật / QApplication. Test trực tiếp keyboard._listener internals.
Logic trong các hàm helper mirror đúng logic AppController:
  _restart_proc()   ↔  AppController._restart_processing_thread()
  _restart_listen() ↔  AppController._hard_restart_keyboard_listener()
  _emit_safe_impl() ↔  AppController._emit_safe()

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
# Helper: mirror AppController._restart_listening_thread_if_dead (HK4 — không WM_QUIT)
# ---------------------------------------------------------------------------
def _restart_listen(lst) -> tuple[bool, str]:
    """Guard + start new listening_thread khi old đã chết — không WM_QUIT, không dead window.

    Mirror AppController._restart_listening_thread_if_dead (HK4): loại bỏ hoàn toàn
    PostThreadMessageW → không tạo cửa sổ chết nuốt key-UP modifier.
    """
    old = getattr(lst, "listening_thread", None)
    if old is not None and old.is_alive():
        return False, "ABORT: old listening_thread còn sống"
    t = threading.Thread(target=lst.listen, daemon=True)
    lst.listening_thread = t
    t.start()
    return True, "ok (không WM_QUIT)"


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
# CA 2: listening_thread chết → khôi phục
# ===========================================================================
print("\n=== CA 2: listening_thread chết → khôi phục ===")

_lt_now = getattr(lst, "listening_thread", None)
if _lt_now is None or not _lt_now.is_alive():
    skip("CA2 bỏ qua: listening_thread không sống (thiếu quyền SetWindowsHookEx?)")
else:
    orig_listen = lst.listening_thread
    check(orig_listen.is_alive(), "2.0  listening_thread đang sống trước khi kill")

    native = getattr(orig_listen, "native_id", None)
    if native is None:
        skip("CA2 bỏ qua: native_id không có (Python < 3.8?)")
    else:
        # Kill qua WM_QUIT → GetMessage loop trong listen() thoát → thread kết thúc
        WM_QUIT = 0x0012
        ctypes.windll.user32.PostThreadMessageW(native, WM_QUIT, 0, 0)
        orig_listen.join(timeout=2.0)

        check(not orig_listen.is_alive(),
              "2.1  listening_thread đã chết sau WM_QUIT + join(2s)")

        # Khôi phục
        ok2, info2 = _restart_listen(lst)
        check(ok2, f"2.2  _restart_listen trả True ({info2})")
        time.sleep(0.5)

        new_listen = lst.listening_thread
        check(new_listen is not orig_listen,
              "2.3  listening_thread là object mới")
        check(new_listen is not None and new_listen.is_alive(),
              "2.4  listening_thread mới đang sống")

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

# 3b: listening_thread còn sống → _restart_listen phải abort
_lt_now = lst.listening_thread
if _lt_now is None or not _lt_now.is_alive():
    skip("3b bỏ qua: listening_thread không sống hiện tại")
else:
    thread_ref_before_l = lst.listening_thread
    ok3b, info3b = _restart_listen(lst)
    check(not ok3b,
          f"3b  guard abort khi listening_thread còn sống (ok={ok3b}, '{info3b}')")
    check(lst.listening_thread is thread_ref_before_l,
          "3b  listening_thread KHÔNG bị thay thế")

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

# CA 5 (HK3 stuck modifier clear): đã xóa — _hard_restart_keyboard_listener bị bỏ
# hoàn toàn ở HK4; logic clear-modifier không còn tồn tại và không còn cần thiết
# vì không còn dead-window nuốt key-UP (bỏ periodic reinstall là fix tận gốc).

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
