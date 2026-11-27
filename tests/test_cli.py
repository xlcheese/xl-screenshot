"""Command-line captures: xl-screenshot --area 100,100,400,300 --file x.png
and friends. Run as a user would (the launcher, as a separate process), on
X11 without and with Cinnamon's screenshot service (a stand-in)."""
import helpers  # noqa: F401  (paths, a temporary home folder, English)
import json, os, subprocess, sys, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
from xlscreenshot import cli, cinnamon_service as CS

fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.3):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)

OUT = os.path.join(os.environ["HOME"], "out"); os.makedirs(OUT)
LAUNCHER = os.path.join(helpers.BIN, "xl-screenshot")
env = dict(os.environ, NO_AT_BRIDGE="1")
def run(*args, stdin=None):
    p = subprocess.run([sys.executable, LAUNCHER, *args], capture_output=True, env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr.decode()
def size(path):
    try:
        p = GdkPixbuf.Pixbuf.new_from_file(path); return p.get_width(), p.get_height()
    except Exception:
        return None
def path_of(out): return out.decode().strip()

# Which command lines are captures, and which open the app as before
check("no options, --selection, --tray, --version: the app as before",
      not any(cli.wants_cli(["x", *a]) for a in ([], ["--selection"], ["-s"], ["--tray"], ["-v"], ["-s", "-t"])))
check("any capture option, a file name, or --help: a command-line capture",
      all(cli.wants_cli(["x", *a]) for a in (["--area", "1,1,2,2"], ["--screens"], ["x.png"], ["-s", "-F", "a.png"], ["--help"])))

rc, out, err = run("--help")
check("--help lists the capture options", rc == 0 and b"--area" in out and b"--screens" in out and b"--selection" in out)
rc, out, err = run("--version")
check(f"--version ({out.decode().strip()})", rc == 0 and out.startswith(b"xl-Screenshot "))

# --list-screens: the big numbers too, but only when a person reads it in a terminal
import pty
numbers = lambda: subprocess.run(["pgrep", "-f", "show-screen-numbers"], capture_output=True).stdout.split()
def number_windows():
    tree = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True).stdout
    return tree.count("xl-Screenshot screen number")
def in_terminal(*args):
    """Run with its output going to a terminal (a pseudo-terminal), as typed by a person."""
    master, slave = pty.openpty()
    p = subprocess.run([sys.executable, LAUNCHER, *args], stdout=slave, stderr=subprocess.PIPE, env=env, timeout=30)
    os.close(slave)
    out = b""
    try:
        while True:
            chunk = os.read(master, 4096)
            if not chunk: break
            out += chunk
            if len(chunk) < 4096: break
    except OSError:
        pass
    os.close(master)
    return p.returncode, out.decode()
def screen_pixel(x, y):
    pb = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), x, y, 1, 1)
    return tuple(pb.get_pixels()[:3])
before = screen_pixel(640, 400)
t0 = time.time()
rc, out = in_terminal("--list-screens")
took = time.time() - t0
check(f"in a terminal: the list prints and the prompt comes back at once ({took:.1f} s)",
      rc == 0 and "1: 1280x800+0+0" in out and took < 2.5)
shown = False
for _ in range(30):
    if number_windows(): shown = True; break
    time.sleep(0.1)
settle(0.5)
check("…and the screen shows its big number", shown and number_windows() == 1)
check("…drawn in the middle of the screen", screen_pixel(640, 400) != before)
end = time.time() + 6
while time.time() < end and numbers(): time.sleep(0.2)
check("…for a few seconds, then it's gone", not numbers() and number_windows() == 0)
rc, out, err = run("--list-screens")
time.sleep(1.5)
check("read by a script (not a terminal): no numbers", rc == 0 and not numbers())
rc, out = in_terminal("--list-screens", "--no-identify")
time.sleep(1.5)
check("--no-identify: no numbers, even in a terminal", rc == 0 and "1: 1280x800" in out and not numbers())
rc, out, err = run("--identify")
shown = False
for _ in range(30):
    if number_windows(): shown = True; break
    time.sleep(0.1)
check("--identify: the list, and the numbers even from a script", rc == 0 and b"1: 1280x800" in out and shown)
subprocess.run(["pkill", "-f", "show-screen-numbers"]); time.sleep(0.5)

# X11, without the service
rc, out, err = run("--list-screens")
check(f"--list-screens: '{out.decode().strip()}'", rc == 0 and out.decode().strip() == "1: 1280x800+0+0  (primary)")
rc, out, err = run("--area", "100,100,400,300", "--file", os.path.join(OUT, "area.png"))
check("--area X,Y,W,H --file: saved, at that size", rc == 0 and size(path_of(out)) == (400, 300))
check("…and the path is printed", path_of(out) == os.path.join(OUT, "area.png"))
rc, out, err = run("-a", "100,100,400,300", "-F", os.path.join(OUT, "area.png"))
check(f"scrot's -a and -F work too; an existing file isn't replaced ({os.path.basename(path_of(out))})",
      rc == 0 and path_of(out) == os.path.join(OUT, "area_1.png"))
rc, out, err = run("-a", "0,0,10,10", "-o", "-F", os.path.join(OUT, "area.png"))
check("--overwrite replaces it", rc == 0 and path_of(out) == os.path.join(OUT, "area.png") and size(path_of(out)) == (10, 10))
rc, out, err = run("--area", "5,5,64,48", os.path.join(OUT, "shot_$wx$h_%Y.png"))
check(f"a bare FILE, with $w, $h and %Y ({os.path.basename(path_of(out))})",
      rc == 0 and os.path.basename(path_of(out)) == f"shot_64x48_{time.strftime('%Y')}.png")
rc, out, err = run("--area", "120x80+5+6", "-F", os.path.join(OUT, "geom.png"))
check("--area also takes WxH+X+Y, as --list-screens prints it (120x80)", rc == 0 and size(path_of(out)) == (120, 80))
rc, out, err = run("--screens")
folder = os.path.join(os.environ["HOME"], "Pictures", "xl-Screenshot")
check(f"--screens with no file: into Pictures/xl-Screenshot ({os.path.basename(path_of(out))})",
      rc == 0 and os.path.dirname(path_of(out)) == folder and size(path_of(out)) == (1280, 800))
rc, out, err = run("--screen", "1", "--format", "jpg", "-q", "50", "-F", os.path.join(OUT, "one"))
check("--screen 1, --format jpg: saved as one.jpg", rc == 0 and path_of(out) == os.path.join(OUT, "one.jpg")
      and open(path_of(out), "rb").read(2) == b"\xff\xd8")
rc, out, err = run("--screen", os.path.join(OUT, "pointer.png"))
check("--screen with no number: the pointer's screen", rc == 0 and size(path_of(out)) == (1280, 800))
rc, out, err = run("-a", "0,0,50,40", "-F", "-")
check("--file -: the PNG on standard output, nothing else", rc == 0 and out[:4] == b"\x89PNG")
loader = GdkPixbuf.PixbufLoader(); loader.write(out); loader.close()
check("…and it's the right size", (loader.get_pixbuf().get_width(), loader.get_pixbuf().get_height()) == (50, 40))
rc, out, err = run("-a", "0,0,30,20", "--pointer", "-F", os.path.join(OUT, "ptr.png"))
check("--pointer works", rc == 0 and size(path_of(out)) == (30, 20))

rc, out, err = run("-a", "0,0,40,30", "--annotate", "-F", os.path.join(OUT, "ann.png"))
ann = []
for _ in range(40):
    ann = subprocess.run(["pgrep", "-af", "xl-annotate"], capture_output=True).stdout.decode().split("\n")
    ann = [l for l in ann if os.path.join(OUT, "ann.png") in l]
    if ann: break
    time.sleep(0.25)
check("--annotate: saved, and xl-Annotate opens it", rc == 0 and size(path_of(out)) == (40, 30) and len(ann) == 1)
subprocess.run(["pkill", "-f", "xl-annotate"])
# Mistakes: a clear message and exit code 2
for args, words in ((["--screen", "3"], "no screen 3"), (["--screen", "0"], "numbered from 1"),
                    (["--area", "1,2,3"], "X,Y,W,H"), (["--area", "1,2,0,5"], "more than 0"),
                    (["--screens", "--area", "1,1,5,5"], "not allowed with"),
                    (["-a", "1,1,5,5", "-F", "-", "--annotate"], "needs a file"),
                    (["-q", "200", "-a", "1,1,5,5"], "1 to 100")):
    rc, out, err = run(*args)
    check(f"{' '.join(args)}: exit 2, says '{words}'", rc == 2 and words in err and not out)

# Windows (X11): the focused one, and one by its id
w = Gtk.Window(title="CLI target"); w.set_default_size(320, 200); w.move(200, 150); w.show_all(); w.present()
settle(1.5)
xid = w.get_window().get_xid()
rc, out, err = run("--window-id", hex(xid), "-F", os.path.join(OUT, "byid.png"))
s = size(path_of(out)) if rc == 0 else None
check(f"--window-id: that window, with its title bar ({s})", s is not None and s[0] >= 320 and s[1] >= 200 and s[1] < 300)
rc, out, err = run("--focused", "-F", os.path.join(OUT, "focused.png"))
check(f"--focused: the focused window ({size(path_of(out)) if rc == 0 else err.strip()})",
      rc == 0 and size(path_of(out)) == s)
rc, out, err = run("--window-id", "0x1", "-F", os.path.join(OUT, "none.png"))
check("--window-id of no window: exit 1, nothing saved", rc == 1 and not os.path.exists(os.path.join(OUT, "none.png")))

# The clipboard: still there after xl-screenshot has exited
rc, out, err = run("-a", "10,10,77,33", "--clipboard")
check("--clipboard on its own: nothing saved, nothing printed", rc == 0 and not out)
clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
img = None
for _ in range(30):
    img = clipboard.wait_for_image()
    if img is not None: break
    time.sleep(0.2)
check("…and the image can be pasted after it has exited", img is not None and (img.get_width(), img.get_height()) == (77, 33))
holders = lambda: subprocess.run(["pgrep", "-f", "hold-clipboard"], capture_output=True).stdout.split()
check("…kept by a small helper (no clipboard manager here)", len(holders()) == 1)
clipboard.set_text("something else", -1); clipboard.store(); settle(1.5)
check("…which goes once something else is copied", len(holders()) == 0)

# --selection: the app's own Selection, drawn here as a user would
args = cli.build_parser().parse_args(["--selection", "-F", os.path.join(OUT, "sel.png")])
cap = cli.Capture(args); cap.start(); settle(1)
from xlscreenshot.selection import SelectionOverlay
ovs = [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_mapped()]
check("--selection: the Selection overlay comes up", len(ovs) == 1)
class E: pass
def ev(x, y): e = E(); e.x, e.y, e.button = x, y, 1; return e
if ovs:
    ov = ovs[0]
    ov.on_button_press(None, ev(40, 50)); ov.on_motion_notify(None, ev(240, 150)); ov.on_button_release(None, ev(240, 150)); settle(0.3)
    ov.on_capture_confirmed(None)
end = time.time() + 5
while time.time() < end and not cap.done: settle(0.1)
check("…and gives the area drawn (200x100)", cap.result is not None and (cap.result.get_width(), cap.result.get_height()) == (200, 100))
check("…saved where asked", cap.result is not None and cli.save(cap.result, args) == os.path.join(OUT, "sel.png"))
args = cli.build_parser().parse_args(["--selection"])
cap = cli.Capture(args); cap.start(); settle(1)
ovs = [t for t in Gtk.Window.list_toplevels() if isinstance(t, SelectionOverlay) and t.get_mapped()]
if ovs: ovs[0].on_cancel_clicked(None)
end = time.time() + 3
while time.time() < end and not cap.done: settle(0.1)
check("--selection, Esc: nothing captured", cap.done and cap.result is None)

# With Cinnamon's service (stand-in): the right calls, in desktop units
LOG = os.path.join(os.environ["HOME"], "calls.txt")
fake = subprocess.Popen([sys.executable, os.path.join(helpers.TESTS, "fake_cinnamon_screenshot.py"), LOG, "ok"])
for _ in range(50):
    if CS.CinnamonScreenshot.find(timeout_ms=200) is not None: break
    time.sleep(0.1)
calls = lambda: [json.loads(l) for l in open(LOG)] if os.path.exists(LOG) else []
rc, out, err = run("--area", "100,100,400,300", "-p", "-F", os.path.join(OUT, "svc-area.png"))
c = calls()[-1] if calls() else None
check(f"service: --area asks Cinnamon for that area, with the pointer ({c and c[1][:5]})",
      rc == 0 and c and c[0] == "ScreenshotArea" and c[1][:5] == [100, 100, 400, 300, True] and size(path_of(out)) == (400, 300))
rc, out, err = run("--screens", "-F", os.path.join(OUT, "svc-all.png"))
check("service: --screens is Cinnamon's Screenshot", rc == 0 and calls()[-1][0] == "Screenshot" and size(path_of(out)) == (1280, 800))
rc, out, err = run("--focused", "--shadow", "-F", os.path.join(OUT, "svc-focused.png"))
check("service: --focused --shadow is Cinnamon's ScreenshotWindow, with the shadow",
      rc == 0 and calls()[-1][0] == "ScreenshotWindow" and calls()[-1][1][0] is True and size(path_of(out)) == (340, 240))
rc, out, err = run("--window", "-F", os.path.join(OUT, "svc-window.png"))
names = [c[0] for c in calls()[-2:]]
check(f"service: --window picks with Cinnamon's picker, then captures it ({names})",
      rc == 0 and names == ["SelectWindow", "ScreenshotWindowById"] and size(path_of(out)) == (300, 200))
rc, out, err = run("-a", "1,2,30,40", "--clipboard")
c = calls()[-1]
check("service: --clipboard has Cinnamon copy it (it stays after we exit; works on Wayland too)",
      rc == 0 and c[0] == "ScreenshotArea" and c[1][-1] is True and not out)
check("…so no helper of ours is needed", len(holders()) == 0)
rc, out, err = run("-a", "1,2,30,40", "-F", os.path.join(OUT, "nocopy.png"))
check("…and without --clipboard, Cinnamon doesn't copy", rc == 0 and calls()[-1][1][-1] is False)
leftover = [f for f in os.listdir(GLib.get_user_runtime_dir() or GLib.get_tmp_dir()) if f.startswith("xl-screenshot-")]
check("no temporary files left behind", not leftover)
fake.kill()
print("FAILURES:", fails or "none")
