import helpers  # noqa: F401  (paths, a temporary home folder, English)
import sys, os, subprocess, tempfile
import xs_shim as xs
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

def pump():
    while Gtk.events_pending(): Gtk.main_iteration_do(False)

app = xs.XLScreenshotTool()
app.show_all(); pump()
check("preview hidden at startup", not app.preview_area.get_visible())
check("config not written at startup", not os.path.exists(xs.CONFIG_PATH))

# capture_region clipping (window hanging off top-left)
pb = xs.capture_region(-50, -30, 200, 100, False)
check("off-screen crop size is 150x70", pb and (pb.get_width(), pb.get_height()) == (150, 70))
check("fully off-screen returns None", xs.capture_region(-500, -500, 100, 100, False) is None)

# pointer offset: paint test on a white pixbuf
white = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 100, 100); white.fill(0xffffffff)
out = xs.draw_cursor_on_pixbuf(white, 1000, 500, (1020, 530))  # pointer at local (20,30)
px = out.get_pixels(); rs = out.get_rowstride(); nc = out.get_n_channels()
def pix(x, y): o = y*rs + x*nc; return tuple(px[o:o+3])
check("pointer outline drawn at local (20,30)", pix(20, 30) != (255,255,255) or pix(20,31) != (255,255,255))
check("nothing drawn at global coords", pix(0, 0) == (255,255,255))
check("pointer outside image -> unchanged", xs.draw_cursor_on_pixbuf(white, 0, 0, (500, 500)) is white)

# Screen capture path
app.include_pointer = True
app.hide(); app.perform_full_screen_capture(); pump()
check("screen capture sets pixbuf", app.active_pixbuf is not None)
check("preview visible after capture", app.preview_area.get_visible())
check("window restored", app.get_visible())

# Window capture: make a test window, set fake frame extents
tw = Gtk.Window(); tw.set_decorated(False); tw.move(100, 80); tw.resize(300, 200); tw.show_all(); pump()
GLib.usleep(200000); pump()
xid = str(tw.get_window().get_xid())
subprocess.run(["xprop", "-id", xid, "-f", "_NET_FRAME_EXTENTS", "32c", "-set", "_NET_FRAME_EXTENTS", "2,3,30,4"], check=True)
check("xprop parse", xs.xprop_cardinals(xid, "_NET_FRAME_EXTENTS") == [2,3,30,4])
check("xprop missing prop -> None", xs.xprop_cardinals(xid, "_GTK_FRAME_EXTENTS") is None)
x,y,w,h = xs.get_window_geometry(xid); print("  geometry", x,y,w,h)
app.include_pointer = False
app.perform_window_grab(xid); pump()
check("window grab always adds WM frame", (app.active_pixbuf.get_width(), app.active_pixbuf.get_height()) == (w+5, h+34))
subprocess.run(["xprop", "-id", xid, "-f", "_GTK_FRAME_EXTENTS", "32c", "-set", "_GTK_FRAME_EXTENTS", "10,10,8,12"], check=True)
subprocess.run(["xprop", "-id", xid, "-remove", "_NET_FRAME_EXTENTS"], check=True)
app.perform_window_grab(xid); pump()
check("CSD shadow trimmed", (app.active_pixbuf.get_width(), app.active_pixbuf.get_height()) == (w-20, h-20))
check("no include_border left in config", "include_border" not in app.config)
app.hide(); app.perform_window_grab("0xdeadbeef"); pump()
check("bad window id -> window restored", app.get_visible())

# xdotool missing -> restored, not stuck hidden
old_path = os.environ["PATH"]; os.environ["PATH"] = "/nonexistent"
app._show_error = lambda *a: print("  (error dialog:", a[0] + ")")
app.hide(); app.prompt_window_selection(); pump()
os.environ["PATH"] = old_path
check("missing xdotool -> window restored", app.get_visible())

# Save path resolution
app.save_format = "png"
check("no ext -> .png", app._resolve_save_path("/t/foo") == ("/t/foo.png", "png"))
check("typed .jpg -> jpeg", app._resolve_save_path("/t/shot.jpg") == ("/t/shot.jpg", "jpeg"))
check("typed .JPEG -> jpeg", app._resolve_save_path("/t/shot.JPEG") == ("/t/shot.JPEG", "jpeg"))
check("other ext appended", app._resolve_save_path("/t/a.b") == ("/t/a.b.png", "png"))

# Selection overlay: handle flip, cancel restores, capture
app.hide()
ov = xs.SelectionOverlay(app); pump()
ov.rect_x, ov.rect_y, ov.rect_w, ov.rect_h = 100, 100, 100, 100
class E: pass
def ev(x, y, b=1): e = E(); e.x, e.y, e.button = x, y, b; return e
ov.on_button_press(None, ev(150, 100))  # 'n' handle
check("grabbed n handle", ov.active_handle == "n")
ov.on_motion_notify(None, ev(150, 250)); ov.on_motion_notify(None, ev(150, 260))
check("drag past bottom flips cleanly (200..260)", (ov.rect_y, ov.rect_h) == (200, 60))
ov.on_button_release(None, ev(150, 260)); pump()
check("control box shown", ov.control_box.get_visible())
ov.on_cancel_clicked(None); pump()
check("cancel restores main window", app.get_visible())
check("cancel keeps earlier preview", app.preview_area.get_visible())

app.hide()
ov = xs.SelectionOverlay(app); pump()
ov.rect_x, ov.rect_y, ov.rect_w, ov.rect_h = 10, 20, 30, 40
app.include_pointer = True
ov.on_capture_confirmed(None)
ctx = GLib.MainContext.default()
for _ in range(50):
    GLib.usleep(20000); pump()
check("selection capture size 30x40", (app.active_pixbuf.get_width(), app.active_pixbuf.get_height()) == (30, 40))
check("window restored after selection", app.get_visible())

# Config robustness
os.makedirs(xs.CONFIG_DIR, exist_ok=True)
open(xs.CONFIG_PATH, "w").write('["not", "a", "dict"]')
check("bad config -> defaults", xs.load_config() == xs.DEFAULT_CONFIG)
open(xs.CONFIG_PATH, "w").write('{"delay_sec": "five", "save_format": "bmp"}')
c = xs.load_config(); check("wrong types ignored", c["delay_sec"] == 0 and c["save_format"] == "png")

# Real save
p = os.path.join(os.environ["HOME"], "x.jpg")
app.active_pixbuf.savev(p, "jpeg", ["quality"], ["90"]); check("jpeg save works", os.path.getsize(p) > 0)

print("\nFAILURES:", fails if fails else "none")
