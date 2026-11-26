"""Accurate and Fast Selection: the menu choice, and Fast's overlay (no
handles or buttons, the size while you drag, letting go captures)."""
import helpers  # noqa: F401  (paths, a temporary home folder, English)
import time
import xs_shim as xs
from gi.repository import Gtk

fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

def settle(sec=0.2):
    t0 = time.time()
    while time.time() - t0 < sec:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)

class E: pass
def ev(x, y, b=1): e = E(); e.x, e.y, e.button = x, y, b; return e

app = xs.XLScreenshotTool(); app.show_all(); settle(0.5)
check("Accurate Selection is the default", app.menu_accurate.get_active() and not app.fast_selection)
labels = [m.get_label() for m in app.menu_accurate.get_parent().get_children() if isinstance(m, Gtk.MenuItem)]
check("the menu has Accurate Selection then Fast Selection",
      "Accurate Selection" in labels and labels.index("Fast Selection") == labels.index("Accurate Selection") + 1)

# Accurate: handles and buttons, as before
app.hide(); ov = xs.SelectionOverlay(app); settle(0.5)
check("Accurate: the box has handles", not ov.fast and len(ov.get_handles()) == 8)
ov.destroy(); settle(0.3)

# Choosing Fast is remembered
app.menu_fast.set_active(True)
check("choosing Fast Selection is saved", app.fast_selection and xs.load_config()["fast_selection"] is True)
app2 = xs.XLScreenshotTool()
check("…and is still chosen next time", app2.menu_fast.get_active() and app2.fast_selection); app2.destroy()

# Fast: no handles; the size shows while dragging; no buttons
app.active_pixbuf = None
app.hide(); ov = xs.SelectionOverlay(app); settle(0.5)
check("Fast: no handles", ov.fast and ov.get_handles() == {})
ov.on_button_press(None, ev(100, 100)); ov.on_motion_notify(None, ev(260, 190)); settle(0.3)
check(f"Fast: the size ({ov.size_label.get_text()}) shows while dragging",
      ov.size_label.get_mapped() and ov.size_label.get_text() == "160 × 90")
check("…with no Cancel or Capture buttons", not ov.cancel_btn.get_mapped() and not ov.capture_btn.get_mapped())
ov.on_button_release(None, ev(260, 190))
t0 = time.time()
while time.time() - t0 < 3 and app.active_pixbuf is None: settle(0.05)
p = app.active_pixbuf
check("Fast: letting go captures that area (160x90)", p is not None and (p.get_width(), p.get_height()) == (160, 90))
check("…and the window comes back with the thumbnail", app.get_visible() and app.preview_area.get_visible())

# A click (or a tiny slip) doesn't capture: the overlay waits for a real drag
app.active_pixbuf = None
app.hide(); ov = xs.SelectionOverlay(app); settle(0.5)
ov.on_button_press(None, ev(300, 300)); ov.on_motion_notify(None, ev(302, 301)); ov.on_button_release(None, ev(302, 301)); settle(0.3)
check("Fast: a click captures nothing and the overlay stays up",
      app.active_pixbuf is None and ov.get_mapped() and (ov.rect_w, ov.rect_h) == (0, 0))
ov.on_button_press(None, ev(20, 30)); ov.on_motion_notify(None, ev(70, 110)); ov.on_button_release(None, ev(70, 110))
t0 = time.time()
while time.time() - t0 < 3 and app.active_pixbuf is None: settle(0.05)
p = app.active_pixbuf
check("…then a real drag captures (50x80)", p is not None and (p.get_width(), p.get_height()) == (50, 80))

# Esc still cancels
app.hide(); ov = xs.SelectionOverlay(app); settle(0.5)
ov.on_cancel_clicked(None); settle(0.3)
check("Fast: Esc cancels and brings the window back", app.get_visible())

# With a delay, Fast counts down after you let go, then captures
app.delay_sec = 1; app.active_pixbuf = None
app.hide(); ov = xs.SelectionOverlay(app); settle(0.5)
ov.on_button_press(None, ev(10, 10)); ov.on_motion_notify(None, ev(110, 60)); ov.on_button_release(None, ev(110, 60))
settle(0.4)
check("Fast with a delay: nothing yet, mid-countdown", app.active_pixbuf is None)
t0 = time.time()
while time.time() - t0 < 4 and app.active_pixbuf is None: settle(0.05)
p = app.active_pixbuf
check("…then the capture (100x50)", p is not None and (p.get_width(), p.get_height()) == (100, 50))
app.delay_sec = 0

app.menu_accurate.set_active(True)
check("back to Accurate is saved", not app.fast_selection and xs.load_config()["fast_selection"] is False)
print("FAILURES:", fails or "none")
