import helpers  # paths, a temporary home folder, English
"""Screens and Screen with several monitors (faked: the test screen is one)."""
import json, os, subprocess, sys, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk, GdkPixbuf
import xlscreenshot.window as W
from xlscreenshot import screens_icon as SI
from xlscreenshot import cinnamon_service as CS
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
def px(pb, x, y):
    o = y * pb.get_rowstride() + x * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o + 3])

# a desktop: the left half red, the right half blue
desk = Gtk.Window(); desk.set_type_hint(Gdk.WindowTypeHint.DESKTOP); desk.set_decorated(False); desk.move(0, 0)
desk.set_default_size(1280, 800)
area = Gtk.DrawingArea(); desk.add(area)
def draw(_w, cr):
    cr.set_source_rgb(1, 0, 0); cr.rectangle(0, 0, 640, 800); cr.fill()
    cr.set_source_rgb(0, 0, 1); cr.rectangle(640, 0, 640, 800); cr.fill()
area.connect("draw", draw); desk.show_all(); settle(0.8)

# ---- one monitor: as before ----
w = W.ScreenshotWindow(); w.cinnamon = None; w.delay_sec = 0; w.show_all(); settle(0.5)
one_width = w.btn_cluster.get_allocated_width()
check("one monitor: three buttons, no Screens", not w.screens_btn.get_visible() and not w.multi_monitor
      and [b.get_visible() for b in w.btn_cluster.get_children()] == [False, True, True, True])

# ---- fake two monitors side by side ----
class FakeMonitor:
    def __init__(self, x, y=0): self.x, self.y = x, y
    def get_geometry(self):
        r = Gdk.Rectangle(); r.x, r.y, r.width, r.height = self.x, self.y, 640, 800 if self.y == 0 and LAYOUT == "row" else 400; return r
    def connect(self, *a): return 0
    def __hash__(self): return hash((self.x, self.y))
    def __eq__(self, o): return isinstance(o, FakeMonitor) and (o.x, o.y) == (self.x, self.y)
LAYOUT = "row"
MONS = [FakeMonitor(0), FakeMonitor(640)]
real = {n: getattr(Gdk.Display, n) for n in ("get_n_monitors", "get_monitor", "get_monitor_at_point", "get_monitor_at_window", "get_primary_monitor")}
Gdk.Display.get_n_monitors = lambda self: len(MONS)
Gdk.Display.get_monitor = lambda self, i: MONS[i]
Gdk.Display.get_monitor_at_point = lambda self, x, y: MONS[1] if x >= 640 and len(MONS) > 1 else MONS[0]
Gdk.Display.get_primary_monitor = lambda self: MONS[0]
window_monitor = [MONS[1]]
Gdk.Display.get_monitor_at_window = lambda self, win: window_monitor[0]
w._update_monitors(); settle(0.5)
check("two monitors: Screens appears, as the first of four buttons",
      w.multi_monitor and w.screens_btn.get_visible() and w.btn_cluster.get_children()[0] is w.screens_btn)
check("…and the row keeps its width", w.btn_cluster.get_allocated_width() == one_width)
widths = [b.get_allocated_width() for b in w.btn_cluster.get_children()]
check(f"…the four buttons are the same width {widths}", max(widths) - min(widths) <= 1)
check("…no tooltips on Screen or Screens (the labels say it)", w.screen_btn.get_tooltip_text() is None and w.screens_btn.get_tooltip_text() is None)
img, label = w.screens_btn.get_child().get_children()
check("…Screens' icon is drawn from the layout", img.get_storage_type() == Gtk.ImageType.SURFACE)
check("…and its icon and label actually show (not an empty button)", img.get_mapped() and label.get_mapped() and label.get_text() == "Screens")

# ---- the icon ----
col = (0, 0, 0, 1)
def size(mons):
    s = SI.render(mons, col); return s.get_width(), s.get_height()
side, stacked = size([(0, 0, 1920, 1080), (1920, 0, 1920, 1080)]), size([(0, 0, 1920, 1080), (0, 1080, 1920, 1080)])
three = size([(0, 0, 1920, 1080), (1920, 0, 1920, 1080), (3840, 0, 1920, 1080)])
check(f"icon: two side by side uses the button's width ({side[0]}x{side[1]}), as tall as the others",
      side[0] > 60 and side[0] <= SI.ICON_MAX_WIDTH and side[1] == SI.ICON_HEIGHT)
check(f"…two stacked is narrower ({stacked[0]}x{stacked[1]})", stacked[0] < side[0] and stacked[1] == SI.ICON_HEIGHT)
check(f"…three in a row stays within the button ({three[0]})", three[0] <= SI.ICON_MAX_WIDTH)
def frame_shape(mons):
    """Width / height of the first monitor as drawn."""
    surf = SI.render(mons, col, scale=1); d, stp = surf.get_data(), surf.get_stride()
    rows = [y for y in range(surf.get_height()) if any(d[y * stp + x * 4 + 3] >= 128 for x in range(4, 10))]
    return (surf.get_width() / len(mons)) / (rows[-1] - rows[0] + 1) if rows else 0
screen_shape = 512 / (404 - 55)
side_shape = frame_shape([(0, 0, 1920, 1080), (1920, 0, 1920, 1080)])
check(f"…side by side, each monitor is shaped like the Screen icon's ({side_shape:.2f} vs {screen_shape:.2f}), not flatter",
      abs(side_shape - screen_shape) < 0.2)
def bezel(surface, x_from, y):
    """Thickness of the first dark run from x_from, across a monitor's left edge."""
    d, st = surface.get_data(), surface.get_stride()
    a = lambda x: d[y * st + x * 4 + 3]
    x = x_from
    while x < surface.get_width() and a(x) < 128: x += 1
    n = 0
    while x < surface.get_width() and a(x) >= 128: x += 1; n += 1
    return n
two_s = SI.render([(0, 0, 1920, 1080), (1920, 0, 1920, 1080)], col, scale=4)
three_s = SI.render([(0, 0, 1920, 1080), (1920, 0, 1920, 1080), (3840, 0, 1920, 1080)], col, scale=4)
b2, b3 = bezel(two_s, 0, two_s.get_height() // 3), bezel(three_s, 0, three_s.get_height() // 2 - 4)
check(f"…the monitors' frames keep one line weight, however many ({b2} and {b3} px at 4x)", b2 > 0 and abs(b2 - b3) <= 1)
st = SI.render([(0, 0, 1920, 1080), (0, 1080, 1920, 1080)], col, scale=2)
d, stride = st.get_data(), st.get_stride()
mid_x = st.get_width() // 2
column = [d[y * stride + mid_x * 4 + 3] >= 128 for y in range(st.get_height())]
runs, n = [], 0
for dark in column + [False]:
    if dark: n += 1
    elif n: runs.append(n); n = 0
# down the middle: top monitor (top edge, bottom edge), bottom monitor (top edge, bottom edge + stand)
check(f"…stands only under the bottom row (runs down the middle: {runs})",
      len(runs) == 4 and runs[1] < runs[3] - 4)
check("…with one monitor: no icon needed (Screen's own)", SI.render([], col) is None)
six = SI.render([(i * 1920, 0, 1920, 1080) for i in range(6)], col)
grid = SI.render([(0, 0, 1920, 1080), (1920, 0, 1920, 1080), (0, 1080, 1920, 1080), (1920, 1080, 1920, 1080)], col)
check("…more than four monitors: drawn as a 2 x 2 (still readable)", (six.get_width(), six.get_height()) == (grid.get_width(), grid.get_height()))

# ---- capturing on X11 (no Cinnamon service) ----
W.get_pointer_position = lambda: (900, 300)       # over the right (blue) monitor
w.screens_btn.clicked()
check("Screens: every monitor (1280x800)", wait_for(lambda: w.active_pixbuf is not None and w.active_pixbuf.get_width() == 1280)
      and w.active_pixbuf.get_height() == 800)
w.active_pixbuf = None
w.screen_btn.clicked()
got = wait_for(lambda: w.active_pixbuf is not None)
check(f"Screen: just the monitor the pointer is on (640x800, blue {px(w.active_pixbuf, 10, 10) if got else ''})",
      got and (w.active_pixbuf.get_width(), w.active_pixbuf.get_height()) == (640, 800) and px(w.active_pixbuf, 10, 10) == (0, 0, 255))
W.get_pointer_position = lambda: (100, 300)
w.active_pixbuf = None; w.screen_btn.clicked()
got = wait_for(lambda: w.active_pixbuf is not None)
check("…and the other one when the pointer is there (red)", got and px(w.active_pixbuf, 10, 10) == (255, 0, 0))

# ---- through Cinnamon's service ----
LOG = os.path.join(helpers.PICTURES, "screens-calls.txt")
fake = subprocess.Popen([sys.executable, os.path.join(helpers.TESTS, "fake_cinnamon_screenshot.py"), LOG, "ok"])
wait_for(lambda: CS.CinnamonScreenshot.find(timeout_ms=200) is not None)
w.cinnamon = CS.CinnamonScreenshot.find()
calls = lambda: [json.loads(l) for l in open(LOG)] if os.path.exists(LOG) else []
open(LOG, "w").close(); W.get_pointer_position = lambda: (900, 300)
w.active_pixbuf = None; w.screen_btn.clicked()
check("with Cinnamon's service, Screen asks for just that monitor's area",
      wait_for(lambda: w.active_pixbuf is not None) and calls() and calls()[0][0] == "ScreenshotArea" and calls()[0][1][:4] == [640, 0, 640, 800])
open(LOG, "w").close(); w.active_pixbuf = None; w.screens_btn.clicked()
check("…and Screens for everything", wait_for(lambda: w.active_pixbuf is not None) and calls() and calls()[0][0] == "Screenshot")
# Wayland: apps aren't told where the pointer is: the monitor xl-Screenshot is on
w.wayland = True; window_monitor[0] = MONS[0]
open(LOG, "w").close(); w.active_pixbuf = None; w.screen_btn.clicked()
check("on Wayland, Screen captures the monitor xl-Screenshot is on",
      wait_for(lambda: w.active_pixbuf is not None) and calls() and calls()[0][1][:4] == [0, 0, 640, 800])
w.wayland = False
fake.kill()

# ---- the tray menu, and back to one monitor ----
from xlscreenshot.tray import TrayIcon
tray = TrayIcon.__new__(TrayIcon)          # just its menu: no real tray icon needed
tray.window, tray.on_quit = w, lambda: None
tray.menu = tray._build_menu()
check("tray menu: Screens offered with several monitors", tray.screens_item.get_visible())
tray.show_screens(False)
check("…and not with one", not tray.screens_item.get_visible())
MONS[:] = [FakeMonitor(0)]
w._update_monitors(); settle(0.3)
check("unplugging back to one monitor: Screens goes, three buttons again",
      not w.screens_btn.get_visible() and not w.multi_monitor)
for n, f in real.items(): setattr(Gdk.Display, n, f)
print("FAILURES:", fails or "none")
