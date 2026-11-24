import helpers  # paths, a temporary home folder, English
"""Resize, and Rotate & Flip (xlcheese/xl-screenshot#8)."""
import subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk, Gdk, GdkPixbuf
import cairo
from xlshared.ui import add_icon_search_path
from xlannotate import shapes as S
from xlannotate.window import AnnotateWindow
add_icon_search_path()
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def near(a, b, tol=1e-6): return all(abs(x - y) <= tol for x, y in zip(a, b))
def settle(t=0.3):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o + 3])
def picture(w=600, h=400):
    """White, with a red block in the top-left corner and a blue one bottom-right."""
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h); cr = cairo.Context(s)
    cr.set_source_rgb(1, 1, 1); cr.paint()
    cr.set_source_rgb(1, 0, 0); cr.rectangle(0, 0, 40, 30); cr.fill()
    cr.set_source_rgb(0, 0, 1); cr.rectangle(w - 40, h - 30, 40, 30); cr.fill()
    s.flush(); return Gdk.pixbuf_get_from_surface(s, 0, 0, w, h)
RED, BLUE = (255, 0, 0), (0, 0, 255)

win = AnnotateWindow(); win.load_pixbuf(picture(), name="ops.png"); win.resize(900, 650); win.show_all(); settle(0.8)
cv = win.canvas
check("tool bar: Crop, Resize and Rotate & Flip together", win.image_tools.get_children() == [win.tool_buttons["crop"], win.resize_btn, win.rotate_btn])
arrow = S.ArrowShape(100, 100, 300, 100, stroke=(1, 0, 0, 1), size=6); arrow.set_middle(200, 40)
marks = [arrow, S.RectShape(50, 200, 100, 50, stroke=(0, 0, 1, 1), size=6), S.TextShape(400, 300, "Note", size=6),
         S.StepShape(500, 50, size=6), S.FreehandShape([(10, 10), (60, 80), (120, 40)], size=6),
         S.InkShape([(200, 300), (260, 330)], [1.0, 0.4], size=6), S.LoupeShape(300, 250, size=6),
         S.HighlightShape(20, 350, 80, 20), S.PixelateShape(450, 100, 80, 40, size=6)]
for m in marks: cv.add_shape(m.copy())
before = [m.copy() for m in cv.shapes]
def where(m):
    """Every number that says where a mark is."""
    if isinstance(m, S.LineShape): return (m.x1, m.y1, m.x2, m.y2) + tuple(m.middle())
    if isinstance(m, S.FreehandShape): return tuple(c for p in m.points for c in p)
    if isinstance(m, S.LoupeShape): return (m.cx, m.cy)
    if isinstance(m, S.StepShape): return (m.x, m.y)
    if isinstance(m, S.TextShape): b = m.bounds(); return (b[0] + b[2] / 2, b[1] + b[3] / 2)
    return (m.x, m.y, m.w, m.h)

# ---- rotate right ----
cv.transform_image("rotate-right")
b = cv.base
check("Rotate Right: 600x400 becomes 400x600", (b.get_width(), b.get_height()) == (400, 600))
check("…the top-left corner ends up top-right", pix(b, 399 - 5, 5) == RED and pix(b, 5, 599 - 5) == BLUE)
s0 = cv.shapes
check("…the step follows (500,50 -> 350,500)", near((s0[3].x, s0[3].y), (350, 500)))
check("…the box turns with it (50,200 100x50 -> 150,50 50x100)", near(where(s0[1]), (150, 50, 50, 100)))
check("…the curved arrow's ends and curve follow", near(where(s0[0]), (300, 100, 300, 300, 360, 200)))
check("…the text moves but stays upright", s0[2].text == "Note" and near(where(s0[2]), (400 - where(before[2])[1], where(before[2])[0]), 0.5))
check("…freehand and ink points follow; ink keeps its widths", near(where(s0[4])[:2], (390, 10)) and s0[5].widths == [1.0, 0.4])
check("…the loupe follows", near(where(s0[6]), (150, 300)))
for _ in range(3): cv.transform_image("rotate-right")
check("four turns: back to the start, pixels and every mark", (cv.base.get_width(), cv.base.get_height()) == (600, 400)
      and pix(cv.base, 5, 5) == RED and all(near(where(a), where(b), 1e-6) for a, b in zip(cv.shapes, before)))
cv.transform_image("rotate-left"); cv.transform_image("rotate-right")
check("Rotate Left undoes Rotate Right", all(near(where(a), where(b), 1e-6) for a, b in zip(cv.shapes, before)))

# ---- flips ----
cv.transform_image("flip-horizontal")
check("Flip Horizontally: left and right swap", pix(cv.base, 599 - 5, 5) == RED and pix(cv.base, 5, 399 - 5) == BLUE)
m0 = cv.shapes[0]
check("…the curved arrow is mirrored (still bowing up)", near(where(m0), (500, 100, 300, 100, 400, 40)))
cv.transform_image("flip-horizontal")
check("…twice is back to the start", all(near(where(a), where(b), 1e-6) for a, b in zip(cv.shapes, before)))
cv.transform_image("flip-vertical")
check("Flip Vertically: top and bottom swap", pix(cv.base, 5, 399 - 5) == RED and near(where(cv.shapes[3]), (500, 350)))
check("…the curve now bows down", cv.shapes[0].middle()[1] > 300)

# ---- undo / redo ----
undo = lambda: win.on_key_press(win, type("K", (), {"keyval": Gdk.KEY_z, "state": Gdk.ModifierType.CONTROL_MASK})())
redo = lambda: win.on_key_press(win, type("K", (), {"keyval": Gdk.KEY_z, "state": Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK})())
undo()
check("Undo puts the image and marks back", pix(cv.base, 5, 5) == RED and all(near(where(a), where(b), 1e-6) for a, b in zip(cv.shapes, before)))
redo()
check("Redo flips again", pix(cv.base, 5, 399 - 5) == RED)
undo()

# ---- resize ----
cv.resize_image(300, 200)
check("Resize to 300x200", (cv.base.get_width(), cv.base.get_height()) == (300, 200) and pix(cv.base, 3, 3) == RED)
check("…marks scale with it", near(where(cv.shapes[3]), (250, 25)) and near(where(cv.shapes[1]), (25, 100, 50, 25)))
check("…and so do line widths and sizes", abs(cv.shapes[0].size - 3) < 1e-6 and abs(cv.shapes[3].size - 3) < 1e-6)
undo()
check("Undo brings back the full size and the marks", cv.base.get_width() == 600 and all(near(where(a), where(b), 1e-6) for a, b in zip(cv.shapes, before)))
n = len(cv._undo)
check("resizing to the same size changes nothing", not cv.resize_image(600, 400) and len(cv._undo) == n)

# ---- the Resize popover ----
win.resize_btn.set_active(True); settle(0.4)
check("the Resize popover starts at the image's size", (win.resize_w.get_value_as_int(), win.resize_h.get_value_as_int(), win.resize_pct.get_value_as_int()) == (600, 400, 100))
win.resize_w.set_value(300); settle()
check("proportions locked: width 300 makes height 200 and 50%", (win.resize_h.get_value_as_int(), win.resize_pct.get_value_as_int()) == (200, 50))
win.resize_pct.set_value(200); settle()
check("200% makes 1200x800", (win.resize_w.get_value_as_int(), win.resize_h.get_value_as_int()) == (1200, 800))
win.resize_lock.set_active(False); win.resize_pct.set_value(100); win.resize_w.set_value(450); settle()
check("unlocked: the height stays put", (win.resize_w.get_value_as_int(), win.resize_h.get_value_as_int()) == (450, 400))
win.resize_apply.clicked(); settle(0.4)
check("Resize applies it and closes the popover", (cv.base.get_width(), cv.base.get_height()) == (450, 400) and not win.resize_popover.get_visible())
undo(); win.resize_lock.set_active(True)

# ---- the Rotate & Flip popover and keys ----
check("Rotate & Flip offers four choices with their keys", list(win.rotate_items) == ["rotate-left", "rotate-right", "flip-horizontal", "flip-vertical"])
win.rotate_btn.set_active(True); settle(0.3)
win.rotate_items["rotate-right"].clicked(); settle(0.3)
check("choosing Rotate Right rotates", cv.base.get_width() == 400 and not win.rotate_btn.get_popover().get_visible())
undo()
key = lambda kv, shift=False: win.on_key_press(win, type("K", (), {"keyval": kv, "state": Gdk.ModifierType.SHIFT_MASK if shift else 0})())
key(Gdk.KEY_r); check("R rotates right", cv.base.get_width() == 400 and pix(cv.base, 394, 5) == RED); undo()
key(Gdk.KEY_R, shift=True); check("Shift+R rotates left", cv.base.get_width() == 400 and pix(cv.base, 5, 594) == RED); undo()
key(Gdk.KEY_l); check("L flips horizontally", pix(cv.base, 594, 5) == RED); undo()
key(Gdk.KEY_L, shift=True); check("Shift+L flips vertically", pix(cv.base, 5, 394) == RED); undo()
key(Gdk.KEY_R); check("with Caps Lock (R without Shift) it still rotates right", pix(cv.base, 394, 5) == RED); undo()
print("FAILURES:", fails or "none")
