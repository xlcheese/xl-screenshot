import helpers  # paths, a temporary home folder, English
"""Capturing through Cinnamon's screenshot service, on X11 and Wayland
(xlcheese/xl-screenshot#10), against a stand-in for the service."""
import json, os, subprocess, sys, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, GLib
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
w = window(wayland=True)
check("…the shadow option is off and greyed out", not w.menu_shadow.get_sensitive())
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
        w.start_selection()
        got = wait_for(lambda: w.active_pixbuf is not None)
        names = [c[0] for c in calls()]
        check("Wayland Selection: Cinnamon's selection, then that area (300x150)",
              got and names == ["SelectArea", "ScreenshotArea"] and calls()[1][1][:4] == [10, 20, 300, 150]
              and (w.active_pixbuf.get_width(), w.active_pixbuf.get_height()) == (300, 150))
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

# ---- Esc / clicking the desktop in Cinnamon's picker ----
start_service("cancel")
w = window(wayland=True)
w.on_window_capture_clicked(None)
check("Window picker cancelled: no capture, the window comes back",
      wait_for(lambda: w.get_visible() and not w._capturing) and w.active_pixbuf is None)
w.start_selection()
check("Selection cancelled: no capture, the window comes back",
      wait_for(lambda: w.get_visible() and not w._capturing) and w.active_pixbuf is None)
# a delay on Wayland: no X11 key grab (it would hang there)
w.delay_sec = 1
w.start_delay(lambda: None)
check("a delay on Wayland doesn't try an X11 key grab", w._escape_grab is None)
w.cancel_delay(); w.destroy()
fake.kill()
print("FAILURES:", fails or "none")
