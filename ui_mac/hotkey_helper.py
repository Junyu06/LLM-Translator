import argparse
import os
import socket
import sys
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ui_mac.hotkey_mac import DoubleCmdCListener  # noqa: E402


def _set_agent_mode():
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


def run(port: int, token: str):
    _set_agent_mode()
    def on_trigger():
        nonlocal sock
        try:
            sock.sendall(b"TRIGGER\n")
        except Exception:
            pass

    while True:
        try:
            sock = socket.create_connection(("127.0.0.1", port))
            sock.sendall((token + "\n").encode("utf-8"))
        except Exception:
            time.sleep(0.5)
            continue
        listener = DoubleCmdCListener(on_trigger=on_trigger)
        try:
            listener.run()
        except Exception:
            time.sleep(0.5)
        finally:
            try:
                sock.close()
            except Exception:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    run(args.port, args.token)


if __name__ == "__main__":
    main()
