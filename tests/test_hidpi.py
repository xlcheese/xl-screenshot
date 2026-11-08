import helpers  # noqa: F401  (paths, a temporary home folder, English)
import os, sys, time, subprocess, tempfile
SCALE_ARG = sys.argv[1] if len(sys.argv) > 1 else "1"
os.environ["GDK_SCALE"] = SCALE_ARG
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
import gi; gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf
import cairo
from xlscreenshot.window import ScreenshotWindow
from xlscreenshot.selection import SelectionOverlay
from xlscreenshot import capture
SC = int(SCALE_ARG)
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.6):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)
# a desktop with a distinct colour every 10 device pixels, so any offset or scale shows
root = Gdk.get_default_root_window(); W, H = root.get_width() * SC, root.get_height() * SC
pat = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H); cr = cairo.Context(pat)
for x in range(0, W, 10):
    for y in range(0, H, 40):
        cr.set_source_rgb((x // 10 % 25) / 25, (y // 40 % 25) / 25, 0.5); cr.rectangle(x, y, 10, 40); cr.fill()
desk = Gtk.Window(); desk.set_type_hint(Gdk.WindowTypeHint.DESKTOP); desk.set_decorated(False)
desk.move(0, 0); desk.set_default_size(W // SC, H // SC)
da = Gtk.DrawingArea(); desk.add(da)
def draw(_w, c): c.scale(1 / SC, 1 / SC); c.set_source_surface(pat, 0, 0); c.paint()
da.connect("draw", draw); desk.show_all(); settle(1)
def px(pb, x, y):
    b = pb.get_pixels(); o = y * pb.get_rowstride() + x * pb.get_n_channels(); return tuple(b[o:o + 3])
def pat_px(x, y):
    d = pat.get_data(); o = y * pat.get_stride() + x * 4; return (d[o + 2], d[o + 1], d[o])
check(f"scale {SC}: root scale factor is {capture.screen_scale()}", capture.screen_scale() == SC)
full = capture.grab_screen()
check("the screen grab is in device pixels", (full.get_width(), full.get_height()) == (W, H))
check("…and shows the desktop", px(full, 1234, 567) == pat_px(1234, 567))
win = ScreenshotWindow(); win.show_all(); settle(); win.hide(); settle()
got = []
win.update_screenshot_buffer = lambda pb: got.append(pb)
win.start_delay = lambda cb, *a, on_cancel=None: (settle(0.8), cb())
ov = SelectionOverlay(win); settle(1)
class E: pass
def ev(x, y):
    e = E(); e.x, e.y, e.x_root, e.y_root, e.button, e.state = x, y, x, y, 1, 0; return e
ov.on_button_press(None, ev(100, 80)); ov.on_motion_notify(None, ev(400, 300)); ov.on_button_release(None, ev(400, 300)); settle(1)
shot = Gdk.pixbuf_get_from_window(ov.get_window(), 0, 0, ov.get_allocated_width(), ov.get_allocated_height())
# inside the selection the overlay shows the desktop undimmed, at the same place
check("overlay shows the desktop at its real size and place (inside the selection)",
      px(shot, 250 * SC + 3, 200 * SC + 7) == pat_px(250 * SC + 3, 200 * SC + 7))
ov.on_capture_confirmed(None); settle(1)
check("a Selection capture was taken", len(got) == 1)
if got:
    pb = got[0]
    check(f"…of the selected area at full resolution ({pb.get_width()}x{pb.get_height()})",
          (pb.get_width(), pb.get_height()) == (300 * SC, 220 * SC))
    check("…starting at the selection's corner", px(pb, 0, 0) == pat_px(100 * SC, 80 * SC) and px(pb, 155, 101) == pat_px(100 * SC + 155, 80 * SC + 101))
got.clear(); win.perform_full_screen_capture(); settle()
check("Screen capture is the whole desktop", got and (got[0].get_width(), got[0].get_height()) == (W, H))
print("FAILURES:", fails or "none")
