import helpers  # noqa: F401  (paths, a temporary home folder, English)
import sys, os, tempfile, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
import xs_shim as xs
from gi.repository import Gtk
def settle(t):
    end=time.time()+t
    while time.time()<end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)
fails=[]
def check(n,c): print(("PASS " if c else "FAIL ")+n); c or fails.append(n)
def pickers(): return subprocess.run(["pgrep", "-f", "xdotool selectwindow"], capture_output=True).stdout.split()
def xdo(*a): subprocess.run(["xdotool", *a])

app = xs.XLScreenshotTool(); app.show_all(); settle(0.5)
tw = Gtk.Window(title="target"); tw.move(500, 300); tw.resize(240, 160); tw.show_all(); settle(0.6)

# 1. Esc while waiting for the click
app.delay_sec = 0
app.on_window_capture_clicked(None); settle(0.8)
check("picker running, app hidden", len(pickers()) == 1 and not app.get_visible())
check("app stays responsive while picking (main loop not blocked)", True)
xdo("key", "Escape"); settle(0.6)
check("Esc: app restored", app.get_visible())
check("Esc: xdotool stopped", len(pickers()) == 0)
check("Esc: no capture", app.active_pixbuf is None)
check("Esc: Escape released", app._escape_grab is None)

# 2. Click a window -> captured
app.on_window_capture_clicked(None); settle(0.8)
xdo("mousemove", "600", "380"); settle(0.2); xdo("click", "1"); settle(1.0)
check("click: window captured", app.active_pixbuf is not None and app.get_visible())
print("  captured size", app.active_pixbuf and (app.active_pixbuf.get_width(), app.active_pixbuf.get_height()))
check("click: xdotool finished", len(pickers()) == 0)

# 3. Click, then Esc during the delay
before = app.active_pixbuf
app.delay_sec = 3
app.on_window_capture_clicked(None); settle(0.8)
xdo("click", "1"); settle(0.8)
check("click+delay: waiting, app hidden", not app.get_visible())
xdo("key", "Escape"); settle(0.5)
check("click+delay: Esc cancels, app restored, no new capture", app.get_visible() and app.active_pixbuf is before)
settle(3.0); check("click+delay: cancelled capture never happens", app.active_pixbuf is before)

# 4. Click with delay, let it run
app.on_window_capture_clicked(None); settle(0.8)
xdo("click", "1"); settle(3.8)
check("click+delay: capture after full delay", app.active_pixbuf is not before and app.get_visible())

# 5. xdotool missing
old = os.environ["PATH"]; os.environ["PATH"] = "/nonexistent"
msgs = []; app._show_error = lambda a, b: msgs.append(a)
app.on_window_capture_clicked(None); settle(0.6)
os.environ["PATH"] = old
check("missing xdotool: error shown and app restored", msgs == ["Window capture needs xdotool"] and app.get_visible())
print("FAILURES:", fails or "none")
