"""Capturing through Cinnamon's own screenshot service (xlcheese/xl-screenshot#10).

Cinnamon is the window manager, so it can capture the screen, a window or an
area on X11 and on Wayland alike, and it has its own window picker (the
screen dims and the window under the pointer is lifted) and area selector.
It listens on D-Bus as org.cinnamon.Screenshot; newer Cinnamon versions have
all the methods used here. Every call is asynchronous, so nothing here can
make xl-Screenshot hang: each one ends by calling its callback, with None
when the capture failed or was cancelled.
"""

import itertools
import os

from gi.repository import Gio, GLib, GdkPixbuf

BUS_NAME = "org.cinnamon.Screenshot"
OBJECT_PATH = "/org/cinnamon/Screenshot"
INTERFACE = "org.cinnamon.Screenshot"

# What xl-Screenshot needs from the service
NEEDED = {"Screenshot", "ScreenshotArea", "ScreenshotWindowById", "SelectWindow", "SelectArea"}

CAPTURE_TIMEOUT_MS = 30000     # taking a picture; picking (SelectWindow/SelectArea) waits for the user

_counter = itertools.count()


def _is_cancel(error):
    return error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED) or \
        "cancel" in (error.message or "").lower()


class CinnamonScreenshot:
    """The service, if this desktop has it with everything we need."""

    def __init__(self, proxy, methods):
        self._proxy = proxy
        self.methods = methods
        # Command-line captures: Cinnamon also puts each capture on the
        # clipboard, where it stays after we exit (a windowless program
        # can't own the clipboard on Wayland). copied: the last one was.
        self.copy_captures = False
        self.copied = False

    @classmethod
    def find(cls, bus=None, timeout_ms=1500):
        """The service, or None if it isn't running or lacks a method we use."""
        try:
            bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION, None)
            reply = bus.call_sync(BUS_NAME, OBJECT_PATH, "org.freedesktop.DBus.Introspectable",
                                  "Introspect", None, GLib.VariantType("(s)"),
                                  Gio.DBusCallFlags.NONE, timeout_ms, None)
            info = Gio.DBusNodeInfo.new_for_xml(reply.unpack()[0]).lookup_interface(INTERFACE)
            if info is None:
                return None
            methods = {m.name for m in info.methods}
            if not NEEDED <= methods:
                return None
            proxy = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
                                           Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
                                           info, BUS_NAME, OBJECT_PATH, INTERFACE, None)
            return cls(proxy, methods)
        except GLib.Error:
            return None

    # ---- the calls ----

    def _tempfile(self):
        folder = GLib.get_user_runtime_dir() or GLib.get_tmp_dir()
        return os.path.join(folder, f"xl-screenshot-{os.getpid()}-{next(_counter)}.png")

    def _call(self, method, params, timeout_ms, on_reply):
        """on_reply(values) with the unpacked reply, or on_reply(None) on a
        failure or a cancel."""
        def done(proxy, result):
            try:
                values = proxy.call_finish(result).unpack()
            except GLib.Error as e:
                if not _is_cancel(e):
                    print(f"Cinnamon screenshot service: {method} failed: {e.message}")
                values = None
            on_reply(values)
        self._proxy.call(method, params, Gio.DBusCallFlags.NONE, timeout_ms, None, done)

    def _capture(self, method, args, signature, on_done, copy=None):
        """Calls a capture method that writes a PNG file, and hands back the picture."""
        path = self._tempfile()
        copy = self.copy_captures if copy is None else copy
        params = GLib.Variant(signature, tuple(args) + (path, copy))

        def reply(values):
            pixbuf = None
            if values and values[0]:
                self.copied = copy
                used = values[1] or path
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(used)
                except GLib.Error as e:
                    print(f"Could not read the screenshot: {e.message}")
                for leftover in {used, path}:
                    try:
                        os.unlink(leftover)
                    except OSError:
                        pass
            on_done(pixbuf)
        self._call(method, params, CAPTURE_TIMEOUT_MS, reply)

    def screenshot(self, include_pointer, on_done, copy=None):
        """The whole desktop. copy=False: never to the clipboard (the still
        picture Selection is drawn over)."""
        self._capture("Screenshot", (include_pointer,), "(bsb)", on_done, copy)

    def screenshot_area(self, x, y, w, h, include_pointer, on_done):
        """A rectangle, in desktop units (as SelectArea gives them)."""
        self._capture("ScreenshotArea", (x, y, w, h, include_pointer), "(iiiibsb)", on_done)

    def screenshot_window(self, window_id, include_shadow, include_pointer, on_done):
        """One window's own picture: clean rounded corners, shadow if asked."""
        self._capture("ScreenshotWindowById", (window_id, include_shadow, include_pointer),
                      "(tbbsb)", on_done)

    def screenshot_focused_window(self, include_shadow, include_pointer, on_done):
        """The window that has the focus (older Cinnamon versions may lack it)."""
        if "ScreenshotWindow" not in self.methods:
            on_done(None)
            return
        self._capture("ScreenshotWindow", (include_shadow, include_pointer), "(bbsb)", on_done)

    def select_window(self, on_done):
        """Cinnamon's window picker. on_done(window_id), or None if cancelled."""
        self._call("SelectWindow", None, -1, lambda v: on_done(v[0] if v else None))

    def select_area(self, on_done):
        """Cinnamon's area selector. on_done((x, y, w, h)), or None if cancelled."""
        self._call("SelectArea", None, -1,
                   lambda v: on_done(tuple(v) if v and v[2] > 0 and v[3] > 0 else None))


def session_is_wayland():
    """True in a Wayland session: then the X11 ways of capturing don't work."""
    from gi.repository import Gdk
    display = Gdk.Display.get_default()
    if display is not None and type(display).__name__.startswith("GdkWayland"):
        return True
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" and display is None
