import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from xlshared.ui import add_icon_search_path
from xlannotate import shapes as S
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
    def __init__(self, x=0, y=0, button=1, type=Gdk.EventType.BUTTON_PRESS, state=0, keyval=0):
        self.x, self.y, self.button, self.type, self.state, self.keyval = x, y, button, type, state, keyval
def pix(pb, x, y):
    o = y * pb.get_rowstride() + x * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o+3])
def wdrag(cv, wx1, wy1, wx2, wy2):
    cv.on_button_press(cv, Ev(wx1, wy1)); cv.on_motion(cv, Ev((wx1+wx2)/2, (wy1+wy2)/2))
    cv.on_motion(cv, Ev(wx2, wy2)); cv.on_button_release(cv, Ev(wx2, wy2))
def drag(cv, ix1, iy1, ix2, iy2):
    wdrag(cv, *cv.to_widget(ix1, iy1), *cv.to_widget(ix2, iy2))
def click(cv, ix, iy):
    x, y = cv.to_widget(ix, iy); cv.on_button_press(cv, Ev(x, y)); cv.on_button_release(cv, Ev(x, y))
def key(win, keyval, state=0):
    return win.on_key_press(win, Ev(keyval=keyval, state=state))
def sample_image(w=600, h=400):
    """White page with black text, and a noisy colourful strip to pixelate."""
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h); cr = cairo.Context(surf)
    cr.set_source_rgb(1, 1, 1); cr.paint()
    cr.set_source_rgb(0, 0, 0); cr.select_font_face("Sans", 0, 1); cr.set_font_size(26)
    cr.move_to(30, 60); cr.show_text("Password: hunter2")
    cr.move_to(30, 130); cr.show_text("Click Save, then Close")
    for i in range(0, 300, 3):
        cr.set_source_rgb((i * 7 % 255) / 255, (i * 13 % 255) / 255, (i * 29 % 255) / 255)
        cr.rectangle(30 + i, 200, 3, 60); cr.fill()
    surf.flush(); return Gdk.pixbuf_get_from_surface(surf, 0, 0, w, h)
def tool(win, name): win.tool_buttons[name].set_active(True)

def rgba(name, alpha=1.0): return tuple(dict(S.COLORS)[name]) + (alpha,)
def color(win, name, target="line"):
    win.set_color_target(target); win.color_buttons[name].set_active(True)
def set_size(win, v): win.size_scale.set_value(v)
def text_view(cv):
    return cv._text_popover.get_child().get_children()[0].get_child()
def type_text(cv, text, keep=True):
    view = text_view(cv); view.get_buffer().set_text(text); cv.finish_text_edit(keep)


win = AnnotateWindow(); win.ask_unsaved = lambda: "discard"
win.show_all(); win.load_pixbuf(sample_image(), name="sample.png"); settle(0.5)
cv = win.canvas
check("image shown 1:1", cv._transform()[0] == 1.0)

# ---- Toolbar layout ----
kids = win.toolbar.get_children()
crop_parent = win.tool_buttons["crop"].get_parent()
check("Crop has its own group, after the drawing tools", crop_parent is not win.tool_buttons["arrow"].get_parent()
      and kids.index(crop_parent) == kids.index(win.tool_buttons["arrow"].get_parent()) + 2)
order = [t for t in ("select", "arrow", "line", "freehand", "rectangle", "ellipse", "highlight", "text", "step", "pixelate", "loupe")]
xs = [win.tool_buttons[t].translate_coordinates(win, 0, 0)[0] for t in order]
check("drawing tools in order", xs == sorted(xs))

# ---- Line ----
tool(win, "line"); color(win, "Blue")
drag(cv, 300, 330, 500, 330)
ln = cv.shapes[-1]
check("line drawn (no arrow head)", type(ln) is S.LineShape)
flat = cv.render_flat()
check("line drawn in blue, ends without a head", pix(flat, 400, 330)[2] > 180 and pix(flat, 497, 322) == (255, 255, 255))

# ---- Highlighter ----
tool(win, "highlight"); color(win, "Yellow")
drag(cv, 25, 100, 330, 145)
hl = cv.shapes[-1]
check("highlight drawn", isinstance(hl, S.HighlightShape))
flat = cv.render_flat()
bg = pix(flat, 27, 104)
check("highlight tints white to yellow", bg[0] > 200 and bg[1] > 180 and bg[2] < 100)
# find a black text pixel under the highlight and check it stayed dark
dark = min((sum(pix(flat, x, y)), (x, y)) for x in range(30, 320) for y in range(108, 140))
check("text under the highlight stays dark", dark[0] < 120)

# ---- Pixelate ----
tool(win, "pixelate"); set_size(win, 6)
drag(cv, 30, 200, 330, 260)
pxl = cv.shapes[-1]
check("pixelate drawn with 14px blocks", isinstance(pxl, S.PixelateShape) and pxl.block == 14)
flat = cv.render_flat()
block = {pix(flat, 31 + dx, 201 + dy) for dx in range(12) for dy in range(12)}
check("pixelated area is flat blocks", len(block) == 1)
orig_variety = {pix(cv.base, 31 + dx, 201) for dx in range(12)}
check("…where the original had detail", len(orig_variety) > 2)
check("outside the box untouched", pix(flat, 400, 230) == pix(cv.base, 400, 230))
# Password: pixelate it too, and check the letters are gone
drag(cv, 25, 30, 260, 75)
flat = cv.render_flat()
row = [pix(flat, x, 50) for x in range(30, 250)]
check("password text blurred into blocks", len(set(row)) < 25)

# ---- Numbered steps ----
tool(win, "step"); color(win, "Red"); set_size(win, 6)
for x in (420, 470, 520):
    click(cv, x, 60)
steps = [s for s in cv.shapes if isinstance(s, S.StepShape)]
check("three steps placed with clicks", len(steps) == 3)
seen = []
orig_draw = S.StepShape.draw
S.StepShape.draw = lambda self, cr, base=None, number=None: seen.append((self.x, number)) or orig_draw(self, cr, base, number)
cv.render_flat()
check("steps numbered 1, 2, 3 in order", seen == [(420, 1), (470, 2), (520, 3)])
tool(win, "select"); click(cv, 420, 60); key(win, Gdk.KEY_Delete)
seen.clear(); cv.render_flat()
check("delete step 1: the others renumber to 1, 2", seen == [(470, 1), (520, 2)])
key(win, Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK)
seen.clear(); cv.render_flat()
check("undo brings step 1 back as number 1", seen == [(420, 1), (470, 2), (520, 3)])
S.StepShape.draw = orig_draw
flat = cv.render_flat()
check("step circle is red with a white number", pix(flat, 470 - 10, 60)[0] > 180 and max(pix(flat, 470 + dx, 60 + dy) for dx in range(-4, 5) for dy in range(-6, 7)) >= (240, 240, 240))
above = [pix(flat, 470 + dx, 60 - 30) for dx in range(-30, 31)]
check("nothing stray drawn around a step (no line joining it to the last mark)", all(p == (255, 255, 255) for p in above))
check("number is black on light colours", S.is_light(rgba("Yellow")) and not S.is_light(rgba("Red")))

# ---- Resize handles ----
tool(win, "rectangle"); color(win, "Green")
drag(cv, 360, 150, 460, 250)
rect = cv.shapes[-1]
tool(win, "select"); click(cv, 360, 200)
check("select a rectangle: 8 handles", cv.selected is rect and len(rect.handles()) == 8)
sx, sy = cv.to_widget(460, 250)
cv.on_motion(cv, Ev(sx, sy))
check("hover a corner handle: resize cursor", cv._cursor_name == "se-resize")
wdrag(cv, sx, sy, sx + 60, sy + 40)
check("drag corner: box grows", (rect.x, rect.y, rect.w, rect.h) == (360, 150, 160, 140))
key(win, Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK)
rect = cv.shapes[-1]
check("undo the resize", (rect.w, rect.h) == (100, 100))
click(cv, 360, 200)
wx, wy = cv.to_widget(360, 150)
wdrag(cv, wx, wy, *cv.to_widget(500, 300))
check("drag past the opposite corner flips cleanly", (rect.x, rect.y, rect.w, rect.h) == (460, 250, 40, 50))
nx, ny = cv.to_widget(rect.x + rect.w / 2, rect.y)
wdrag(cv, nx, ny, nx, ny - 30)
check("side handle changes one edge only", (rect.x, rect.y, rect.w, rect.h) == (460, 220, 40, 80))
mx, my = cv.to_widget(rect.x, rect.y + 40)
cv.on_motion(cv, Ev(mx + 1, my + 1))
check("hover a mark (not a handle): move cursor", cv._cursor_name in ("move", "w-resize"))
cv.on_motion(cv, Ev(*cv.to_widget(250, 380)))
check("hover empty space: normal cursor", cv._cursor_name == "default")

tool(win, "arrow"); color(win, "Red")
drag(cv, 100, 300, 250, 300)
arrow = cv.shapes[-1]
tool(win, "select"); click(cv, 175, 300)
check("select an arrow: 2 end handles", set(arrow.handles()) == {"start", "end"})
ex, ey = cv.to_widget(250, 300)
cv.on_motion(cv, Ev(ex, ey))
check("hover an end: crosshair", cv._cursor_name == "crosshair")
wdrag(cv, ex, ey, *cv.to_widget(250, 360))
check("drag the head end: arrow re-aimed, tail stays", (arrow.x1, arrow.y1, arrow.x2, arrow.y2) == (100, 300, 250, 360))
key(win, Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK)
check("undo re-aim", (cv.shapes[-1].x2, cv.shapes[-1].y2) == (250, 300))
check("text and steps have no handles", S.TextShape(0, 0, "a", size=6).handles() == {} and steps[0].handles() == {})
n_before = len(cv._undo)
click(cv, 175, 300)
check("clicking a handle without moving adds no undo step", len(cv._undo) == n_before)

# Visual: everything, with the rectangle selected
click(cv, 460, 260); settle(0.3)
gw = win.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "tools_all.png"), "png", [], [])

# ---- Crop ----
n_marks = len(cv.shapes)
line_before = (cv.shapes[0].x1, cv.shapes[0].y1)
tool(win, "crop"); settle(0.2)
check("Crop: bar shows, Crop button off until an area is drawn", win.crop_bar.get_visible() and not win.crop_apply_btn.get_sensitive())
check("Crop clears the selection", cv.selected is None)
drag(cv, -50, -50, 520, 340)
check("crop area stays on the image", (cv.crop.x, cv.crop.y) == (0, 0) and win.crop_apply_btn.get_sensitive())
# adjust with a handle and move it
hx, hy = cv.to_widget(0, 0)
wdrag(cv, hx, hy, *cv.to_widget(20, 10))
check("crop handle adjusts the area", (cv.crop.x, cv.crop.y, cv.crop.w, cv.crop.h) == (20, 10, 500, 330))
cx, cy = cv.to_widget(200, 200)
wdrag(cv, cx, cy, cx + 500, cy)
check("moving the area stops at the image edge", (cv.crop.x, cv.crop.y) == (100, 10))
wdrag(cv, *cv.to_widget(300, 200), *cv.to_widget(220, 200))
check("move it back", (cv.crop.x, cv.crop.y) == (20, 10))
settle(0.8)
check("crop bar's Crop and Cancel buttons are actually on screen", win.crop_apply_btn.get_mapped() and win.crop_apply_btn.get_allocated_width() > 20)
gw = win.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "tools_crop.png"), "png", [], [])
key(win, Gdk.KEY_Return); settle(0.8)   # the crop bar slides away
check("Enter crops to 500x330", (cv.base.get_width(), cv.base.get_height()) == (500, 330))
check("marks moved with the crop", (cv.shapes[0].x1, cv.shapes[0].y1) == (line_before[0] - 20, line_before[1] - 10) and len(cv.shapes) == n_marks)
check("after cropping: back to Select, bar hidden", win.tool_buttons["select"].get_active() and not win.crop_bar.get_visible())
check("title shows unsaved", win.get_title().startswith("*"))
key(win, Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK)
check("Undo brings back the whole image and mark positions", (cv.base.get_width(), cv.shapes[0].x1) == (600, line_before[0]))
key(win, Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
check("Redo crops again", cv.base.get_width() == 500)
tool(win, "crop"); drag(cv, 10, 10, 200, 200)
key(win, Gdk.KEY_Escape)
check("Esc clears the crop area, stays in Crop", cv.crop is None and win.tool_buttons["crop"].get_active())
key(win, Gdk.KEY_Escape); settle(0.8)
check("Esc again leaves Crop", win.tool_buttons["select"].get_active() and not win.crop_bar.get_visible())
tool(win, "crop"); drag(cv, 10, 10, 12, 12)
check("a tiny crop area is ignored", cv.crop is None)
win.leave_crop()
check("Crop is never remembered as the starting tool", win.config["tool"] != "crop")

# Save: everything drawn in at the cropped size
out = os.path.join(os.environ["HOME"], "out.png")
check("save cropped + annotated", win._write(out, "png"))
saved = GdkPixbuf.Pixbuf.new_from_file(out)
check("saved file is the cropped size", (saved.get_width(), saved.get_height()) == (500, 330))
win.modified = False; win.destroy()

# ---- Crop from xl-Screenshot ----
sw = ScreenshotWindow(); sw.present(); settle(0.3)
sw.update_screenshot_buffer(sample_image(800, 500)); settle(0.3)
sw.open_annotate(); settle(0.4); aw = sw.annotate_window
tool(aw, "step"); click(aw.canvas, 300, 300)
tool(aw, "crop"); drag(aw.canvas, 200, 200, 600, 450); aw.apply_crop()
aw.done(); settle(0.4)
check("screenshot gets the cropped image", (sw.active_pixbuf.get_width(), sw.base_pixbuf.get_width()) == (400, 400))
check("…and the step, moved with the crop, still editable", len(sw.shapes) == 1 and (sw.shapes[0].x, sw.shapes[0].y) == (100, 100))
sw.open_annotate(); settle(0.3); aw = sw.annotate_window
check("reopen: cropped image and step", aw.canvas.base.get_width() == 400 and len(aw.canvas.shapes) == 1)
key(aw, Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK)
check("(undo history starts fresh when reopened)", aw.canvas.base.get_width() == 400)
aw.modified = False; aw.destroy(); settle(0.2)
print("FAILURES:", fails or "none")
