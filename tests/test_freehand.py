import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time, math, random
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from xlshared.ui import add_icon_search_path
from xlannotate import shapes as S, config as C
from xlannotate.window import AnnotateWindow
from gi.repository import Gtk, Gdk, GdkPixbuf
add_icon_search_path()
SP = helpers.PICTURES
fails = []
def check(n, c):
    print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.3):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.01)
class Ev:
    def __init__(self, x=0, y=0, button=1, type=Gdk.EventType.BUTTON_PRESS, state=0, keyval=0):
        self.x, self.y, self.button, self.type, self.state, self.keyval = x, y, button, type, state, keyval
CTRL = Gdk.ModifierType.CONTROL_MASK; SHIFT = Gdk.ModifierType.SHIFT_MASK
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o+3])
def white(w, h):
    p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h); p.fill(0xffffffff); return p
def stroke(cv, pts):
    """Draw with the mouse through image points."""
    w = [cv.to_widget(*p) for p in pts]
    cv.on_button_press(cv, Ev(*w[0]))
    for p in w[1:]: cv.on_motion(cv, Ev(*p))
    cv.on_button_release(cv, Ev(*w[-1]))
def key(win, keyval, state=0): return win.on_key_press(win, Ev(keyval=keyval, state=state))
def wobbly(pts, amp=2.0, seed=1):
    r = random.Random(seed); ph = r.uniform(0, 6)
    return [(x + amp * 0.6 * math.sin(i / 8 + ph) + r.uniform(-0.6, 0.6), y + amp * math.sin(i / 8 + ph) + r.uniform(-0.6, 0.6)) for i, (x, y) in enumerate(pts)]
def seg(x1, y1, x2, y2, n): return [(x1 + (x2 - x1) * t / n, y1 + (y2 - y1) * t / n) for t in range(n + 1)]

win = AnnotateWindow(); win.ask_unsaved = lambda: "discard"
win.show_all(); win.load_pixbuf(white(640, 420), name="w.png"); settle(0.5)
cv = win.canvas

# ---- Tool bar ----
check("Freehand button sits after Line", "freehand" in win.tool_buttons and
      win.tool_buttons["line"].translate_coordinates(win, 0, 0)[0] < win.tool_buttons["freehand"].translate_coordinates(win, 0, 0)[0]
      < win.tool_buttons["rectangle"].translate_coordinates(win, 0, 0)[0])
tbw = win.toolbar.get_preferred_width()[0]
n_buttons = sum(len(g.get_children()) if isinstance(g, Gtk.Box) and g.get_style_context().has_class("linked") else 0
                for g in win.toolbar.get_children())
print(f"   toolbar: {tbw}px")
holder = Gtk.Window(); probe = Gtk.Button(); probe.set_image(Gtk.Image.new_from_icon_name("edit-undo-symbolic", Gtk.IconSize.BUTTON)); holder.add(probe)
probe_pad = probe.get_style_context().get_padding(Gtk.StateFlags.NORMAL)
theme = (probe_pad.left, probe_pad.right, probe_pad.top, probe_pad.bottom)
def padding(b):
    p = b.get_style_context().get_padding(Gtk.StateFlags.NORMAL); return (p.left, p.right, p.top, p.bottom)
check("tool bar buttons: the theme's normal icon-button size (not shrunk)", padding(win.undo_btn) == theme
      and padding(win.tool_buttons["arrow"]) == theme and padding(win.dash_buttons["dashed"]) == theme)
flat = [b for g in win.toolbar.get_children() for b in (g.get_children() if isinstance(g, Gtk.Box) else [g]) if isinstance(b, Gtk.Button)]
check("every tool bar button is flat (frame only on hover)", flat and all(b.get_relief() == Gtk.ReliefStyle.NONE for b in flat))
check("…and not joined into strips (so hovered buttons keep all their edges)",
      not any(g.get_style_context().has_class("linked") for g in win.toolbar.get_children() if isinstance(g, Gtk.Box)))
check("zoom buttons, Solid/Sheer and Aa keep their frames", win.zoom_label_btn.get_relief() == Gtk.ReliefStyle.NORMAL
      and win.opacity_buttons["solid"].get_relief() == Gtk.ReliefStyle.NORMAL and win.font_button.get_relief() == Gtk.ReliefStyle.NORMAL)

# ---- Freehand drawing ----
win.tool_buttons["freehand"].set_active(True)
win.set_color_target("line"); win.color_buttons["Purple"].set_active(True); win.size_scale.set_value(5)
wave = [(40 + i * 3, 80 + 25 * math.sin(i / 6)) for i in range(80)]
stroke(cv, wave)
f = cv.shapes[-1] if cv.shapes else None
check("freehand: a wavy line stays a drawing", isinstance(f, S.FreehandShape))
check("…in the chosen colour and size", f.stroke[:3] == tuple(dict(S.COLORS)["Purple"]) and f.size == 5)
near = lambda a, b: abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6
check("…smoothed (more points than drawn, ends kept)", len(f.points) > len(wave) and near(f.points[0], wave[0]) and near(f.points[-1], wave[-1]))
print(f"   points: drawn {len(wave)}, after smoothing {len(f.points)}")
flat = cv.render_flat()
check("drawn on the image", pix(flat, 40 + 20 * 3, 80 + 25 * math.sin(20 / 6))[0] < 200)
check("no tidy offer for a plain drawing", cv._tidy_popover is None)
win.tool_buttons["select"].set_active(True)
x, y = wave[40]
cv.on_button_press(cv, Ev(*cv.to_widget(x, y))); cv.on_button_release(cv, Ev(*cv.to_widget(x, y)))
check("select: click on the drawing picks it", cv.selected is f)
check("…8 handles to stretch it", len(f.handles()) == 8)
x0, y0, x1, y1 = f._box()
ex, ey = cv.to_widget(x1, (y0 + y1) / 2)
cv.on_button_press(cv, Ev(ex, ey)); cv.on_motion(cv, Ev(ex + 60, ey)); cv.on_button_release(cv, Ev(ex + 60, ey))
nx0, ny0, nx1, ny1 = f._box()
check("drag the right handle: drawing stretched wider, same height", abs((nx1 - nx0) - (x1 - x0 + 60)) < 0.5 and abs((ny1 - ny0) - (y1 - y0)) < 0.5)
key(win, Gdk.KEY_z, CTRL)
f = next(s for s in cv.shapes if isinstance(s, S.FreehandShape))
check("undo the stretch", abs(f._box()[2] - x1) < 0.01)
cv.select(f)
sx, sy = cv.to_widget(*f.handles()["se"])
w0, h0 = x1 - x0, y1 - y0
cv.on_button_press(cv, Ev(sx, sy, state=SHIFT)); cv.on_motion(cv, Ev(sx + 120, sy + 5, state=SHIFT)); cv.on_button_release(cv, Ev(sx + 120, sy + 5, state=SHIFT))
bx0, by0, bx1, by1 = f._box()
check("Shift + corner: keeps its proportions", abs((bx1 - bx0) / (by1 - by0) - w0 / h0) < 0.02)
key(win, Gdk.KEY_z, CTRL)
win.dash_buttons["dotted"].set_active(True)
f = next(s for s in cv.shapes if isinstance(s, S.FreehandShape)); cv.select(f); win.dash_buttons["dotted"].set_active(True)
check("restyle: dotted", f.dash == "dotted")
cv.select(None)

# ---- Tidy-up ----
win.tool_buttons["freehand"].set_active(True); win.dash_buttons["solid"].set_active(True)
n = len(cv.shapes)
circle = wobbly([(500 + 60 * math.cos(a), 300 + 45 * math.sin(a)) for a in [0.4 + 2 * math.pi * 1.08 * i / 90 for i in range(91)]])
stroke(cv, circle); settle(0.2)
e = cv.shapes[-1]
check("a rough circle becomes a clean ellipse", isinstance(e, S.EllipseShape) and len(cv.shapes) == n + 1)
check("…same colour and size, no fill", e.stroke[:3] == tuple(dict(S.COLORS)["Purple"]) and e.size == 5 and e.fill is None)
check("…close to where it was drawn", abs(e.x + e.w / 2 - 500) < 8 and abs(e.y + e.h / 2 - 300) < 8)
pop = cv._tidy_popover
labels = [c.get_label() for c in pop.get_child().get_children()] if pop else []
check("offer shown: 'Tidied into an ellipse' + Keep My Drawing", labels == ["Tidied into an ellipse", "Keep My Drawing"])
gw = win.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "tidy_offer.png"), "png", [], [])
undo_len = len(cv._undo)
pop.get_child().get_children()[1].clicked(); settle(0.3)
check("Keep My Drawing: the hand-drawn version is back", isinstance(cv.shapes[-1], S.FreehandShape) and len(cv.shapes) == n + 1)
check("…without adding another Undo step", len(cv._undo) == undo_len and cv._tidy_popover is None)
key(win, Gdk.KEY_z, CTRL)
check("one Undo removes the drawing completely", len(cv.shapes) == n)

stroke(cv, wobbly(seg(60, 380, 300, 340, 70), seed=3)); settle(0.1)
check("a rough straight line becomes a clean line", type(cv.shapes[-1]) is S.LineShape)
shaft = seg(80, 250, 330, 170, 70); ang = math.atan2(-80, 250) + math.pi - math.radians(30)
hook = seg(330, 170, 330 + 28 * math.cos(ang), 170 + 28 * math.sin(ang), 10)[1:]
stroke(cv, wobbly(shaft + hook, amp=1.5, seed=4)); settle(0.1)
a = cv.shapes[-1]
check("a line with a hook becomes an arrow, pointing the right way", isinstance(a, S.ArrowShape) and a.x2 > a.x1 and abs(a.x2 - 330) < 10)
box = seg(150, 120, 350, 120, 30)[:-1] + seg(350, 120, 350, 220, 20)[:-1] + seg(350, 220, 150, 220, 30)[:-1] + seg(150, 220, 150, 120, 20) + seg(150, 120, 170, 120, 3)[1:]
stroke(cv, wobbly(box, seed=5)); settle(0.1)
r = cv.shapes[-1]
check("a rough box becomes a clean rectangle", isinstance(r, S.RectShape) and not isinstance(r, S.EllipseShape) and abs(r.w - 200) < 12 and abs(r.h - 100) < 12)
cv.on_button_press(cv, Ev(*cv.to_widget(10, 10))); cv.on_button_release(cv, Ev(*cv.to_widget(10, 10)))
check("the offer goes away on the next click", cv._tidy_popover is None)

win.tidy_item.set_active(False)
n = len(cv.shapes)
stroke(cv, circle)
check("tidy-up off (menu): a circle stays a drawing", isinstance(cv.shapes[-1], S.FreehandShape) and cv._tidy_popover is None)
check("…and that's remembered", C.load_config()["tidy_shapes"] is False)
win.tidy_item.set_active(True)

# ---- Line/fill selector ----
win.tool_buttons["rectangle"].set_active(True)
win.set_color_target("line"); win.color_buttons["Red"].set_active(True)
win.set_color_target("fill"); win.color_buttons["Blue"].set_active(True); win.opacity_buttons["see-through"].set_active(True)
win.set_color_target("line")
settle(0.2)
wl = win.well
def well_pixels():
    w, h = wl.get_allocated_width(), wl.get_allocated_height()
    gw = wl.get_window(); x, y = wl.translate_coordinates(wl.get_toplevel(), 0, 0)
    return Gdk.pixbuf_get_from_window(win.get_window(), x, y, w, h)
pb = well_pixels()
lx, ly, lw, lh = wl._rect("line", True); fx, fy, fw, fh = wl._rect("fill", False)
ox = int((lx + lw + fx) / 2); oy = int((ly + lh + fy) / 2)    # where they overlap
check("line square in front, solid red (no white centre)", close := pix(pb, lx + lw / 2, ly + lh / 2)[0] > 200 and pix(pb, lx + lw / 2, ly + lh / 2)[1] < 60)
check("…and it's in front where the squares overlap", pix(pb, ox, oy)[0] > 200 and pix(pb, ox, oy)[2] < 80)
check("chosen square is bigger", wl._rect("line", True)[2] > wl._rect("fill", False)[2])
fp = [pix(pb, fx + fw - 4, fy + fh - 4), pix(pb, fx + fw - 6, fy + fh - 4)]
check("see-through fill: bottom-right half shows the checkerboard", fp[0] != fp[1])
tl = pix(pb, fx + fw * 0.62, fy + fh * 0.62 - 6) if False else pix(pb, int(fx + fw - 3), int(fy + fh * 0.55))
win.set_color_target("fill"); settle(0.2); pb = well_pixels()
check("choose fill: now the fill square is bigger, line still in front",
      wl._rect("fill", True)[2] > wl._rect("line", False)[2] and pix(pb, *(int(v) for v in (wl._rect("line", False)[0] + 8, wl._rect("line", False)[1] + 8)))[0] > 200)
win.color_buttons["None"].set_active(True); settle(0.2); pb = well_pixels()
fx, fy, fw, fh = wl._rect("fill", True)
cells = {pix(pb, int(fx + fw - 2 - dx), int(fy + fh - 2)) for dx in range(0, 9)}
check("None shows as a grey checkerboard", len(cells) >= 2 and all(abs(c[0] - c[1]) < 6 and abs(c[1] - c[2]) < 6 for c in cells))
win.tool_buttons["arrow"].set_active(True); settle(0.2); pb2 = well_pixels()
check("arrow tool (no fill): the fill square isn't faded or changed", pix(pb2, int(fx + fw - 4), int(fy + fh - 4)) == pix(pb, int(fx + fw - 4), int(fy + fh - 4)))
win.set_color_target("line")
check("'Sheer' instead of 'See-through'", win.opacity_buttons["see-through"].get_child().get_label() == "Sheer"
      and "Semi-transparent" in win.opacity_buttons["see-through"].get_tooltip_text())

# ---- Font button: "Aa", fixed width ----
win.tool_buttons["text"].set_active(True); settle(0.2)
check("font button shows 'Aa' (and it is visible)", win.font_sample.get_text() == "Aa" and win.font_sample.get_mapped() and "Sans Bold" in win.font_button.get_tooltip_text())
sw1 = win.sidebar.get_allocated_width()
for font in ("Serif Italic", "Monospace Bold", "DejaVu Sans Condensed Bold Oblique"):
    win.set_font(font); settle(0.15)
check("sidebar width doesn't change with the font", win.sidebar.get_allocated_width() == sw1)
print(f"   sidebar width: {sw1}px (was ~120)")
check("sidebar is narrower than before", sw1 < 110)
check("font chosen without a size", cv.font == "DejaVu Sans Bold Oblique Condensed")

gw = win.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "round_window.png"), "png", [], [])
win.modified = False; win.destroy()
print("FAILURES:", fails or "none")
