import helpers  # paths, a temporary home folder, English
"""Window capture on X11 without Cinnamon's screenshot service: our look-alike
of Cinnamon's window picker, rounded corners and a drawn shadow."""
import subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk
from xlscreenshot.window import ScreenshotWindow
from xlscreenshot.selection import WindowPickerOverlay
from xlscreenshot.x11_windows import list_windows, window_at
from xlscreenshot import window_look as L
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.4):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
def wait_for(cond, t=5):
    end = time.time() + t
    while time.time() < end:
        settle(0.1)
        if cond(): return True
    return False
def alpha(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return pb.get_pixels()[o + 3]
def test_window(title, x, y, color):
    w = Gtk.Window(title=title); w.set_default_size(300, 200)
    w.override_background_color(Gtk.StateFlags.NORMAL, color); w.show_all(); w.move(x, y)
    return w
a = test_window("Window A", 100, 100, Gdk.RGBA(1, 0, 0, 1))
settle(0.5)
b = test_window("Window B", 300, 200, Gdk.RGBA(0, 0, 1, 1))     # on top, overlapping A
settle(1)
wins = list_windows()
ids = [w["id"] for w in wins]
xa, xb = a.get_window().get_toplevel().get_xid(), b.get_window().get_toplevel().get_xid()
def info(xid):
    return next((w for w in wins if w["id"] == xid), None)
wa, wb = info(xa), info(xb)
check("the window list has both windows", wa is not None and wb is not None)
check("…top first (B was opened last)", wa is not None and wb is not None and wins.index(wb) < wins.index(wa))
check("…with their size, title bar included", wa is not None and wa["rect"][2] >= 300 and wa["rect"][3] >= 200)
check("…and who draws the title bar", wa is not None and (wa["framed"] or wa["csd"]))
ax, ay = wa["rect"][0] + 20, wa["rect"][1] + 60                  # a point only A covers
check("a point inside only A finds A", window_at(wins, ax, ay) is wa)
check("where they overlap, the top window (B) wins", window_at(wins, wb["rect"][0] + 5, wb["rect"][1] + 5) is wb)

app = ScreenshotWindow(); app.cinnamon = None; app.wayland = False; app.delay_sec = 0
app.show_all(); settle()
class Ev:
    def __init__(self, x, y, button=1): self.x, self.y, self.x_root, self.y_root, self.button, self.state = x, y, x, y, button, 0
def picker():
    return next((t for t in Gtk.Window.list_toplevels() if isinstance(t, WindowPickerOverlay) and t.get_visible()), None)

# pick A, without a shadow
app.menu_shadow.set_active(False)
app.on_window_capture_clicked(None)
check("Window: our picker appears (no xdotool), xl-Screenshot hidden", wait_for(lambda: picker() is not None) and not app.get_visible())
p = picker()
check("…the desktop is tinted like Selection", p.mask_color[3] > 0)
p.on_motion_notify(None, Ev(ax, ay)); settle(0.2)
check("hovering lifts the window under the pointer (A)", p.hovered is not None and p.hovered["rect"] == wa["rect"] and p.rect_w == wa["rect"][2])
p.on_motion_notify(None, Ev(wb["rect"][0] + 5, wb["rect"][1] + 5)); settle(0.2)
check("…moving onto B lifts B", p.hovered is not None and p.hovered["rect"] == wb["rect"])
p.on_motion_notify(None, Ev(ax, ay)); settle(0.1)
p.on_button_press(None, Ev(ax, ay))
got = wait_for(lambda: app.active_pixbuf is not None)
pb = app.active_pixbuf
check(f"a click captures that window ({pb.get_width()}x{pb.get_height()})" if got else "a click captures that window",
      got and (pb.get_width(), pb.get_height()) == wa["rect"][2:] and picker() is None)
r = L.corner_radius_for(wa)
check(f"…its top corners rounded like the theme's ({r} px): transparent in the corner, solid inside",
      got and r > 0 and pb.get_has_alpha() and alpha(pb, 0, 0) == 0 and alpha(pb, pb.get_width() - 1, 0) == 0
      and alpha(pb, pb.get_width() // 2, pb.get_height() // 2) == 255 and alpha(pb, 0, pb.get_height() - 1) == 255)

# with a shadow
app.active_pixbuf = None; app.menu_shadow.set_active(True); settle(0.1)
check("Include Window Shadow is available on X11 too (drawn)", app.menu_shadow.get_sensitive())
app.on_window_capture_clicked(None); wait_for(lambda: picker() is not None)
picker().on_motion_notify(None, Ev(ax, ay)); picker().on_button_press(None, Ev(ax, ay))
got = wait_for(lambda: app.active_pixbuf is not None)
pb = app.active_pixbuf
m = (pb.get_width() - wa["rect"][2]) // 2 if got else 0
check(f"…with a shadow: room round the window ({m} px each side)", got and m > 10 and pb.get_height() == wa["rect"][3] + 2 * m)
check("…soft and darker just below the window, clear far out",
      got and 0 < alpha(pb, pb.get_width() // 2, m + wa["rect"][3] + 4) < 255 and alpha(pb, 1, 1) < alpha(pb, pb.get_width() // 2, m + wa["rect"][3] + 4))
# the bottom corners fade like a blur: no darker spot where the bottom and side shadows meet
def a_at(x, y): return alpha(pb, x, y) if got else 0
d = 6; ww, wh = wa["rect"][2], wa["rect"][3]
below, beside, corner = a_at(m + ww // 2, m + wh + d), a_at(m - d, m + wh // 2), a_at(m + ww + d, m + wh + d)
check(f"…its bottom corners fade, no heavier spot (corner {corner}, below {below}, beside {beside})", corner <= max(below, beside))
app.menu_shadow.set_active(False)

# Esc, and a click on the desktop
app.active_pixbuf = None
app.on_window_capture_clicked(None); wait_for(lambda: picker() is not None)
picker().on_key_press(None, type("K", (), {"keyval": Gdk.KEY_Escape})())
check("Esc: no capture, xl-Screenshot comes back", wait_for(lambda: picker() is None and app.get_visible()) and app.active_pixbuf is None)
app.on_window_capture_clicked(None); wait_for(lambda: picker() is not None)
picker().on_button_press(None, Ev(1270, 790))           # the empty desktop corner
check("a click on the desktop cancels too", wait_for(lambda: picker() is None and app.get_visible()) and app.active_pixbuf is None)

# maximized windows stay square, with no shadow
from gi.repository import GdkPixbuf
solid = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 200, 100); solid.fill(0x336699ff)
radius = L.corner_radius_for({"maximized": True, "csd": True})
flat = L.finish_window(solid, radius=radius, rounded=radius > 0, shadow=False)
check("maximized windows: square corners, no shadow", radius == 0 and alpha(flat, 0, 0) == 255
      and (flat.get_width(), flat.get_height()) == (200, 100))
# the theme's corners count, including personal tweaks (as a theme tool might make)
css = Gtk.CssProvider(); css.load_from_data(b"window.ssd decoration, window.csd decoration { border-radius: 14px 14px 0 0; }")
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
check("a theme with rounder corners (14 px) is followed", L.corner_radius_for({"framed": True}) == 14 and L.corner_radius_for({"csd": True}) == 14)
print("FAILURES:", fails or "none")
