import helpers  # paths, a temporary home folder, English
"""Selection and Crop are tinted with the theme's rubberband colors, as
Cinnamon's own window picker and area selection are."""
import subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk, GdkPixbuf
from xlshared.ui import rubberband_colors, SELECTION_DIM
from xlscreenshot.window import ScreenshotWindow
from xlscreenshot.selection import SelectionOverlay
from xlannotate.window import AnnotateWindow
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.4):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o + 3])

w = ScreenshotWindow(); w.show_all(); settle()
mask, outline = rubberband_colors(w)
check(f"a theme without a rubberband tint: the grey dimming as before {tuple(round(c, 2) for c in mask)}",
      mask == (0, 0, 0, SELECTION_DIM) or mask[3] > 0.02)
# a theme with an unmistakable rubberband: red tint, pure green outline
css = Gtk.CssProvider()
css.load_from_data(b".rubberband { background-color: rgba(255, 0, 0, 0.5); border: 1px solid #00ff00; }")
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
settle()
mask, outline = rubberband_colors(w)
check("the theme's rubberband colors are found", tuple(round(c, 2) for c in mask) == (1.0, 0.0, 0.0, 0.5) and outline[:3] == (0.0, 1.0, 0.0))

# xl-Screenshot's Selection: a white desktop, tinted red outside the selection
desk = Gtk.Window(); desk.set_type_hint(Gdk.WindowTypeHint.DESKTOP); desk.set_decorated(False); desk.move(0, 0)
desk.set_default_size(1280, 800); desk.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1, 1)); desk.show_all(); settle(0.8)
w.hide(); settle()
ov = SelectionOverlay(w); settle(0.8)
class Ev:
    def __init__(self, x, y): self.x, self.y, self.x_root, self.y_root, self.button, self.state = x, y, x, y, 1, 0
ov.on_button_press(None, Ev(400, 300)); ov.on_motion_notify(None, Ev(700, 500)); ov.on_button_release(None, Ev(700, 500)); settle(0.6)
shot = Gdk.pixbuf_get_from_window(ov.get_window(), 0, 0, ov.get_allocated_width(), ov.get_allocated_height())
outside, inside = pix(shot, 100, 100), pix(shot, 550, 400)
edge = max((pix(shot, x, 350) for x in range(396, 405)), key=lambda p: p[1] - p[0])   # across the left edge, away from the handle
check(f"Selection: tinted with the theme's rubberband color outside {outside}", outside[0] > 200 and outside[1] < 160 and outside[2] < 160)
check(f"…clear inside {inside}", inside == (255, 255, 255))
check(f"…outlined in the rubberband's outline color {edge}", edge[1] > 150 and edge[0] < 100)
ov.destroy(); settle()

# xl-Annotate's Crop: the same tint and outline
a = AnnotateWindow(); p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 400, 300); p.fill(0xffffffff)
a.load_pixbuf(p, name="t.png"); a.resize(800, 600); a.show_all(); settle(0.8)
cv = a.canvas; cv.zoom_to(1.0); settle()
a.tool_buttons["crop"].set_active(True); settle()
x1, y1 = cv.to_widget(100, 80); x2, y2 = cv.to_widget(300, 220)
cv.on_button_press(cv, Ev(x1, y1)); cv.on_motion(cv, Ev(x2, y2)); cv.on_button_release(cv, Ev(x2, y2)); settle(0.6)
shot = Gdk.pixbuf_get_from_window(cv.get_window(), 0, 0, cv.get_allocated_width(), cv.get_allocated_height())
ox, oy = cv.to_widget(30, 30); ix, iy = cv.to_widget(200, 150); ex, ey = cv.to_widget(100, 110)
outside, inside = pix(shot, ox, oy), pix(shot, ix, iy)
edge = max((pix(shot, round(ex) + d, round(ey)) for d in range(-4, 5)), key=lambda p: p[1] - p[0])
check(f"Crop: the same tint outside the area {outside}", outside[0] > 200 and outside[1] < 160)
check(f"…clear inside {inside}", inside == (255, 255, 255))
check(f"…and the same outline {edge}", edge[1] > 150 and edge[0] < 100)
print("FAILURES:", fails or "none")
