import helpers  # paths, a temporary home folder, English
"""The speed-sensitive ink pen (xlcheese/xl-screenshot#7)."""
import subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk, GdkPixbuf
from xlshared.ui import add_icon_search_path
from xlannotate import shapes as S
from xlannotate.window import AnnotateWindow
add_icon_search_path()
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.3):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
def white(w=600, h=400):
    p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h); p.fill(0xffffffff); return p
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o + 3])
def thickness(pb, x, y_from=0, y_to=400):
    """How many pixels of ink a column crosses."""
    return sum(1 for y in range(y_from, y_to) if min(pix(pb, x, y)) < 200)

check("slow is wider than fast", S.ink_width_factor(speed=100) > S.ink_width_factor(speed=2000))
check("…and never thinner than a quarter", S.ink_width_factor(speed=1e9) == S.INK_THINNEST)
check("pen pressure: harder is wider", S.ink_width_factor(pressure=0.9) > S.ink_width_factor(pressure=0.2))

win = AnnotateWindow(); win.load_pixbuf(white(), name="ink.png"); win.resize(900, 650); win.show_all(); settle(0.8)
cv = win.canvas; cv.zoom_to(1.0); settle(0.3)
names = [n for n, b in sorted(win.tool_buttons.items(), key=lambda kv: kv[1].get_parent().get_children().index(kv[1]))
         if b.get_parent() is win.tool_buttons["freehand"].get_parent()]
check("an Ink button sits right after Freehand", names.index("ink") == names.index("freehand") + 1)
check("…with its own icon", Gtk.IconTheme.get_default().has_icon("xl-annotate-ink-symbolic"))

class Ev:
    def __init__(self, x, y, t, pressure=None):
        self.x, self.y, self.time, self.button, self.state = x, y, t, 1, 0
        self.type = Gdk.EventType.BUTTON_PRESS; self._p = pressure
    def get_axis(self, axis):
        return (self._p is not None, self._p or 0.0)
def stroke(points, pressure=None):
    """points: (x, y, ms) in image pixels (the view is 1:1)."""
    (x, y, t), rest = points[0], points[1:]
    wx, wy = cv.to_widget(x, y)
    cv.on_button_press(cv, Ev(wx, wy, t, pressure))
    for x, y, t in rest:
        cv.on_motion(cv, Ev(*cv.to_widget(x, y), t, pressure))
    cv.on_button_release(cv, Ev(*cv.to_widget(x, y), t, pressure)); settle(0.2)

win.tool_buttons["ink"].set_active(True); win.color_buttons["Black"].set_active(True); settle()
win.size_scale.set_value(6); settle()
check("Ink has no dash styles", not win.dash_buttons["dashed"].get_sensitive())
# slowly from x=50 to 250 (100 px a second), then quickly to 550 (3000 px a second): a straight line
pts = [(50 + 5 * i, 200, 1000 + 50 * i) for i in range(41)]                  # slow
pts += [(250 + 15 * i, 200, 3000 + 5 * i) for i in range(1, 21)]              # fast
stroke(pts)
ink = cv.shapes[-1]
check("an ink stroke was added", isinstance(ink, S.InkShape) and len(cv.shapes) == 1)
check("…and a straight one isn't tidied into a line (handwriting stays handwriting)", isinstance(ink, S.InkShape))
w = ink.widths
slow = [wi for (x, y), wi in zip(ink.points, w) if 100 < x < 230]
fast = [wi for (x, y), wi in zip(ink.points, w) if 420 < x < 540]
check(f"drawn slowly it's wide, quickly it's thin ({min(slow):.2f} vs {max(fast):.2f})", min(slow) > max(fast) * 1.8)
check("the width flows, no sudden jumps", max(abs(a - b) for a, b in zip(w, w[1:])) < 0.15)
flat = cv.render_flat()
t_slow, t_fast = thickness(flat, 150), thickness(flat, 500)
check(f"on the picture: thick where slow ({t_slow}px), thin where fast ({t_fast}px)", t_slow >= 2 * t_fast and t_fast >= 1)
# the size slider sets the full width
big = S.InkShape(ink.points, ink.widths, stroke=(0, 0, 0, 1), size=12)
check("a bigger size draws a wider line", thickness(S.render_flat(white(), [big]), 150) > t_slow)
# a drawing tablet: pressure, not speed
cv.shapes.clear(); cv.queue_draw()
stroke([(50 + 5 * i, 100, 1000 + 5 * i) for i in range(41)], pressure=0.95)   # fast but pressing hard
stroke([(50 + 5 * i, 300, 1000 + 500 * i) for i in range(41)], pressure=0.1)  # slow but light
hard, light = cv.shapes[-2], cv.shapes[-1]
check("with a tablet pen, pressure sets the width (hard and fast is wider than light and slow)",
      min(hard.widths[5:-5]) > max(light.widths[5:-5]) * 2)

# the usual mark behavior
mark = S.InkShape([(100 + i, 200 + (i % 7)) for i in range(0, 300, 3)], [0.4 + 0.6 * (i % 50) / 50 for i in range(0, 300, 3)],
                  stroke=(0.88, 0.11, 0.14, 0.4), size=8)
sheer = S.render_flat(white(), [mark])
inked = [pix(sheer, x, 202) for x in range(120, 380, 7) if min(pix(sheer, x, 202)) < 250]
check("a Sheer ink line is one even color (no darker overlaps)", inked and max(p[1] for p in inked) - min(p[1] for p in inked) <= 3)
check("clicking on it selects it", mark.contains(200, 203, 3) and not mark.contains(200, 240, 3))
moved = mark.copy(); moved.move_by(10, 20)
check("moving keeps the widths", moved.widths == mark.widths and moved.points[0] == (110, 220))
st = mark.copy(); st.drag_handle("e", st._box()[2] * 1.0 + 100, 200, mark.copy())
check("stretching keeps the widths", st.widths == mark.widths and st._box()[2] > mark._box()[2] + 90)
shadow = S.InkShape(mark.points, mark.widths, stroke=(0, 0, 0, 1), size=8, shadow=True)
check("a shadow draws under it", min(pix(S.render_flat(white(), [shadow]), 200, 214)) < 250)
cv.shapes.clear(); stroke(pts); n = len(cv.shapes)
win.on_key_press(win, type("K", (), {"keyval": Gdk.KEY_z, "state": Gdk.ModifierType.CONTROL_MASK})())
check("Undo removes the stroke", len(cv.shapes) == n - 1)
print("FAILURES:", fails or "none")
