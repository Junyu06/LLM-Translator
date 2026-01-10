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
    from Quartz import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
except Exception:
    AXIsProcessTrustedWithOptions = None
    kAXTrustedCheckOptionPrompt = None

try:
    from Quartz import kCGEventMaskBit  # type: ignore
    _event_mask_bit = kCGEventMaskBit
except Exception:
    from Quartz import CGEventMaskBit  # type: ignore
    _event_mask_bit = CGEventMaskBit

# mac keycode for 'c' (US layout): 8
KEYCODE_C = 8


def ensure_accessibility(prompt: bool = True) -> bool:
    if AXIsProcessTrustedWithOptions is None:
        return True
    options = {}
    if prompt and kAXTrustedCheckOptionPrompt is not None:
        options = {kAXTrustedCheckOptionPrompt: True}
    try:
        return bool(AXIsProcessTrustedWithOptions(options))
    except Exception:
        return False

class DoubleCmdCListener:
    def __init__(self, on_trigger, interval_sec=0.35):
        self.on_trigger = on_trigger
        self.interval = interval_sec
        self._last_cmd_c_time = 0.0
        self._tap = None
        self._source = None

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

    def install(self):
        if AXIsProcessTrustedWithOptions is not None and kAXTrustedCheckOptionPrompt is not None:
            try:
                if not AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
                    raise RuntimeError(
                        "Accessibility permission is required for the hotkey."
                    )
            except Exception:
                pass
        self._install_quartz()

    def _install_quartz(self):
        mask = _event_mask_bit(kCGEventKeyDown)
        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            mask,
            self._callback,
            None
        )
        if self._tap is None:
            raise RuntimeError(
                "Failed to create event tap. "
                "You likely need to grant Accessibility/Input Monitoring permissions."
            )

        self._source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), self._source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)

    def run(self):
        self.install()
        if self._tap is not None:
            CFRunLoopRun()
