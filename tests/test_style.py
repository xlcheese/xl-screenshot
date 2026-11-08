import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time, math
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from xlshared.ui import add_icon_search_path
from xlannotate import shapes as S, config as C
from xlannotate.window import AnnotateWindow
from xlscreenshot.window import ScreenshotWindow
from gi.repository import Gtk, Gdk, GdkPixbuf
import cairo
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
    def __init__(self, x=0, y=0, button=1, type=Gdk.EventType.BUTTON_PRESS, state=0, keyval=0, direction=None):
        self.x, self.y, self.button, self.type, self.state, self.keyval = x, y, button, type, state, keyval
        self.direction = direction
SHIFT = Gdk.ModifierType.SHIFT_MASK; CTRL = Gdk.ModifierType.CONTROL_MASK
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o+3])
def wdrag(cv, wx1, wy1, wx2, wy2, state=0):
    cv.on_button_press(cv, Ev(wx1, wy1, state=state)); cv.on_motion(cv, Ev((wx1+wx2)/2, (wy1+wy2)/2, state=state))
    cv.on_motion(cv, Ev(wx2, wy2, state=state)); cv.on_button_release(cv, Ev(wx2, wy2, state=state))
def drag(cv, ix1, iy1, ix2, iy2, state=0):
    wdrag(cv, *cv.to_widget(ix1, iy1), *cv.to_widget(ix2, iy2), state=state)
def click(cv, ix, iy, state=0):
    x, y = cv.to_widget(ix, iy); cv.on_button_press(cv, Ev(x, y, state=state)); cv.on_button_release(cv, Ev(x, y, state=state))
def key(win, keyval, state=0): return win.on_key_press(win, Ev(keyval=keyval, state=state))
def rgba(name, a=1.0): return tuple(dict(S.COLORS)[name]) + (a,)
def tool(win, t): win.tool_buttons[t].set_active(True)
def color(win, name, target="line"): win.set_color_target(target); win.color_buttons[name].set_active(True)
def white(w, h):
    p = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h); p.fill(0xffffffff); return p
def close(a, b, tol=12): return all(abs(x - y) <= tol for x, y in zip(a, b))

win = AnnotateWindow(); win.ask_unsaved = lambda: "discard"
win.show_all(); win.load_pixbuf(white(600, 400), name="w.png"); settle(0.5)
cv = win.canvas

# ---- Sidebar colours ----
names = [n for n in win.color_buttons]
check("sidebar: None + 9 colours incl. Pink and Purple", names == ["None", "Red", "Orange", "Yellow", "Green", "Blue", "Purple", "Pink", "Black", "White"])
check("starts setting the line colour", win.color_target == "line")
tool(win, "rectangle"); color(win, "Blue"); color(win, "Yellow", "fill")
win.opacity_buttons["see-through"].set_active(True)
check("fill colour set see-through", cv.fill == rgba("Yellow", S.SEE_THROUGH_ALPHA) and cv.stroke == rgba("Blue"))
drag(cv, 50, 50, 250, 150)
r = cv.shapes[-1]
check("rectangle gets blue line + see-through yellow fill", r.stroke == rgba("Blue") and r.fill == rgba("Yellow", 0.4))
flat = cv.render_flat()
inside = pix(flat, 150, 100)
check("see-through fill blends with the image", inside[2] > 120 and inside[2] < 220 and inside[0] > 200)
check("border is solid blue", close(pix(flat, 50, 100), (54, 133, 227), 30))
win.set_color_target("fill")
check("well click switches what the swatches set; sidebar shows fill's colour", win.color_buttons["Yellow"].get_active() and win.opacity_buttons["see-through"].get_active())
win.set_color_target("line")
check("…and back to the line's colour (solid)", win.color_buttons["Blue"].get_active() and win.opacity_buttons["solid"].get_active())
color(win, "None", "fill")
check("None: no fill", cv.fill is None and not win.opacity_buttons["solid"].get_sensitive())
win.set_color_target("line")
win.swap_colors()
check("swap: line becomes None, fill becomes blue", cv.stroke is None and cv.fill == rgba("Blue"))
win.swap_colors()

# Select + recolour
tool(win, "select"); click(cv, 50, 100)
check("select the rectangle: sidebar shows its line colour", cv.selected is r and win.color_buttons["Blue"].get_active())
color(win, "Pink")
check("pick Pink: the rectangle's line turns pink", r.stroke == rgba("Pink"))
color(win, "None", "fill")
check("pick None for its fill: fill removed", r.fill is None)
key(win, Gdk.KEY_z, CTRL)
r = cv.shapes[-1]
check("undo brings the fill back", r.fill == rgba("Yellow", 0.4))
cv.select(None); click(cv, 150, 100)
check("filled shape can be picked by clicking inside", cv.selected is r)
# custom colour: no swatch looks chosen
r.stroke = (0.3, 0.3, 0.3, 1.0); win.set_color_target("line")
check("colour not in the palette: no swatch looks chosen", not any(b.get_active() for b in win.color_buttons.values()))
cv.select(None)

# ---- Line style, shadow ----
tool(win, "line"); color(win, "Black"); win.dash_buttons["dashed"].set_active(True)
drag(cv, 300, 300, 580, 300)
ln = cv.shapes[-1]
check("dashed line", ln.dash == "dashed")
flat = cv.render_flat()
row = [pix(flat, x, 300)[0] < 100 for x in range(310, 570)]
gaps = sum(1 for i in range(1, len(row)) if row[i] != row[i - 1])
check("…it really is dashed (several gaps)", gaps >= 10)
win.dash_buttons["solid"].set_active(True)
tool(win, "text")
check("text tool: line style off, shadow on, font shown", not win.dash_buttons["dashed"].get_sensitive()
      and win.shadow_btn.get_sensitive() and win.font_box.get_visible())
tool(win, "pixelate")
check("pixelate: no line style or shadow, size on", not win.shadow_btn.get_sensitive() and win.size_scale.get_sensitive())
tool(win, "highlight")
check("highlighter: size slider off", not win.size_scale.get_sensitive())
tool(win, "arrow"); win.shadow_btn.set_active(True); color(win, "Red")
drag(cv, 300, 200, 450, 200)
check("arrow with shadow", cv.shapes[-1].shadow)
flat = cv.render_flat()
check("shadow drawn below the arrow (grey)", pix(flat, 380, 206)[0] < 235 and abs(pix(flat, 380, 206)[0] - pix(flat, 380, 206)[2]) < 25)
win.shadow_btn.set_active(False)

# ---- Size slider, per tool ----
tool(win, "arrow"); win.size_scale.set_value(3)
tool(win, "text"); win.size_scale.set_value(14)
tool(win, "pixelate"); win.size_scale.set_value(2)
tool(win, "arrow")
check("size remembered per tool (lines 3)", win.size_scale.get_value() == 3)
tool(win, "text")
check("…text 14", win.size_scale.get_value() == 14 and "Text size" in win.size_scale.get_tooltip_text())
tool(win, "pixelate")
check("…pixelate 2 = 6px blocks (finer than before)", win.size_scale.get_value() == 2 and S.pixel_block(2) == 6 and S.pixel_block(1) == 4)
tool(win, "select"); click(cv, 375, 200)
arrow = cv.selected
check("select the arrow: slider shows its size", arrow is not None and win.size_scale.get_value() == arrow.size)
n = len(cv._undo)
for v in (7, 8, 9, 10, 11):
    win.size_scale.set_value(v)
check("dragging the slider resizes the mark", arrow.size == 11)
check("…as one undo step, not five", len(cv._undo) == n + 1)
key(win, Gdk.KEY_z, CTRL)
check("one undo puts the size back", cv.shapes[cv.shapes.index(next(s for s in cv.shapes if isinstance(s, S.ArrowShape)))].size == 6)
cv.select(None)

# ---- Ellipse ----
tool(win, "ellipse"); color(win, "Green"); color(win, "None", "fill"); win.size_scale.set_value(4)
drag(cv, 400, 40, 560, 140)
e = cv.shapes[-1]
check("ellipse drawn", isinstance(e, S.EllipseShape) and (e.x, e.y, e.w, e.h) == (400, 40, 160, 100))
check("ellipse: edge hits, centre and corner miss", e.contains(400, 90, 3) and not e.contains(480, 90, 3) and not e.contains(402, 42, 3))
flat = cv.render_flat()
check("ellipse drawn green at its left edge, not in the box corner", pix(flat, 401, 90)[1] > 150 and pix(flat, 401, 90)[0] < 120 and pix(flat, 404, 44) == (255, 255, 255))

# ---- Shift constraints ----
tool(win, "rectangle"); color(win, "Blue")
drag(cv, 20, 200, 120, 260, state=SHIFT)
sq = cv.shapes[-1]
check("Shift: rectangle becomes a square", sq.w == sq.h == 100)
tool(win, "arrow")
drag(cv, 20, 380, 120, 370, state=SHIFT)
a2 = cv.shapes[-1]
check("Shift: arrow snaps to horizontal", abs(a2.y2 - a2.y1) < 0.01)
drag(cv, 200, 380, 260, 330, state=SHIFT)
a3 = cv.shapes[-1]
check("Shift: arrow snaps to 45°", abs(abs(a3.x2 - a3.x1) - abs(a3.y2 - a3.y1)) < 0.01)
tool(win, "select"); click(cv, 20, 230)
before = (sq.x, sq.y)
drag(cv, 20, 230, 70, 236, state=SHIFT)
check("Shift: moving goes straight across", (sq.x, sq.y) == (before[0] + 50, before[1]))
cx, cy = cv.to_widget(sq.x + sq.w, sq.y + sq.h)
wdrag(cv, cx, cy, cx + 30, cy + 70, state=SHIFT)
check("Shift: corner handle keeps it square", abs(sq.w - sq.h) < 0.01)
cv.select(None)

# ---- Loupe ----
pat = white(600, 400)
surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 600, 400); c = cairo.Context(surf); c.set_source_rgb(1, 1, 1); c.paint()
c.set_source_rgb(0, 0, 0); c.rectangle(298, 0, 4, 400); c.fill()        # a 4px black stripe at x=298..302
surf.flush(); pat = Gdk.pixbuf_get_from_surface(surf, 0, 0, 600, 400)
w5 = AnnotateWindow(); w5.ask_unsaved = lambda: "discard"; w5.show_all(); w5.load_pixbuf(pat, name="p.png"); settle(0.4)
c5 = w5.canvas
tool(w5, "loupe"); w5.size_scale.set_value(10)
click(c5, 300, 200)
lp = c5.shapes[-1]
check("loupe placed with a click, zoom 2, radius from the slider", isinstance(lp, S.LoupeShape) and lp.zoom == 2.0 and lp.radius == S.loupe_radius(10))
flat = c5.render_flat()
dark = [x for x in range(240, 361) if pix(flat, x, 200)[0] < 80]
check("loupe magnifies: the 4px stripe is ~8px wide inside it", 7 <= len(dark) <= 10)
check("outside the loupe the stripe is still 4px", len([x for x in range(280, 321) if pix(flat, x, 20)[0] < 80]) == 4)
tool(w5, "select"); click(c5, 300, 200)
check("loupe has a size handle and a green zoom handle", set(lp.handles()) == {"size", "zoom"} and lp.special_handles() == {"zoom"})
zx, zy = c5.to_widget(*lp.handles()["zoom"])
tx, ty = c5.to_widget(lp.cx + lp.radius, lp.cy)       # quarter way round clockwise
wdrag(c5, zx, zy, tx, ty)
check("drag the green handle a quarter turn: zoom 2 → 3", abs(lp.zoom - 3.0) < 0.15)
key(w5, Gdk.KEY_z, CTRL)
check("…undoable", c5.shapes[-1].zoom == 2.0)
lp = c5.shapes[-1]; click(c5, 300, 200)
sx, sy = c5.to_widget(*lp.handles()["size"])
wdrag(c5, sx, sy, sx + 40, sy + 40)
check("drag the size handle: lens grows", lp.radius > S.loupe_radius(10))

# ---- View zoom ----
check("fits by default (100% for a small image)", c5.zoom is None and abs(c5.view_scale() - 1.0) < 1e-9 and w5.zoom_label_btn.get_label() == "100%")
key(w5, Gdk.KEY_plus, CTRL); settle(0.3)
check("Ctrl++ zooms in to 125%", abs(c5.view_scale() - 1.25) < 1e-9 and w5.zoom_label_btn.get_label() == "125%")
key(w5, Gdk.KEY_plus, CTRL); key(w5, Gdk.KEY_plus, CTRL); key(w5, Gdk.KEY_plus, CTRL); settle(0.4)
check("zoomed in: the image is bigger than the view, so it scrolls", c5.get_allocated_width() > w5.scroller.get_allocated_width())
ix, iy = c5.to_image(*c5.to_widget(300, 200))
check("coordinates still map correctly when zoomed", abs(ix - 300) < 1e-6 and abs(iy - 200) < 1e-6)
# drawing while zoomed lands in the right place
tool(w5, "step"); click(c5, 100, 100)
check("drawing while zoomed lands on the right spot", (c5.shapes[-1].x, c5.shapes[-1].y) == (100, 100))
key(w5, Gdk.KEY_0, CTRL); settle(0.3)
check("Ctrl+0 fits again", c5.zoom is None)
# Ctrl+scroll around the pointer
c5.zoom_to(2.0); settle(0.4)                    # zoomed in enough that the view can scroll
def in_view(ix, iy):
    wx, wy = c5.to_widget(ix, iy)
    return (wx - w5.scroller.get_hadjustment().get_value(), wy - w5.scroller.get_vadjustment().get_value())
before = in_view(500, 300)
c5.on_scroll(c5, Ev(*c5.to_widget(500, 300), state=CTRL, direction=Gdk.ScrollDirection.UP)); settle(0.4)
after = in_view(500, 300)
check("Ctrl+scroll zooms in", abs(c5.view_scale() - 2.5) < 1e-9)
check("…keeping the point under the pointer in place", abs(before[0] - after[0]) <= 2 and abs(before[1] - after[1]) <= 2)
print("   (point under the pointer: before", tuple(round(v) for v in before), "after", tuple(round(v) for v in after), ")")
check("plain scroll doesn't zoom", c5.on_scroll(c5, Ev(10, 10, state=0, direction=Gdk.ScrollDirection.UP)) is False)
key(w5, Gdk.KEY_1, CTRL); settle(0.2)
check("Ctrl+1: actual size", c5.zoom == 1.0)
big = white(3000, 2000)
w5.load_pixbuf(big, name="big.png"); settle(0.4)
settle(0.4)
check("big image fits (shrunk), label shows its %", c5.view_scale() < 0.5 and w5.zoom_label_btn.get_label() == f"{round(c5.view_scale() * 100)}%")
w5.modified = False; w5.destroy()

# ---- Text: multi-line, font, background ----
tool(win, "text"); color(win, "White"); color(win, "Black", "fill"); win.opacity_buttons["see-through"].set_active(True)
win.size_scale.set_value(6)
x, y = cv.to_widget(60, 20)
cv.on_button_press(cv, Ev(x, y)); settle()
view = cv._text_popover.get_child().get_children()[0].get_child()
buf = view.get_buffer(); buf.set_text("First line")
end = buf.get_end_iter(); buf.place_cursor(end)
ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS); ev.keyval = Gdk.KEY_Return; ev.state = SHIFT; ev.window = view.get_window(Gtk.TextWindowType.TEXT)
handled = view.emit("key-press-event", ev)
check("Shift+Enter doesn't finish the text", cv._finish_text is not None)
buf.set_text("First line\nSecond line")
ev2 = Gdk.Event.new(Gdk.EventType.KEY_PRESS); ev2.keyval = Gdk.KEY_Return; ev2.state = 0; ev2.window = view.get_window(Gtk.TextWindowType.TEXT)
view.emit("key-press-event", ev2); settle()
t = cv.shapes[-1]
check("Enter finishes: two-line text added", isinstance(t, S.TextShape) and t.text == "First line\nSecond line")
check("text: white letters on a see-through black box", t.stroke == rgba("White") and t.fill == rgba("Black", 0.4))
bx, by, bw, bh = t.bounds()
flat = cv.render_flat()
check("background box drawn behind the text", pix(flat, bx + 3, by + bh / 2)[0] < 200)
check("two lines are taller than one", bh > S.text_size(6) * 2)
win.set_font("Serif Italic 12")
check("font chosen (size left to the slider)", cv.font == "Serif Italic")
x, y = cv.to_widget(300, 360); cv.on_button_press(cv, Ev(x, y)); settle()
view = cv._text_popover.get_child().get_children()[0].get_child(); view.get_buffer().set_text("Serif")
ev3 = Gdk.Event.new(Gdk.EventType.KEY_PRESS); ev3.keyval = Gdk.KEY_Escape; ev3.window = view.get_window(Gtk.TextWindowType.TEXT)
n = len(cv.shapes); view.emit("key-press-event", ev3); settle()
check("Esc cancels the text", len(cv.shapes) == n)
x, y = cv.to_widget(300, 360); cv.on_button_press(cv, Ev(x, y)); settle()
cv._text_popover.get_child().get_children()[0].get_child().get_buffer().set_text("Kept")
cv._text_popover.popdown(); settle(0.4)
check("clicking away keeps the text", cv.shapes[-1].text == "Kept" and cv.shapes[-1].font == "Serif Italic")

# ---- Settings remembered ----
cfg = C.load_config()
check("style remembered in settings", cfg["font"] == "Serif Italic" and cfg["sizes"]["text"] == 6 and cfg["stroke"][:3] == list(rgba("White")[:3]))
w6 = AnnotateWindow(); w6.show_all(); settle(0.2)
check("…and restored in a new window", w6.canvas.font == "Serif Italic" and w6.canvas.sizes["pixelate"] == 2)
w6.destroy()

# ---- Layout ----
gw = win.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "style_window.png"), "png", [], [])
win.modified = False; win.destroy()

# ---- Embedded: Copy stays in the toolbar, no Open/Save ----
sw = ScreenshotWindow(); sw.present(); settle(0.3)
sw.update_screenshot_buffer(white(300, 200)); settle(0.3)
sw.open_annotate(); settle(0.4); aw = sw.annotate_window
check("from xl-Screenshot: Copy in the toolbar, no Open/Save", aw.file_group.get_children() == [aw.copy_btn] and not hasattr(aw, "save_btn"))
tool(aw, "ellipse"); drag(aw.canvas, 20, 20, 120, 90)
aw.done(); settle(0.3)
check("ellipse comes back to xl-Screenshot as an editable mark", isinstance(sw.shapes[0], S.EllipseShape))

# ---- xl-Screenshot: closing to the tray clears the capture ----
class FakeApp: tray = object()
sw.get_application = lambda: FakeApp()
sw.close(); settle(0.3)
check("tray close: window hidden", not sw.get_visible())
check("tray close: capture forgotten", sw.active_pixbuf is None and sw.base_pixbuf is None and sw.shapes == [])
check("tray close: Save/Copy off, Annotate and thumbnail hidden", not sw.save_btn.get_sensitive() and not sw.copy_btn.get_sensitive()
      and not sw.annotate_btn.get_visible() and not sw.preview_area.get_visible())
sw.present(); settle(0.4)
check("reopened: fresh, small window", sw.get_allocated_height() < 300)
print("FAILURES:", fails or "none")
