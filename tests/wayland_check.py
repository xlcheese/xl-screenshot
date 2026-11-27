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
                       ("Window", lambda: w.on_window_capture_clicked(None), (300, 200))):
    w.active_pixbuf = None
    t0 = time.time(); go()
    while time.time() - t0 < 8 and (w.active_pixbuf is None or w._capturing):
        settle(0.1)
    p = w.active_pixbuf
    check(f"Wayland {name}: captured ({p.get_width()}x{p.get_height()}) and the window came back" if p else f"Wayland {name}: captured",
          p is not None and (p.get_width(), p.get_height()) == size and w.get_visible() and not w._capturing)
# Selection: our own overlay, as a real full-screen Wayland window
from xlscreenshot.selection import SelectionOverlay
class Ev:
    def __init__(self, x, y): self.x, self.y, self.x_root, self.y_root, self.button, self.state = x, y, x, y, 1, 0
w.active_pixbuf = None; w.start_selection()
t0 = time.time()
while time.time() - t0 < 6 and not [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_mapped()]:
    settle(0.1)
ovs = [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_mapped()]
check(f"Wayland Selection: our overlay shows full screen ({ovs[0].get_allocated_width()}x{ovs[0].get_allocated_height()})" if ovs else "Wayland Selection: our overlay shows",
      len(ovs) == 1 and (ovs[0].get_allocated_width(), ovs[0].get_allocated_height()) == (1280, 800))
if ovs:
    ov = ovs[0]
    ov.on_button_press(None, Ev(100, 100)); ov.on_motion_notify(None, Ev(400, 250)); ov.on_button_release(None, Ev(400, 250)); settle(0.5)
    check(f"…with the size label ({ov.size_label.get_text()}) and Capture Selection on screen",
          ov.size_label.get_text() == "300 × 150" and ov.capture_btn.get_mapped())
    ov.on_capture_confirmed(None)
    t0 = time.time()
    while time.time() - t0 < 6 and w.active_pixbuf is None: settle(0.1)
    p = w.active_pixbuf
    check("…and captures that area (300x150); the window comes back",
          p is not None and (p.get_width(), p.get_height()) == (300, 150) and w.get_visible())
# Fast Selection: letting go captures, with no buttons
w.fast_selection = True; w.active_pixbuf = None; w.start_selection()
t0 = time.time()
while time.time() - t0 < 6 and not [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_mapped()]:
    settle(0.1)
ovs = [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_mapped()]
if ovs:
    ov = ovs[0]
    ov.on_button_press(None, Ev(50, 60)); ov.on_motion_notify(None, Ev(250, 160)); settle(0.3)
    check(f"Wayland Fast Selection: the size ({ov.size_label.get_text()}) shows while dragging, no buttons",
          ov.size_label.get_mapped() and ov.size_label.get_text() == "200 × 100" and not ov.capture_btn.get_mapped())
    ov.on_button_release(None, Ev(250, 160))
    t0 = time.time()
    while time.time() - t0 < 6 and w.active_pixbuf is None: settle(0.1)
p = w.active_pixbuf
check("…letting go captures that area (200x100); the window comes back",
      p is not None and (p.get_width(), p.get_height()) == (200, 100) and w.get_visible())
w.fast_selection = False
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
# The command line on Wayland: through Cinnamon's service
import json, os, subprocess, sys
LAUNCHER = os.path.join(helpers.BIN, "xl-screenshot")
def cli(*args):
    p = subprocess.run([sys.executable, LAUNCHER, *args], capture_output=True, timeout=60)
    return p.returncode, p.stdout.decode().strip(), p.stderr.decode()
calls = lambda: [json.loads(l) for l in open(os.path.join(os.environ["XDG_RUNTIME_DIR"], "calls.txt"))]
out_png = os.path.join(os.environ["HOME"], "wl-area.png")
rc, out, err = cli("--area", "10,20,200,100", "-F", out_png)
check("Wayland command line: --area through Cinnamon's ScreenshotArea",
      rc == 0 and out == out_png and calls()[-1][0] == "ScreenshotArea" and calls()[-1][1][:4] == [10, 20, 200, 100])
rc, out, err = cli("--screen", "1", "--clipboard")
check("…--screen 1 --clipboard: Cinnamon copies it", rc == 0 and calls()[-1][1][-1] is True and not out)
rc, out, err = cli("--screen")
check("…--screen without a number explains that Wayland needs one", rc == 2 and "give the screen's number" in err)
rc, out, err = cli("--identify")
time.sleep(1)
running = subprocess.run(["pgrep", "-f", "show-screen-numbers"], capture_output=True).stdout.split()
check("…--identify lists the screens and shows the numbers (full-screen, see-through)", rc == 0 and out.startswith("1: 1280x800") and len(running) == 1)
time.sleep(3.5)
check("…which go after a few seconds", not subprocess.run(["pgrep", "-f", "show-screen-numbers"], capture_output=True).stdout)
rc, out, err = cli("--window-id", "0x123")
check("…--window-id says it's X11 only", rc == 2 and "X11 only" in err)
print("FAILURES:", fails or "none")
