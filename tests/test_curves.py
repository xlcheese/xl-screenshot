import helpers  # paths, a temporary home folder, English
"""Curved arrows and lines with a middle handle (xlcheese/xl-screenshot#3)."""
import math, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk, GdkPixbuf
from xlshared.ui import add_icon_search_path
from xlannotate import shapes as S
from xlannotate.window import AnnotateWindow
add_icon_search_path()
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def near(a, b, tol=0.5): return all(abs(x - y) <= tol for x, y in zip(a, b))
def settle(t=0.3):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
def white(w=600, h=400):
    p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h); p.fill(0xffffffff); return p
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o + 3])
RED = (0.88, 0.11, 0.14, 1.0)
is_red = lambda p: p[0] > 180 and p[1] < 90 and p[2] < 90
is_white = lambda p: min(p) > 245

# ---- the marks themselves ----
a = S.ArrowShape(100, 300, 500, 300, stroke=RED, size=6)
check("a new arrow is straight, its middle handle halfway", a.bend is None and near(a.handles()["bend"], (300, 300)))
check("the middle handle is the green, shape-changing kind", a.special_handles() == {"bend"})
a.drag_handle("bend", 300, 180, a.copy())
check("dragging the middle handle bends the arrow through that point", a.bend is not None and near(a.middle(), (300, 180)))
flat = S.render_flat(white(), [a])
check("…drawn through the new middle point", is_red(pix(flat, 300, 180)))
check("…and no longer along the straight line", is_white(pix(flat, 300, 300)))
dx, dy = 500 - 300, 300 - 60; n = math.hypot(dx, dy)
check("the arrowhead points the way the curve runs at the tip", near(a.tip_direction(), (dx / n, dy / n), 1e-6))
tx, ty = a.tip_direction()
check("…the head is drawn along it", is_red(pix(flat, 500 - tx * 10, 300 - ty * 10)) and is_white(pix(flat, 465, 300)))
check("clicking on the curve selects it", a.contains(300, 182, 4))
check("…clicking where the straight line was doesn't", not a.contains(300, 300, 4))
bx, by, bw, bh = a.bounds()
check("its bounds take in the curve", by < 180 and by + bh > 300)

# stretching keeps the shape; moving keeps it too
b = a.copy(); b.drag_handle("end", 700, 300, b.copy())
check("dragging an end stretches the curve with it", near(b.middle(), (400, 120)))
b.move_by(10, 20)
check("moving keeps the curve", near(b.middle(), (410, 140)))
# snapping straight, and Shift for a centred curve
c = a.copy(); c.drag_handle("bend", 302, 304, c.copy())
check("a middle handle dragged close to the line snaps straight", c.bend is None)
c.drag_handle("bend", 300, 290, c.copy())
check("…but a small, clear bend stays", c.bend is not None)
c.drag_handle("bend", 360, 200, c.copy(), constrain=True)
check("Shift keeps the bend centred (a symmetric curve)", near(c.middle(), (300, 200)))

# a curved line, and see-through (Sheer) arrows stay one even color
line = S.LineShape(100, 100, 500, 100, stroke=RED, size=6)
line.drag_handle("bend", 300, 40, line.copy())
check("lines bend too", is_red(pix(S.render_flat(white(), [line]), 300, 40)))
dash = S.LineShape(100, 100, 500, 100, stroke=RED, size=6, dash="dashed"); dash.set_middle(300, 40)
check("a dashed curve still draws", sum(is_red(pix(S.render_flat(white(), [dash]), 300 + i, 40)) for i in range(-30, 31)) > 10)
sheer = a.copy(); sheer.stroke = (0.88, 0.11, 0.14, 0.4)
sf = S.render_flat(white(), [sheer])
shaft, head = pix(sf, 300, 180), pix(sf, 500 - tx * 12, 300 - ty * 12)
check(f"a Sheer curved arrow is one even color (shaft {shaft}, head {head})", near(shaft, head, 3) and not is_white(shaft))

# ---- in the window: the handle, undo/redo, short lines ----
win = AnnotateWindow(); win.load_pixbuf(white(), name="curve.png"); win.resize(900, 650); win.show_all(); settle(0.8)
cv = win.canvas; cv.zoom_to(1.0); settle(0.3)
cv.add_shape(S.ArrowShape(100, 300, 500, 300, stroke=RED, size=6))
win.tool_buttons["select"].set_active(True); cv.select(cv.shapes[0]); settle()
class Ev:
    def __init__(self, x, y, state=0): self.x, self.y, self.button, self.state = x, y, 1, state; self.type = Gdk.EventType.BUTTON_PRESS
def wdrag(x1, y1, x2, y2, state=0):
    cv.on_button_press(cv, Ev(x1, y1, state)); cv.on_motion(cv, Ev((x1 + x2) / 2, (y1 + y2) / 2, state))
    cv.on_motion(cv, Ev(x2, y2, state)); cv.on_button_release(cv, Ev(x2, y2, state)); settle(0.2)
class Key:
    def __init__(self, keyval, state): self.keyval, self.state = keyval, state
mx, my = cv.to_widget(300, 300)
check("the selected arrow shows its middle handle", cv.handle_at(mx, my) == "bend")
wdrag(mx, my, *cv.to_widget(300, 160))
check("dragging it on screen bends the arrow", cv.shapes[0].bend is not None and near(cv.shapes[0].middle(), (300, 160), 1))
check("…marked as a change to save", win.modified)
win.on_key_press(win, Key(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK))
check("Undo straightens it again", cv.shapes[0].bend is None)
win.on_key_press(win, Key(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK))
check("Redo bends it again", cv.shapes[0].bend is not None)
check("the saved picture has the curve", is_red(pix(cv.render_flat(), 300, 160)))
# a very short line: its ends can still be grabbed past the middle handle
cv.add_shape(S.LineShape(200, 100, 212, 100, stroke=RED, size=4)); cv.select(cv.shapes[-1]); settle()
ex, ey = cv.to_widget(212, 100)
check("a short line's end can still be grabbed", cv.handle_at(ex + 2, ey) == "end")
check("…and its middle handle too", cv.handle_at(*cv.to_widget(206, 100)) == "bend")
print("FAILURES:", fails or "none")
