import helpers  # noqa: F401  (paths, a temporary home folder, English)
import sys, os, tempfile, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
import xs_shim as xs
from gi.repository import Gtk, GLib
from Xlib import X, XK
import Xlib.display, Xlib.error
def settle(t):
    end=time.time()+t
    while time.time()<end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)
fails=[]
def check(n,c): print(("PASS " if c else "FAIL ")+n); c or fails.append(n)
def press_esc(): subprocess.run(["xdotool", "key", "Escape"])
def escape_is_free():
    d = Xlib.display.Display(); r = d.screen().root
    kc = d.keysym_to_keycode(XK.string_to_keysym("Escape")); c = Xlib.error.CatchError(Xlib.error.BadAccess)
    r.grab_key(kc, 0, True, X.GrabModeAsync, X.GrabModeAsync, onerror=c); d.sync()
    free = c.get_error() is None
    if free: r.ungrab_key(kc, 0); d.sync()
    d.close(); return free

app = xs.XLScreenshotTool(); app.show_all(); settle(0.5)
app.delay_sec = 3

# Screen: Esc during the delay
app.on_screen_capture_clicked(None); settle(0.5)
check("screen: window hidden during delay", not app.get_visible())
check("screen: Escape grabbed during delay", not escape_is_free())
t = time.time(); press_esc(); settle(0.3)
check("screen: Esc restores window right away", app.get_visible())
check("screen: no screenshot taken", app.active_pixbuf is None)
check("screen: Escape released after cancel", escape_is_free())
settle(3.0)
check("screen: cancelled timer never fires later", app.active_pixbuf is None)

# Screen: delay completes normally
app.on_screen_capture_clicked(None); settle(3.6)
check("screen: capture after full delay", app.active_pixbuf is not None and app.get_visible())
check("screen: Escape released after capture", escape_is_free())

# Window mode (skip the click part): Esc during delay
before = app.active_pixbuf
tw = Gtk.Window(); tw.move(100,100); tw.resize(200,150); tw.show_all(); settle(0.5)
app.hide(); app.start_delay(app.perform_window_grab, str(tw.get_window().get_xid())); settle(0.5)
press_esc(); settle(0.3)
check("window: Esc restores, no new capture", app.get_visible() and app.active_pixbuf is before)
check("window: Escape released", escape_is_free())
tw.destroy()

# Selection: Esc during delay after Capture Selection
app.hide()
ov = xs.SelectionOverlay(app); settle(0.3)
ov.rect_x, ov.rect_y, ov.rect_w, ov.rect_h = 10, 10, 100, 80
ov.on_capture_confirmed(None); settle(0.5)
check("selection: overlay and main window hidden during delay", not ov.get_visible() and not app.get_visible())
press_esc(); settle(0.3)
check("selection: Esc brings back main window", app.get_visible())
check("selection: no new capture", app.active_pixbuf is before)
check("selection: Escape released", escape_is_free())

# Selection: delay completes
app.hide(); ov = xs.SelectionOverlay(app); settle(0.3)
ov.rect_x, ov.rect_y, ov.rect_w, ov.rect_h = 10, 10, 100, 80
ov.on_capture_confirmed(None); settle(3.6)
check("selection: capture after full delay", app.active_pixbuf.get_width() == 100 and app.get_visible())

# Zero delay: no grab at all
app.delay_sec = 0
app.on_screen_capture_clicked(None); settle(0.1)
check("no delay: Escape not grabbed", escape_is_free())
settle(0.5)
print("FAILURES:", fails or "none")
