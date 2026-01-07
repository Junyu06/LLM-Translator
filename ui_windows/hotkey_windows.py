import time

try:
    import keyboard
except Exception:  # noqa: BLE001 - optional dependency
    keyboard = None


class DoubleCtrlCListener:
    def __init__(self, on_trigger, interval_sec=0.35):
        self.on_trigger = on_trigger
        self.interval = interval_sec
        self._last_ctrl_c_time = 0.0

    def _callback(self, event):
        if event.event_type != "down":
            return
        if event.name != "c":
            return
        if keyboard is None or not keyboard.is_pressed("ctrl"):
            return

        now = time.time()
        if now - self._last_ctrl_c_time <= self.interval:
            self._last_ctrl_c_time = 0.0
            self.on_trigger()
        else:
            self._last_ctrl_c_time = now

    def run(self):
        if keyboard is None:
            raise RuntimeError("keyboard module is not available.")
        keyboard.hook(self._callback)
        keyboard.wait()
