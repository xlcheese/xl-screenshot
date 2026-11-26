import helpers  # paths, a temporary home folder, English
"""Run by test_wayland.sh: xl-Screenshot as a real Wayland app (under a
headless Weston), with the stand-in Cinnamon service."""
import time
import gi
gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk
from xlscreenshot.window import ScreenshotWindow
from xlannotate.window import AnnotateWindow
from gi.repository import GdkPixbuf
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t):
    e = time.time() + t
    while time.time() < e:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)
check("running on a real Wayland display", type(Gdk.Display.get_default()).__name__.startswith("GdkWayland"))
w = ScreenshotWindow(); w.delay_sec = 0; w.show_all(); settle(1)
check("xl-Screenshot sees Wayland, and Cinnamon's service", w.wayland and w.cinnamon is not None)
for name, go, size in (("Screen", lambda: w.on_screen_capture_clicked(None), (1280, 800)),
                       ("Window", lambda: w.on_window_capture_clicked(None), (300, 200)),
                       ("Selection", lambda: w.start_selection(), (300, 150))):
    w.active_pixbuf = None
    t0 = time.time(); go()
    while time.time() - t0 < 8 and (w.active_pixbuf is None or w._capturing):
        settle(0.1)
    p = w.active_pixbuf
    check(f"Wayland {name}: captured ({p.get_width()}x{p.get_height()}) and the window came back" if p else f"Wayland {name}: captured",
          p is not None and (p.get_width(), p.get_height()) == size and w.get_visible() and not w._capturing)
w.delay_sec = 1; w.active_pixbuf = None; t0 = time.time(); w.on_screen_capture_clicked(None)
while time.time() - t0 < 6 and w.active_pixbuf is None: settle(0.1)
check("Wayland: a delay works, with no X11 key grab", w.active_pixbuf is not None and w._escape_grab is None)
w.open_annotate(); settle(1)
check("xl-Annotate opens on Wayland", w.annotate_window is not None and w.annotate_window.get_visible())
w.annotate_window.destroy()
a = AnnotateWindow(); p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 400, 300); p.fill(0xffffffff)
a.load_pixbuf(p, name="wl.png"); a.show_all(); settle(0.8)
a.tool_buttons["crop"].set_active(True); settle(0.6)
check("xl-Annotate on Wayland: the crop popover opens", a.crop_popover.get_visible())
print("FAILURES:", fails or "none")
