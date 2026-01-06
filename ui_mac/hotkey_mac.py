import time
from Quartz import (
    CGEventTapCreate,
    CGEventTapEnable,
    CGEventTapIsEnabled,
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    CFMachPortCreateRunLoopSource,
    kCFRunLoopCommonModes,
    kCGEventKeyDown,
    kCGEventTapOptionDefault,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGKeyboardEventKeycode,
)
from Quartz import kCGEventFlagMaskCommand

try:
    from Quartz import kCGEventMaskBit  # type: ignore
    _event_mask_bit = kCGEventMaskBit
except Exception:
    from Quartz import CGEventMaskBit  # type: ignore
    _event_mask_bit = CGEventMaskBit

# mac keycode for 'c' (US layout): 8
KEYCODE_C = 8

class DoubleCmdCListener:
    def __init__(self, on_trigger, interval_sec=0.35):
        self.on_trigger = on_trigger
        self.interval = interval_sec
        self._last_cmd_c_time = 0.0

    def _callback(self, proxy, event_type, event, refcon):
        try:
            if event_type != kCGEventKeyDown:
                return event

            flags = CGEventGetFlags(event)
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)

            if keycode == KEYCODE_C and (flags & kCGEventFlagMaskCommand):
                now = time.time()
                if now - self._last_cmd_c_time <= self.interval:
                    self._last_cmd_c_time = 0.0
                    self.on_trigger()
                else:
                    self._last_cmd_c_time = now

            return event
        except Exception:
            return event

    def run(self):
        mask = _event_mask_bit(kCGEventKeyDown)
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            mask,
            self._callback,
            None
        )
        if tap is None:
            raise RuntimeError(
                "Failed to create event tap. "
                "You likely need to grant Accessibility/Input Monitoring permissions."
            )

        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
        CGEventTapEnable(tap, True)
        CFRunLoopRun()
