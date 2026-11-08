import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time
import xs_shim as xs
from gi.repository import Gtk, GLib, GdkPixbuf
SP = helpers.PICTURES
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL)
if os.environ.get("COMP"): subprocess.Popen(["xcompmgr"], stderr=subprocess.DEVNULL)
time.sleep(1)

fails = []
def check(n, c):
    print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.6):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)

def drawn_size(app):
    a = app.preview_area; img = app.active_pixbuf
    s = min(1.0, (a.get_allocated_width()-2)/img.get_width(), (a.get_allocated_height()-2)/img.get_height())
    s = max(s, app.thumb_scale)
    return round(img.get_width()*s), round(img.get_height()*s)

def shot(app, name):
    w = app.get_window(); pb = __import__("gi.repository.Gdk", fromlist=["Gdk"]).pixbuf_get_from_window(w, 0, 0, w.get_width(), w.get_height())
    pb.savev(os.path.join(SP, name), "png", [], [])

# a colourful 760x500 test image
img = GdkPixbuf.Pixbuf.new_from_file_at_scale("/usr/share/icons/hicolor/256x256/apps/" + sorted(os.listdir("/usr/share/icons/hicolor/256x256/apps"))[0], 760, 500, False) if os.path.isdir("/usr/share/icons/hicolor/256x256/apps") and os.listdir("/usr/share/icons/hicolor/256x256/apps") else None
if img is None:
    img = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 760, 500); img.fill(0x3366ccff)

app = xs.XLScreenshotTool(); app.show_all(); settle()
app.update_screenshot_buffer(img); settle()
default = app.get_size(); print("  default window", default, "drawn", drawn_size(app))
check("default thumbnail is 408x268", drawn_size(app) == (408, 268))
shot(app, "resize_default.png")

app.resize(3000, 3000); settle()
big = app.get_size(); print("  after resize(3000,3000)", big, "drawn", drawn_size(app))
check("grows to exactly 1:1", drawn_size(app) == (760, 500))
check("window capped (not 3000 wide)", big[0] < 3000 and big[1] < 3000)
shot(app, "resize_full.png")

app.resize(600, 500); settle()
print("  mid", app.get_size(), "drawn", drawn_size(app))
mid = drawn_size(app); check("mid size between default and 1:1", 408 < mid[0] < 760)

app.resize(1, 1); settle()
print("  after resize(1,1)", app.get_size(), "drawn", drawn_size(app))
check("cannot shrink thumbnail below default", drawn_size(app) == (408, 268))

# new small capture resets size and limit
small = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 120, 90); small.fill(0xcc3333ff)
app.resize(1500, 900); settle()
app.update_screenshot_buffer(small); settle()
print("  small capture window", app.get_size(), "drawn", drawn_size(app))
check("small capture shown 1:1", drawn_size(app) == (120, 90))
app.resize(3000, 3000); settle()
print("  small after resize(3000,3000)", app.get_size())
check("small capture: window can't be enlarged", app.get_size()[1] <= default[1])
shot(app, "resize_small.png")

# new big capture after small one: limit raised again
app.update_screenshot_buffer(img); settle()
app.resize(3000, 3000); settle()
check("limit re-computed for new capture", drawn_size(app) == (760, 500))
def aligned():
    a = app.preview_area.get_allocation(); b = app.btn_cluster.get_allocation()
    print("  thumb area x/w", a.x, a.width, " buttons x/w", b.x, b.width)
    return a.x == b.x and a.width == b.width
app.resize(1400, 900); settle()
app.update_screenshot_buffer(img); settle()
check("after capture from a wide window, thumbnail lines up with buttons", aligned())
tall = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 1920, 1080); tall.fill(0x22aa44ff)
app.update_screenshot_buffer(tall); settle()
check("full-HD capture lines up with buttons", aligned())
shot(app, "aligned.png")
print("\nFAILURES:", fails or "none")
