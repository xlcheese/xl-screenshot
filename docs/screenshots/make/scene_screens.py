from common import *
import scenery
from xlshared.ui import add_icon_search_path
from xlscreenshot.window import ScreenshotWindow
from xlscreenshot.selection import SelectionOverlay
start_wm(); add_icon_search_path()
SW, SH = 2880, 1800
wall, poi = scenery.draw(SW, SH)
# the "desktop": the picture full screen, behind everything
desk = Gtk.Window(); desk.set_type_hint(Gdk.WindowTypeHint.DESKTOP); desk.set_decorated(False); desk.move(0, 0); desk.set_default_size(SW // 2, SH // 2)
area = Gtk.DrawingArea(); desk.add(area)
def draw_wall(_w, cr):
    cr.scale(0.5, 0.5); cr.set_source_surface(wall, 0, 0); cr.paint()
area.connect("draw", draw_wall); desk.show_all(); settle(1)
# xl-Screenshot with a capture in its thumbnail (the annotated picture)
win = ScreenshotWindow(); win.show_all(); settle(1)
subprocess.run(["xdotool", "mousemove", "2870", "1790"]); settle(0.3)
flat = GdkPixbuf.Pixbuf.new_from_file(f"{OUT}/annotated-image.png")
win.update_screenshot_buffer(flat); win.resize(460, 470); settle(1.2)
raw = grab(win); save(decorate(raw), "screenshot")
print("screenshot window", raw.get_width(), raw.get_height())
# the Selection overlay, round the cabin and the mountain
win.hide(); settle(0.5)
ov = SelectionOverlay(win); settle(1.2)
class E: pass
def ev(x, y):
    e = E(); e.x, e.y, e.x_root, e.y_root, e.button, e.state = x, y, x, y, 1, 0; return e
x0, y0, x1, y1 = 130, 160, 780, 700
ov.on_button_press(None, ev(x0, y0)); ov.on_motion_notify(None, ev(x1, y1)); ov.on_button_release(None, ev(x1, y1)); settle(1)
pb = grab(ov)
s = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
cr = cairo.Context(s); Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0); cr.paint()
save(s, "selection")
print("selection", pb.get_width(), pb.get_height())
