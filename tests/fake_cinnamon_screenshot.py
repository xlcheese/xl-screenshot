"""A stand-in for Cinnamon's screenshot service (org.cinnamon.Screenshot),
for the tests: same methods, answers with test pictures, and logs each call.

    python3 fake_cinnamon_screenshot.py LOGFILE [ok|cancel|old]

ok      every call succeeds: Screenshot 1280x800 (left half red, right blue), a window 300x200 (340x240
        with its shadow), SelectWindow picks window 77, SelectArea 10,20 300x150
cancel  SelectWindow and SelectArea are cancelled, as when Esc is pressed
old     an older Cinnamon: no SelectWindow or ScreenshotWindowById
"""
import json, sys
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gio, GLib, GdkPixbuf

log_path, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "ok")
METHODS = {
    "ScreenshotArea": "<arg type='i' direction='in'/><arg type='i' direction='in'/><arg type='i' direction='in'/><arg type='i' direction='in'/><arg type='b' direction='in'/><arg type='s' direction='in'/><arg type='b' direction='in'/><arg type='b' direction='out'/><arg type='s' direction='out'/>",
    "ScreenshotWindow": "<arg type='b' direction='in'/><arg type='b' direction='in'/><arg type='s' direction='in'/><arg type='b' direction='in'/><arg type='b' direction='out'/><arg type='s' direction='out'/>",
    "ScreenshotWindowById": "<arg type='t' direction='in'/><arg type='b' direction='in'/><arg type='b' direction='in'/><arg type='s' direction='in'/><arg type='b' direction='in'/><arg type='b' direction='out'/><arg type='s' direction='out'/>",
    "Screenshot": "<arg type='b' direction='in'/><arg type='s' direction='in'/><arg type='b' direction='in'/><arg type='b' direction='out'/><arg type='s' direction='out'/>",
    "SelectArea": "<arg type='i' direction='out'/><arg type='i' direction='out'/><arg type='i' direction='out'/><arg type='i' direction='out'/>",
    "SelectWindow": "<arg type='t' direction='out'/>",
}
if mode == "old":
    for m in ("SelectWindow", "ScreenshotWindowById"):
        del METHODS[m]
XML = "<node><interface name='org.cinnamon.Screenshot'>" + "".join(
    f"<method name='{n}'>{a}</method>" for n, a in METHODS.items()) + "</interface></node>"

def picture(path, w, h, rgba=0x3366ccff):
    p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, w, h); p.fill(rgba); p.savev(path, "png", [], [])

def log(name, args):
    with open(log_path, "a") as f:
        f.write(json.dumps([name, list(args)]) + "\n")

def handle(conn, sender, path, iface, method, params, inv):
    args = params.unpack()
    log(method, args)
    cancel = lambda: inv.return_dbus_error("org.freedesktop.DBus.Error.Failed", "Operation was cancelled")
    if method == "Screenshot":
        # the left half red, the right half blue: shows which part was cut out
        p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1280, 800); p.fill(0x0000ffff)
        p.new_subpixbuf(0, 0, 640, 800).fill(0xff0000ff); p.savev(args[1], "png", [], [])
        inv.return_value(GLib.Variant("(bs)", (True, args[1])))
    elif method == "ScreenshotArea":
        x, y, w, h = args[:4]; picture(args[5], w, h); inv.return_value(GLib.Variant("(bs)", (True, args[5])))
    elif method == "ScreenshotWindowById":
        shadow = args[1]; picture(args[3], 340 if shadow else 300, 240 if shadow else 200)
        inv.return_value(GLib.Variant("(bs)", (True, args[3])))
    elif method == "SelectWindow":
        cancel() if mode == "cancel" else inv.return_value(GLib.Variant("(t)", (77,)))
    elif method == "SelectArea":
        cancel() if mode == "cancel" else inv.return_value(GLib.Variant("(iiii)", (10, 20, 300, 150)))
    else:
        inv.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)

info = Gio.DBusNodeInfo.new_for_xml(XML)
def on_bus(conn, name):
    conn.register_object("/org/cinnamon/Screenshot", info.interfaces[0], handle, None, None)
Gio.bus_own_name(Gio.BusType.SESSION, "org.cinnamon.Screenshot", Gio.BusNameOwnerFlags.REPLACE,
                 on_bus, None, None)
GLib.MainLoop().run()
