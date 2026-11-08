import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
import xs_shim as xs
from gi.repository import Gtk, Gdk
def settle(t=0.5):
    end=time.time()+t
    while time.time()<end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)
class E: pass
def ev(x,y): e=E(); e.x,e.y,e.button=x,y,1; return e
fails=[]
def check(n,c): print(("PASS " if c else "FAIL ")+n); c or fails.append(n)
app = xs.XLScreenshotTool(); app.show_all(); settle(); app.hide()
ov = xs.SelectionOverlay(app); settle()
# first drag: draw a new box, release
ov.on_button_press(None, ev(300,200)); ov.on_motion_notify(None, ev(700,450)); ov.on_button_release(None, ev(700,450)); settle()
a = ov.control_box.get_allocation(); print("  rect 300,200 400x250 -> buttons", a.x, a.y, a.width, a.height)
check("first draw: buttons below selection", a.y >= 450)
from xlscreenshot.selection import PANEL_PAD
check("first draw: the panel's right edge lines up with the selection's", a.x + a.width + PANEL_PAD == 700 and a.x >= 300)
check("…with a gap between the selection and the panel", a.y - PANEL_PAD > 450)
w = ov.get_window(); Gdk.pixbuf_get_from_window(w,0,0,w.get_width(),w.get_height()).savev(os.path.join(helpers.PICTURES, "overlay.png"),"png",[],[])
# selection near bottom: buttons should go above
ov.on_button_press(None, ev(100,600)); ov.on_motion_notify(None, ev(500,790)); ov.on_button_release(None, ev(500,790)); settle()
a = ov.control_box.get_allocation(); print("  rect near bottom -> buttons", a.x, a.y)
check("near bottom edge: panel above the selection", a.y + a.height + PANEL_PAD <= 600)
print("FAILURES:", fails or "none")
