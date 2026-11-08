import helpers  # noqa: F401  (paths, a temporary home folder, English)
import sys, os, tempfile, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from xlscreenshot import application, tray, config
from xlscreenshot.window import ScreenshotWindow
from gi.repository import Gtk, GdkPixbuf, Gio
fails = []
def check(n, c):
    print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.4):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
def dbus_names():
    out = subprocess.run(["dbus-send", "--session", "--print-reply", "--dest=org.freedesktop.DBus",
                          "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"], capture_output=True, text=True).stdout
    return out

check("Mint tray library available", tray.HAS_XAPP)
app = application.ScreenshotApp()
app.command = "/home/wes/Downloads/my stuff/xl-screenshot/usr/bin/xl-screenshot"   # pretend launcher path
app.register(None)
Gtk.Application.do_startup(app) if False else None
app.window = w = ScreenshotWindow(application=app)
w.present(); settle()

check("tray off by default", not w.menu_tray.get_active() and app.tray is None and not os.path.exists(tray.AUTOSTART_PATH))
check("checkbox is in the menu", w.menu_tray.get_label() == "Show in System Tray" and w.menu_tray.get_sensitive())

w.menu_tray.set_active(True); settle()
check("check it: tray icon created", app.tray is not None and app.tray.icon is not None)
check("check it: remembered in settings", config.load_config()["show_tray"] is True)
entry = open(tray.AUTOSTART_PATH).read()
print("  autostart Exec:", [l for l in entry.splitlines() if l.startswith("Exec")][0])
check("check it: starts at login with --tray", 'Exec="/home/wes/Downloads/my stuff/xl-screenshot/usr/bin/xl-screenshot" --tray' in entry)
labels = [mi.get_label() for mi in app.tray.menu.get_children() if not isinstance(mi, Gtk.SeparatorMenuItem)]
check("right-click menu items", labels == ["Show xl-Screenshot", "Screen", "Window", "Selection", "Quit"])
user_icon = os.path.expanduser("~/.local/share/icons/hicolor/scalable/actions/xl-screenshot-tray-symbolic.svg")
check("tray icon given by name (so Cinnamon recolours it)", tray._tray_icon_name() == "xl-screenshot-tray-symbolic")
check("…and copied where Cinnamon finds it by name", os.path.isfile(user_icon)
      and open(user_icon, "rb").read() == open(tray._OUR_ICON, "rb").read())
mtime = os.path.getmtime(user_icon); time.sleep(1.1); tray._tray_icon_name()
check("…not copied again when already up to date", os.path.getmtime(user_icon) == mtime)
open(user_icon, "w").write("<svg/>"); tray._tray_icon_name()
check("…refreshed if the copy is out of date", open(user_icon, "rb").read() == open(tray._OUR_ICON, "rb").read())

# Close the window: only hides
w.close(); settle()
check("close with tray on: window hides, app keeps it", not w.get_visible() and w.get_application() is app)
app.tray.menu.get_children()[0].activate(); settle()
check("tray menu Show brings it back", w.get_visible())

# Left-click the icon: Selection capture
w.close(); settle()
app.tray.on_activate(app.tray.icon, 1, 0); settle(0.6)
check("left-click starts a Selection capture", w.is_busy() and not w.get_visible())
overlays = [t for t in Gtk.Window.list_toplevels() if t.get_title() == "xl-Screenshot Selection" and t.get_visible()]
check("…the selection overlay is up", len(overlays) == 1)
app.tray.on_activate(app.tray.icon, 1, 0); settle(0.4)
check("clicking again while selecting doesn't start a second one",
      len([t for t in Gtk.Window.list_toplevels() if t.get_title() == "xl-Screenshot Selection" and t.get_visible()]) == 1)
overlays[0].on_cancel_clicked(None); settle()
check("cancel: window comes back", w.get_visible() and not w.is_busy())
app.tray.on_activate(app.tray.icon, 3, 0); settle()
check("right-click doesn't start a capture", not w.is_busy())

# Tray menu Screen capture with the window hidden
w.close(); settle()
[mi for mi in app.tray.menu.get_children() if mi.get_label() == "Screen"][0].activate(); settle(0.8)
check("tray menu Screen: captures and shows the result", w.active_pixbuf is not None and w.get_visible())

# Second launches while in the tray
w.close(); settle()
cl = {"tray": True}
class FakeCL:
    def __init__(self, opts): self.opts = opts
    def get_options_dict(self):
        d = GLibVariantDict(self.opts); return d
from gi.repository import GLib
class GLibVariantDict:
    def __init__(self, o): self.o = o
    def end(self): return GLib.Variant("a{sv}", {k: GLib.Variant("b", v) for k, v in self.o.items()})
app.do_command_line(FakeCL({"tray": True})); settle()
check("--tray when already running: shows the window", w.get_visible())

# Quit from the tray, with unsaved annotations: Cancel keeps everything
w.update_screenshot_buffer(GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 200, 100)); settle()
w.open_annotate(); settle(0.4)
aw = w.annotate_window
from xlannotate.shapes import ArrowShape
aw.canvas.add_shape(ArrowShape(10, 10, 100, 50, stroke=(1, 0, 0, 1), size=6))
asked = []
aw.ask_unsaved = lambda: asked.append(1) or "cancel"
quit_called = []
app.quit = lambda: quit_called.append(1)
app.quit_from_tray(); settle()
check("Quit + unsaved annotations: asks first", asked == [1])
check("Quit + unsaved annotations + Cancel: nothing closes", w.annotate_window is aw and not quit_called and app.tray is not None)
aw.ask_unsaved = lambda: "save"
app.quit_from_tray(); settle()
print("  annotate_window:", w.annotate_window, " shapes:", len(w.shapes), " quit_called:", quit_called, " tray:", app.tray)
check("Quit + Keep: annotations kept, app quits", w.annotate_window is None and len(w.shapes) == 1 and quit_called == [1] and app.tray is None)

# Quit + Discard
app.tray = None; w.menu_tray.set_active(False); w.menu_tray.set_active(True); settle()
w.open_annotate(); settle(0.3); aw = w.annotate_window
aw.canvas.add_shape(ArrowShape(10, 60, 100, 60, stroke=(1, 0, 0, 1), size=6))
aw.ask_unsaved = lambda: "discard"
app.quit_from_tray(); settle()
check("Quit + Discard: annotation dropped, app quits", w.annotate_window is None and len(w.shapes) == 1 and quit_called == [1, 1])

# Turn it off again
app.tray = None
w.menu_tray.set_active(True); settle()
w.menu_tray.set_active(False); settle()
check("uncheck: tray icon removed", app.tray is None)
check("uncheck: no longer starts at login", not os.path.exists(tray.AUTOSTART_PATH))
check("uncheck: remembered", config.load_config()["show_tray"] is False)
destroyed = []
w.connect("destroy", lambda *_: destroyed.append(1))
w.close(); settle()
check("uncheck: closing the window really closes it", destroyed == [1])

# Quoting
check("autostart quoting handles quotes and $", tray._desktop_quote('/a b/it\'s "x" $y') == '"/a b/it\'s \\"x\\" \\$y"')
print("FAILURES:", fails or "none")
