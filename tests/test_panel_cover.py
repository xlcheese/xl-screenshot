import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from xlscreenshot.window import ScreenshotWindow
from xlscreenshot.selection import SelectionOverlay
from gi.repository import Gtk, Gdk
def settle(t=0.5):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
class Ev:
    def __init__(self, x, y): self.x, self.y, self.button = x, y, 1
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o+3])

# A fake Cinnamon panel: a bright orange "dock" along the bottom
W, H = 1280, 800
panel = Gtk.Window(); panel.set_type_hint(Gdk.WindowTypeHint.DOCK); panel.set_decorated(False)
panel.set_default_size(W, 40); panel.move(0, H - 40)
area = Gtk.DrawingArea(); area.connect("draw", lambda w, cr: (cr.set_source_rgb(1, 0.5, 0), cr.paint())); panel.add(area)
panel.show_all(); settle(0.8)
root = Gdk.get_default_root_window()
before = Gdk.pixbuf_get_from_window(root, 0, 0, W, H)
ORANGE = pix(before, 600, H - 20)
check("fake panel is showing", ORANGE[0] == 255 and 120 <= ORANGE[1] <= 135 and ORANGE[2] == 0)

sw = ScreenshotWindow(); sw.hide()
ov = SelectionOverlay(sw); settle(1.0)
ov.on_button_press(None, Ev(400, 500)); ov.on_motion_notify(None, Ev(900, H - 5)); ov.on_button_release(None, Ev(900, H - 5)); settle(0.6)
shot = Gdk.pixbuf_get_from_window(root, 0, 0, W, H)
p_out = pix(shot, 200, H - 20)           # panel area, outside the selection: should be the dimmed panel
p_in = pix(shot, 600, H - 20)            # panel area, inside the selection: the panel, undimmed
print(f"   panel area outside selection: {p_out}, inside selection: {p_in}")
xid = ov.get_window().get_xid()
info = subprocess.run(["xwininfo", "-id", str(xid)], capture_output=True, text=True).stdout
check("overlay is override-redirect (no window manager, so no Cinnamon effects)", "Override Redirect State: yes" in info)
check("overlay covers the whole desktop", "Width: 1280" in info and "Height: 800" in info and "Absolute upper-left X:  0" in info)
check("overlay holds the mouse and keyboard while it's up", ov._grabbed)
check("selection screen covers the panel (panel shows dimmed under it)", p_out != ORANGE and p_out[0] < 200)
check("inside the selection, the panel shows at normal brightness", p_in == ORANGE)
a = ov.control_box.get_allocation()
check("Cancel/Capture panel stays on screen", a.y + a.height <= H and a.y >= 0)
shot.savev(os.path.join(helpers.PICTURES, "panel_cover.png"), "png", [], [])

# The captured area matches the selection exactly
import xlscreenshot.selection as SEL
got = {}
real = SEL.capture_region
SEL.capture_region = lambda *a: got.setdefault("args", a) and None
ov.on_capture_confirmed(None); settle(0.6)
check("captures exactly the selected area (overlay at 0,0)", got.get("args", ())[:4] == (400, 500, 500, H - 5 - 500))
# A window manager that put the overlay somewhere else: the capture follows
ov2 = SelectionOverlay(sw); settle(0.8)
ov2.origin_x, ov2.origin_y = 50, 30
ov2.rect_x, ov2.rect_y, ov2.rect_w, ov2.rect_h = 100, 100, 200, 150
got.clear(); ov2.on_capture_confirmed(None); settle(0.6)
check("…and if the overlay sits at (50, 30), the capture is moved to match", got.get("args", ())[:4] == (150, 130, 200, 150))
SEL.capture_region = real

# Real input: Esc from the keyboard (only reaches us through the grab)
ov3 = SelectionOverlay(sw); settle(0.8)
closed = []
ov3.connect("destroy", lambda *a: closed.append(1))
subprocess.run(["xdotool", "key", "Escape"]); settle(0.6)
check("a real Esc key closes the selection screen", closed == [1])
check("…and lets go of the mouse and keyboard", not ov3._grabbed)
check("…and the main window comes back", sw.get_visible())
# Real mouse: draw a selection and click Capture Selection
sw.hide()
ov4 = SelectionOverlay(sw); settle(0.8)
subprocess.run(["xdotool", "mousemove", "200", "150", "mousedown", "1", "mousemove", "500", "300", "mousemove", "600", "400", "mouseup", "1"]); settle(0.6)
check("a real mouse drag makes a selection", (ov4.rect_x, ov4.rect_y, ov4.rect_w, ov4.rect_h) == (200, 150, 400, 250))
b = ov4.capture_btn.get_allocation()
SEL.capture_region = lambda *a: got.setdefault("real", a) and None
got.clear()
subprocess.run(["xdotool", "mousemove", str(b.x + b.width // 2), str(b.y + b.height // 2), "click", "1"]); settle(0.8)
check("a real click on Capture Selection captures that area", got.get("real", ())[:4] == (200, 150, 400, 250))
check("…and lets go of the mouse and keyboard", not ov4._grabbed)
SEL.capture_region = real
print("FAILURES:", fails or "none")
