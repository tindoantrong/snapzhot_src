"""
verify_ctrl_stuck_fix.py — Xác minh CTRL-STUCK-FIX (Hướng A)

Mô phỏng ĐÚNG trạng thái app: đăng ký PrtScn bằng hook_key(suppress=True)
+ ctrl+shift+r bằng add_hotkey, rồi inject Right Ctrl DOWN+UP đơn lẻ,
kiểm chứng modifier_states KHÔNG kẹt pending.

Chạy: python scripts/verify_ctrl_stuck_fix.py
Không cần GUI/Qt. Chạy standalone.
"""

import sys
import os
import time
import ctypes
import threading

# Đảm bảo import từ project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import keyboard
except ImportError:
    print("SKIP: keyboard lib không có — cài pip install keyboard")
    sys.exit(0)

RCTRL_SC = 29  # scan code Right Ctrl (cũng là Left Ctrl — cùng scan code 29)

# ---------------------------------------------------------------------------
# Phần A: TRƯỚC FIX — mô phỏng cách cũ (add_hotkey suppress=True)
# Chứng minh trạng thái kẹt
# ---------------------------------------------------------------------------

def test_before_fix():
    """Cách cũ: add_hotkey PrtScn suppress=True → blocking_hotkeys non-empty → kẹt."""
    print("\n=== BEFORE FIX: add_hotkey(suppress=True) ===")
    keyboard.unhook_all()

    region_fired = []

    try:
        keyboard.add_hotkey(
            "print screen",
            lambda: region_fired.append(1),
            suppress=True,
        )
    except Exception as e:
        print(f"  add_hotkey PrtScn failed: {e}")
        return None

    try:
        keyboard.add_hotkey(
            "ctrl+shift+r",
            lambda: None,
        )
    except Exception as e:
        print(f"  add_hotkey ctrl+shift+r failed: {e}")

    listener = keyboard._listener
    fm = getattr(listener, 'filtered_modifiers', {})
    bh = getattr(listener, 'blocking_hotkeys', {})
    bk = getattr(listener, 'blocking_keys', {})

    print(f"  blocking_hotkeys non-empty: {bool(bh)}")
    print(f"  blocking_keys non-empty:    {bool(bk)}")
    print(f"  filtered_modifiers[ctrl=29]: {fm.get(RCTRL_SC, 0)}")
    print(f"  state machine will activate: {bool(bh) and fm.get(RCTRL_SC, 0) > 0}")

    # Inject Right Ctrl DOWN
    keyboard._os_keyboard.press(RCTRL_SC)
    time.sleep(0.05)

    ms_after_down = dict(getattr(listener, 'modifier_states', {}))
    pe_after_down = list(getattr(listener, '_pressed_events', {}).keys())
    print(f"  After RCTRL DOWN → modifier_states: {ms_after_down}")
    print(f"  After RCTRL DOWN → _pressed_events keys: {pe_after_down}")

    stuck_down = ms_after_down.get(RCTRL_SC) == 'pending'
    print(f"  Ctrl kẹt 'pending' sau DOWN: {'YES (EXPECTED BEFORE FIX)' if stuck_down else 'NO'}")

    # Inject Right Ctrl UP
    keyboard._os_keyboard.release(RCTRL_SC)
    time.sleep(0.1)

    ms_after_up = dict(getattr(listener, 'modifier_states', {}))
    pe_after_up = list(getattr(listener, '_pressed_events', {}).keys())
    print(f"  After RCTRL UP → modifier_states: {ms_after_up}")
    print(f"  After RCTRL UP → _pressed_events keys: {pe_after_up}")

    # Cleanup
    keyboard.unhook_all()
    # Giải phóng Ctrl nếu còn kẹt
    try:
        keyboard._os_keyboard.release(RCTRL_SC)
    except Exception:
        pass
    time.sleep(0.05)

    return stuck_down  # True = repro được kẹt


# ---------------------------------------------------------------------------
# Phần B: SAU FIX — hook_key(suppress=True)
# Chứng minh KHÔNG kẹt
# ---------------------------------------------------------------------------

def test_after_fix():
    """Cách mới: hook_key PrtScn suppress=True → blocking_keys, blocking_hotkeys RỖNG → không kẹt."""
    print("\n=== AFTER FIX: hook_key(suppress=True) ===")
    keyboard.unhook_all()

    region_fired = []

    try:
        def _region_hook(event):
            if event.event_type == keyboard.KEY_DOWN:
                region_fired.append(1)
            return False
        remove_hook = keyboard.hook_key("print screen", _region_hook, suppress=True)
    except Exception as e:
        print(f"  hook_key PrtScn failed: {e}")
        return None

    try:
        keyboard.add_hotkey(
            "ctrl+shift+r",
            lambda: None,
        )
    except Exception as e:
        print(f"  add_hotkey ctrl+shift+r failed: {e}")

    listener = keyboard._listener
    fm = getattr(listener, 'filtered_modifiers', {})
    bh = getattr(listener, 'blocking_hotkeys', {})
    bk = getattr(listener, 'blocking_keys', {})

    print(f"  blocking_hotkeys non-empty: {bool(bh)}")
    print(f"  blocking_keys non-empty:    {bool(bk)}")
    print(f"  filtered_modifiers[ctrl=29]: {fm.get(RCTRL_SC, 0)}")
    print(f"  state machine will activate: {bool(bh) and fm.get(RCTRL_SC, 0) > 0}")

    # Inject Right Ctrl DOWN
    keyboard._os_keyboard.press(RCTRL_SC)
    time.sleep(0.05)

    ms_after_down = dict(getattr(listener, 'modifier_states', {}))
    pe_after_down = list(getattr(listener, '_pressed_events', {}).keys())
    print(f"  After RCTRL DOWN → modifier_states: {ms_after_down}")
    print(f"  After RCTRL DOWN → _pressed_events keys: {pe_after_down}")

    stuck_down = ms_after_down.get(RCTRL_SC) == 'pending'
    print(f"  Ctrl kẹt 'pending' sau DOWN: {'YES' if stuck_down else 'NO (EXPECTED AFTER FIX)'}")

    # Inject Right Ctrl UP
    keyboard._os_keyboard.release(RCTRL_SC)
    time.sleep(0.1)

    ms_after_up = dict(getattr(listener, 'modifier_states', {}))
    pe_after_up = list(getattr(listener, '_pressed_events', {}).keys())
    print(f"  After RCTRL UP → modifier_states: {ms_after_up}")
    print(f"  After RCTRL UP → _pressed_events keys: {pe_after_up}")

    clean = RCTRL_SC not in ms_after_up or ms_after_up.get(RCTRL_SC) == 'free'

    # Verify PrtScn vẫn gọi callback
    prtscn_sc = keyboard.key_to_scan_codes("print screen")[0]
    keyboard._os_keyboard.press(prtscn_sc)
    time.sleep(0.05)
    keyboard._os_keyboard.release(prtscn_sc)
    time.sleep(0.05)
    prtscn_fired = len(region_fired) > 0
    print(f"  PrtScn callback fired: {'YES' if prtscn_fired else 'NO'}")

    # Cleanup
    try:
        remove_hook()
    except Exception:
        pass
    keyboard.unhook_all()
    try:
        keyboard._os_keyboard.release(RCTRL_SC)
    except Exception:
        pass
    time.sleep(0.05)

    return clean, prtscn_fired


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Cần admin để inject keys
    if sys.platform == "win32":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
        if not is_admin:
            print("WARN: Không phải admin — inject key có thể không hoạt động đúng.")

    print("=" * 60)
    print("CTRL-STUCK-FIX Verification Script")
    print("=" * 60)

    before_stuck = test_before_fix()
    time.sleep(0.2)

    after_result = test_after_fix()
    time.sleep(0.2)

    print("\n" + "=" * 60)
    print("KẾT QUẢ:")
    print(f"  BEFORE fix — Ctrl kẹt 'pending': {before_stuck}")
    if after_result is not None:
        clean, prtscn_ok = after_result
        print(f"  AFTER  fix — Ctrl clean (không kẹt): {clean}")
        print(f"  AFTER  fix — PrtScn callback gọi được: {prtscn_ok}")
        if before_stuck and clean and prtscn_ok:
            print("\n  VERDICT: PASS — Fix hoạt động đúng (trước kẹt, sau không kẹt, PrtScn OK)")
        elif before_stuck is False:
            print("\n  WARN: Không repro được kẹt TRƯỚC fix — có thể môi trường không inject được")
        else:
            print("\n  FAIL — Xem chi tiết trên")
    else:
        print("  AFTER fix test bị lỗi — xem traceback")
    print("=" * 60)
