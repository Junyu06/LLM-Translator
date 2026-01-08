import argparse
import socket

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from Foundation import NSObject
from PyObjCTools import AppHelper
import objc


def _send_message(port: int, token: str, message: str):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1) as sock:
            payload = f"{token}\n{message}\n".encode("utf-8")
            sock.sendall(payload)
    except Exception:
        pass


class _MenuHandler(NSObject):
    def initWithPort_token_(self, port, token):
        self = objc.super(_MenuHandler, self).init()
        if self is None:
            return None
        self._port = int(port)
        self._token = token
        return self

    def open_(self, sender):
        _send_message(self._port, self._token, "OPEN")

    def quit_(self, sender):
        _send_message(self._port, self._token, "QUIT")
        AppHelper.stopEventLoop()


def _set_agent_mode():
    try:
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


def run(port: int, token: str):
    _set_agent_mode()
    handler = _MenuHandler.alloc().initWithPort_token_(port, token)

    status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
    button = status_item.button()
    if button is not None:
        button.setTitle_("Translator")

    menu = NSMenu.alloc().init()
    item_open = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Open", "open:", "")
    item_open.setTarget_(handler)
    menu.addItem_(item_open)
    item_quit = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "quit:", "")
    item_quit.setTarget_(handler)
    menu.addItem_(item_quit)
    status_item.setMenu_(menu)

    AppHelper.runEventLoop()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    run(args.port, args.token)


if __name__ == "__main__":
    main()
