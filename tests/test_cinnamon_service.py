import helpers  # paths, a temporary home folder, English
"""Capturing through Cinnamon's screenshot service, on X11 and Wayland
(xlcheese/xl-screenshot#10), against a stand-in for the service."""
import json, os, subprocess, sys, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk, GLib
from xlscreenshot import cinnamon_service as CS
from xlscreenshot.window import ScreenshotWindow
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.4):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
LOG = os.path.join(helpers.PICTURES, "service-calls.txt")
fake = None
def start_service(mode):
    global fake
    if fake: fake.kill(); fake.wait()
    if os.path.exists(LOG): os.remove(LOG)
    fake = subprocess.Popen([sys.executable, os.path.join(helpers.TESTS, "fake_cinnamon_screenshot.py"), LOG, mode])
    for _ in range(50):
        if CS.CinnamonScreenshot.find(timeout_ms=200) is not None or mode == "old": break
        time.sleep(0.1)
    time.sleep(0.5)
def calls():
    if not os.path.exists(LOG): return []
    return [json.loads(l) for l in open(LOG)]
def wait_for(cond, t=5):
    end = time.time() + t
    while time.time() < end:
        settle(0.1)
        if cond(): return True
    return False
def window(wayland):
    w = ScreenshotWindow(); w.wayland = wayland
    w.delay_sec = 0; w.show_all(); settle()
    return w
leftovers = lambda: [f for f in os.listdir(GLib.get_user_runtime_dir() or GLib.get_tmp_dir()) if f.startswith("xl-screenshot-")]

# ---- no service: X11 falls back to its own tools; Wayland says so, never hangs ----
check("no service running: not found", CS.CinnamonScreenshot.find(timeout_ms=500) is None)
import xlscreenshot.window as W
x11 = window(wayland=False)
check("X11, no service: Include Window Shadow is available (a shadow is drawn)", x11.menu_shadow.get_sensitive())
x11.destroy()
real_session = W.session_is_wayland
W.session_is_wayland = lambda: True           # created as on Wayland
w = window(wayland=True)
W.session_is_wayland = real_session
check("Wayland, no service: Include Window Shadow is greyed out (no capture possible)", not w.menu_shadow.get_sensitive())
errors = []
w._show_error = lambda text, secondary: errors.append(text)
for name, start in (("Screen", lambda: w.on_screen_capture_clicked(None)),
                    ("Window", lambda: w.on_window_capture_clicked(None)),
                    ("Selection", lambda: w.start_selection())):
    errors.clear()
    start()
    ok = wait_for(lambda: errors and w.get_visible(), 3)
    check(f"Wayland, no service, {name}: a message, and the window comes back (no hang)", ok and not w._capturing)
w.destroy()

# ---- an older Cinnamon without the window methods: not used ----
start_service("old")
check("older Cinnamon without SelectWindow: not used", CS.CinnamonScreenshot.find() is None)

# ---- with the service ----
start_service("ok")
svc = CS.CinnamonScreenshot.find()
check("the service is found, with everything we need", svc is not None and CS.NEEDED <= svc.methods)
for wayland in (False, True):
    where = "Wayland" if wayland else "X11"
    w = window(wayland)
    check(f"{where}: the shadow option is available", w.menu_shadow.get_sensitive())
    # Screen
    open(LOG, "w").close()
    w.include_pointer = True
    w.on_screen_capture_clicked(None)
    check(f"{where} Screen: the whole desktop, through Cinnamon",
          wait_for(lambda: w.active_pixbuf is not None and w.active_pixbuf.get_width() == 1280)
          and calls() and calls()[0][0] == "Screenshot" and calls()[0][1][0] is True)
    check(f"{where} Screen: the window comes back with the thumbnail", w.get_visible())
    # Window, without and with its shadow
    for shadow, size in ((False, (300, 200)), (True, (340, 240))):
        open(LOG, "w").close(); w.active_pixbuf = None
        w.menu_shadow.set_active(shadow); settle(0.1)
        w.on_window_capture_clicked(None)
        got = wait_for(lambda: w.active_pixbuf is not None)
        names = [c[0] for c in calls()]
        check(f"{where} Window{' with shadow' if shadow else ''}: Cinnamon's picker, then that window ({size[0]}x{size[1]})",
              got and names == ["SelectWindow", "ScreenshotWindowById"]
              and calls()[1][1][0] == 77 and calls()[1][1][1] is shadow
              and (w.active_pixbuf.get_width(), w.active_pixbuf.get_height()) == size)
    check(f"{where}: the shadow choice is remembered", w.config["include_shadow"] is True)
    w.menu_shadow.set_active(False)
    # Selection
    open(LOG, "w").close(); w.active_pixbuf = None
    if wayland:
        from xlscreenshot.selection import SelectionOverlay
        class Ev:
            def __init__(self, x, y): self.x, self.y, self.x_root, self.y_root, self.button, self.state = x, y, x, y, 1, 0
        def overlays():
            return [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_visible()]
        w.include_pointer = False
        w.start_selection()
        got = wait_for(lambda: overlays())
        check("Wayland Selection: our own overlay, over a picture of the desktop from Cinnamon",
              got and [c[0] for c in calls()] == ["Screenshot"] and overlays()[0].still_mode)
        check("…taken without the pointer (no frozen pointer next to the real one)", calls()[0][1][0] is False)
        ov = overlays()[0]
        ov.on_button_press(None, Ev(100, 100)); ov.on_motion_notify(None, Ev(400, 300)); ov.on_button_release(None, Ev(400, 300)); settle(0.3)
        check(f"…with our size label ({ov.size_label.get_text()}) and Cancel / Capture Selection",
              ov.size_label.get_text() == "300 × 200" and ov.capture_btn.get_visible())
        ov.on_capture_confirmed(None)
        got = wait_for(lambda: w.active_pixbuf is not None)
        check("…Capture cuts exactly that area out of the picture (300x200), no second capture",
              got and (w.active_pixbuf.get_width(), w.active_pixbuf.get_height()) == (300, 200)
              and [c[0] for c in calls()] == ["Screenshot"] and not overlays())
        # with a delay: a fresh picture of that area once it's over (as on X11)
        open(LOG, "w").close(); w.active_pixbuf = None; w.delay_sec = 1
        w.start_selection(); wait_for(lambda: overlays()); ov = overlays()[0]
        ov.on_button_press(None, Ev(50, 60)); ov.on_motion_notify(None, Ev(350, 210)); ov.on_button_release(None, Ev(350, 210)); settle(0.2)
        ov.on_capture_confirmed(None)
        got = wait_for(lambda: w.active_pixbuf is not None, 6)
        check("…with a delay, a fresh capture of that area afterwards",
              got and [c[0] for c in calls()] == ["Screenshot", "ScreenshotArea"] and calls()[1][1][:4] == [50, 60, 300, 150])
        w.delay_sec = 0
        # Include Pointer: the picture has none, so a fresh capture with the pointer
        open(LOG, "w").close(); w.active_pixbuf = None; w.include_pointer = True
        w.start_selection(); wait_for(lambda: overlays()); ov = overlays()[0]
        ov.on_button_press(None, Ev(50, 60)); ov.on_motion_notify(None, Ev(350, 210)); ov.on_button_release(None, Ev(350, 210)); settle(0.2)
        ov.on_capture_confirmed(None)
        got = wait_for(lambda: w.active_pixbuf is not None, 6)
        check("…with Include Pointer: the overlay's picture without it, then a fresh capture of the area with it",
              got and [c[0] for c in calls()] == ["Screenshot", "ScreenshotArea"]
              and calls()[0][1][0] is False and calls()[1][1][4] is True)
        w.include_pointer = False
        # Esc closes it and brings the window back
        open(LOG, "w").close(); w.active_pixbuf = None
        w.start_selection(); wait_for(lambda: overlays()); ov = overlays()[0]
        ov.on_key_press(None, type("K", (), {"keyval": Gdk.KEY_Escape})())
        check("…Esc closes the overlay and the window comes back", wait_for(lambda: not overlays() and w.get_visible()) and w.active_pixbuf is None)
        # Cinnamon's own selection is still there, for comparing
        os.environ["XL_SCREENSHOT_CINNAMON_SELECTION"] = "1"
        open(LOG, "w").close()
        w.start_selection()
        got = wait_for(lambda: w.active_pixbuf is not None)
        check("XL_SCREENSHOT_CINNAMON_SELECTION=1: Cinnamon's own selection instead (300x150)",
              got and [c[0] for c in calls()] == ["SelectArea", "ScreenshotArea"]
              and (w.active_pixbuf.get_width(), w.active_pixbuf.get_height()) == (300, 150))
        del os.environ["XL_SCREENSHOT_CINNAMON_SELECTION"]
    else:
        opened = []
        import xlscreenshot.window as W
        real = W.SelectionOverlay
        W.SelectionOverlay = lambda tool: opened.append(tool)
        w.start_selection(); settle(0.6)
        W.SelectionOverlay = real
        check("X11 Selection: still our own overlay (with its size label and handles)", opened == [w] and calls() == [])
        w.restore_window()
    check(f"{where}: no temporary picture files left behind", leftovers() == [])
    w.destroy()

# ---- two monitors on Wayland: an overlay on each; one selection at a time ----
# (the test screen is one monitor, so GTK is told there are two, side by side)
class FakeMonitor:
    def __init__(self, x): self.x = x
    def get_geometry(self):
        r = Gdk.Rectangle(); r.x, r.y, r.width, r.height = self.x, 0, 640, 800; return r
real_n, real_get = Gdk.Display.get_n_monitors, Gdk.Display.get_monitor
Gdk.Display.get_n_monitors = lambda self: 2
Gdk.Display.get_monitor = lambda self, i: FakeMonitor(640 * i)
real_fullscreen = Gtk.Window.fullscreen_on_monitor
Gtk.Window.fullscreen_on_monitor = lambda self, screen, i: None
try:
    from xlscreenshot.selection import SelectionOverlay
    class Ev:
        def __init__(self, x, y): self.x, self.y, self.x_root, self.y_root, self.button, self.state = x, y, x, y, 1, 0
    visible = lambda: [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_visible()]
    w = window(wayland=True); w.start_selection()
    wait_for(lambda: len(visible()) == 2)
    ovs = sorted(visible(), key=lambda o: o.origin_x)
    check("two monitors: an overlay on each", len(ovs) == 2 and [o.origin_x for o in ovs] == [0, 640])
    left, right = ovs
    left.on_button_press(None, Ev(50, 50)); left.on_motion_notify(None, Ev(150, 150)); left.on_button_release(None, Ev(150, 150)); settle(0.2)
    right.on_button_press(None, Ev(100, 100)); right.on_motion_notify(None, Ev(300, 200)); right.on_button_release(None, Ev(300, 200)); settle(0.2)
    check("…drawing on the second clears the first", left.rect_w == 0 and right.rect_w == 200)
    right.on_capture_confirmed(None)
    got = wait_for(lambda: w.active_pixbuf is not None)
    px = tuple(w.active_pixbuf.get_pixels()[:3]) if got else None
    check(f"…capturing on the second monitor cuts from its part of the picture (blue: {px})",
          got and (w.active_pixbuf.get_width(), w.active_pixbuf.get_height()) == (200, 100) and px == (0, 0, 255))
    check("…and both overlays close", wait_for(lambda: not visible()))
    w.destroy()
    w = window(wayland=True); w.start_selection(); wait_for(lambda: len(visible()) == 2)
    visible()[0].on_key_press(None, type("K", (), {"keyval": Gdk.KEY_Escape})())
    check("…Esc on either closes both, and the window comes back once", wait_for(lambda: not visible() and w.get_visible()))
    w.destroy()
finally:
    Gdk.Display.get_n_monitors, Gdk.Display.get_monitor = real_n, real_get
    Gtk.Window.fullscreen_on_monitor = real_fullscreen

# ---- Esc / clicking the desktop in Cinnamon's picker ----
start_service("cancel")
w = window(wayland=True)
w.on_window_capture_clicked(None)
check("Window picker cancelled: no capture, the window comes back",
      wait_for(lambda: w.get_visible() and not w._capturing) and w.active_pixbuf is None)
os.environ["XL_SCREENSHOT_CINNAMON_SELECTION"] = "1"
w.start_selection()
check("Cinnamon's selection cancelled: no capture, the window comes back",
      wait_for(lambda: w.get_visible() and not w._capturing) and w.active_pixbuf is None)
del os.environ["XL_SCREENSHOT_CINNAMON_SELECTION"]
# a delay on Wayland: no X11 key grab (it would hang there)
w.delay_sec = 1
w.start_delay(lambda: None)
check("a delay on Wayland doesn't try an X11 key grab", w._escape_grab is None)
w.cancel_delay(); w.destroy()
fake.kill()
print("FAILURES:", fails or "none")
