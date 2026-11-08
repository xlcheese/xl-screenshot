import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from xlshared.ui import add_icon_search_path
from xlannotate import shapes as S
from xlannotate.window import AnnotateWindow
from xlscreenshot.window import ScreenshotWindow
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
def pix(pb, x, y):
    o = y * pb.get_rowstride() + x * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o+3])
def white(w, h, alpha=False):
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, alpha, 8, w, h); pb.fill(0xffffffff); return pb
def drag(canvas, ix1, iy1, ix2, iy2):
    x1, y1 = canvas.to_widget(ix1, iy1); x2, y2 = canvas.to_widget(ix2, iy2)
    canvas.on_button_press(canvas, Ev(x1, y1))
    canvas.on_motion(canvas, Ev((x1+x2)/2, (y1+y2)/2)); canvas.on_motion(canvas, Ev(x2, y2))
    canvas.on_button_release(canvas, Ev(x2, y2))
def click(canvas, ix, iy, double=False):
    x, y = canvas.to_widget(ix, iy)
    canvas.on_button_press(canvas, Ev(x, y))
    if double:
        canvas.on_button_press(canvas, Ev(x, y, type=Gdk.EventType._2BUTTON_PRESS))
    canvas.on_button_release(canvas, Ev(x, y))
RED = (0.88, 0.11, 0.14, 1.0)

def rgba(name, alpha=1.0): return tuple(dict(S.COLORS)[name]) + (alpha,)
def color(win, name, target="line"):
    win.set_color_target(target); win.color_buttons[name].set_active(True)
def set_size(win, v): win.size_scale.set_value(v)
def text_view(cv):
    return cv._text_popover.get_child().get_children()[0].get_child()
def type_text(cv, text, keep=True):
    view = text_view(cv); view.get_buffer().set_text(text); cv.finish_text_edit(keep)

# ---- Marks on their own ----
a = S.ArrowShape(10, 10, 110, 10, stroke=RED, size=6)
check("arrow: click on the line hits", a.contains(60, 12, 3))
check("arrow: click away misses", not a.contains(60, 40, 3))
r = S.RectShape(0, 0, 0, 0, stroke=RED, size=6); r.set_corners(100, 50, 20, 10)
check("rect: corners normalised", (r.x, r.y, r.w, r.h) == (20, 10, 80, 40))
check("rect: outline hits, middle doesn't", r.contains(20, 30, 3) and not r.contains(60, 30, 3))
t = S.TextShape(5, 5, "Hello", stroke=RED, size=6)
bx, by, bw, bh = t.bounds()
check("text: has a size", bw > 30 and bh > 15)
check("text: size slider picks text size", S.TextShape(0, 0, "x", stroke=RED, size=10).text_size > t.text_size > S.TextShape(0, 0, "x", stroke=RED, size=3).text_size)
t.move_by(10, 20); check("text: moves", (t.x, t.y) == (15, 25))

# ---- Standalone window ----
img_path = os.path.join(os.environ["HOME"], "photo.png")
white(400, 300).savev(img_path, "png", [], [])
win = AnnotateWindow()
win.ask_unsaved = lambda: "cancel"
win.show_all(); settle()
tools_off = not win.tool_buttons["arrow"].get_parent().get_sensitive() and not win.sidebar.get_sensitive()
open_btn = win.file_group.get_children()[0]
check("empty: hint shown, tools off, but Open works", win.empty_label.get_visible() and tools_off
      and open_btn.get_sensitive() and open_btn.is_sensitive() and not win.save_btn.get_sensitive())
check("empty: title is app name", win.get_title() == "xl-Annotate")
check("open file", win.open_file(img_path)); settle(0.5)
cv = win.canvas
check("opened: hint hidden, toolbar on", not win.empty_label.get_visible() and win.toolbar.get_sensitive())
check("opened: title is file name", win.get_title() == "photo.png")
check("400x300 image shown 1:1", cv._transform()[0] == 1.0)

win.tool_buttons["arrow"].set_active(True); color(win, "Red"); set_size(win, 6)
drag(cv, 50, 150, 250, 150); settle()
check("arrow drawn", len(cv.shapes) == 1 and isinstance(cv.shapes[0], S.ArrowShape))
check("modified: title gets *", win.modified and win.get_title().startswith("*"))
check("undo button on", win.undo_btn.get_sensitive() and not win.redo_btn.get_sensitive())
drag(cv, 300, 50, 302, 51)
check("tiny drag doesn't add a mark", len(cv.shapes) == 1)

win.tool_buttons["rectangle"].set_active(True); color(win, "Blue")
drag(cv, 280, 40, 380, 120)
check("rectangle drawn in blue", len(cv.shapes) == 2 and cv.shapes[1].stroke == rgba("Blue"))

win.on_key_press(win, Ev(state=Gdk.ModifierType.CONTROL_MASK, keyval=Gdk.KEY_z))
check("Ctrl+Z undoes the rectangle", len(cv.shapes) == 1)
win.on_key_press(win, Ev(state=Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, keyval=Gdk.KEY_Z))
check("Shift+Ctrl+Z redoes it", len(cv.shapes) == 2)

# Text tool
win.tool_buttons["text"].set_active(True); color(win, "Black")
x, y = cv.to_widget(40, 40)
cv.on_button_press(cv, Ev(x, y)); settle()
view = text_view(cv)
check("text: typing box appears", isinstance(view, Gtk.TextView) and view.has_focus())
type_text(cv, "Look here"); settle()
check("text: added", len(cv.shapes) == 3 and cv.shapes[2].text == "Look here")
k = win.on_key_press(win, Ev(keyval=Gdk.KEY_Delete))
check("Delete with nothing selected does nothing", len(cv.shapes) == 3)

# Select tool: pick, restyle, move, delete, edit text
win.tool_buttons["select"].set_active(True)
click(cv, 150, 151)
check("select: click picks the arrow", cv.selected is cv.shapes[0])
check("select: sidebar shows arrow's colour", win.color_buttons["Red"].get_active())
color(win, "Green")
check("select: new colour applies to the arrow", cv.shapes[0].stroke == rgba("Green"))
set_size(win, 10)
check("select: new thickness applies", cv.shapes[0].size == 10)
before = (cv.shapes[0].x1, cv.shapes[0].y1)
drag(cv, 150, 150, 170, 180)
check("select: drag moves the arrow", (cv.shapes[0].x1, cv.shapes[0].y1) == (before[0] + 20, before[1] + 30))
win.on_key_press(win, Ev(state=Gdk.ModifierType.CONTROL_MASK, keyval=Gdk.KEY_z))
check("select: move is undoable", (cv.shapes[0].x1, cv.shapes[0].y1) == before)
click(cv, 160, 30)
check("select: click on empty space deselects", cv.selected is None)
tx = cv.shapes[2]
click(cv, tx.x + 5, tx.y + 5, double=True); settle()
buf = text_view(cv).get_buffer()
check("select: double-click text opens it with its words", buf.get_text(*buf.get_bounds(), False) == "Look here")
type_text(cv, "Edited"); settle()
check("text edited", cv.shapes[2].text == "Edited")
click(cv, 280, 80)
check("select: click on rectangle edge picks it", isinstance(cv.selected, S.RectShape))
win.on_key_press(win, Ev(keyval=Gdk.KEY_Delete))
check("Delete removes the selected mark", len(cv.shapes) == 2 and cv.selected is None)
win.on_key_press(win, Ev(keyval=Gdk.KEY_Escape))

# Save over the file: marks drawn in, still editable
check("save", win.save()); settle()
check("saved: no * in title", not win.modified and not win.get_title().startswith("*"))
saved = GdkPixbuf.Pixbuf.new_from_file(img_path)
check("saved file has the arrow drawn in (green)", pix(saved, 100, 150)[1] > 150 and pix(saved, 100, 150)[0] < 100)
check("saved file still 400x300 PNG without alpha", (saved.get_width(), saved.get_height(), saved.get_has_alpha()) == (400, 300, False))
check("marks still editable after save", len(cv.shapes) == 2)
check("original image in memory untouched", pix(cv.base, 100, 150) == (255, 255, 255))

# JPEG source
jpg = os.path.join(os.environ["HOME"], "shot.jpg"); white(200, 100).savev(jpg, "jpeg", ["quality"], ["95"])
w2 = AnnotateWindow(); w2.show_all(); w2.open_file(jpg); settle()
w2.tool_buttons["rectangle"].set_active(True); color(w2, "Red")
drag(w2.canvas, 20, 20, 180, 80); w2.save()
with open(jpg, "rb") as f: head = f.read(3)
j = GdkPixbuf.Pixbuf.new_from_file(jpg)
check("JPEG saved back as JPEG with the red box", head == b"\xff\xd8\xff" and pix(j, 20, 50)[0] > 180 and pix(j, 20, 50)[1] < 90)
# Transparent PNG saved as JPEG goes on white
tp = white(50, 50, alpha=True); tp.fill(0x00000000)
from xlshared.ui import save_pixbuf
save_pixbuf(tp, os.path.join(os.environ["HOME"], "t.jpg"), "jpeg")
check("transparent image saved as JPEG on white", pix(GdkPixbuf.Pixbuf.new_from_file(os.path.join(os.environ["HOME"], "t.jpg")), 25, 25) == (255, 255, 255))

# Save with no file (pasted) goes to Save As
called = []
w2.save_as = lambda: called.append(1) or False
w2.path = None; w2.save()
check("save with no file uses Save As", called == [1])

# Unsaved changes on close
w2.path = jpg
drag(w2.canvas, 10, 10, 60, 60)
w2.ask_unsaved = lambda: "cancel"
check("close + Cancel keeps window open", w2.on_delete_event(w2, None) is True)
w2.ask_unsaved = lambda: "save"
check("close + Save saves and closes", w2.on_delete_event(w2, None) is False and not w2.modified)
w2.destroy()

# Paste
clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
pasted = white(120, 80); pasted.fill(0x3366ccff); clip.set_image(pasted); settle(0.3)
w3 = AnnotateWindow(); w3.show_all(); settle()
check("Ctrl+V pastes an image", w3.on_key_press(w3, Ev(state=Gdk.ModifierType.CONTROL_MASK, keyval=Gdk.KEY_v)) and w3.canvas.has_image())
check("pasted: title", w3.get_title() == "Pasted Image")
w3.destroy()

# Screenshot of the standalone window (select something first)
win.tool_buttons["select"].set_active(True); click(cv, 100, 150); settle(0.3)
gw = win.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "annotate_standalone.png"), "png", [], [])
win.modified = False; win.destroy()

# ---- From xl-Screenshot ----
sw = ScreenshotWindow(); sw.present(); settle(0.4)
check("before a capture: no Annotate button", not sw.annotate_btn.get_visible())
cap = white(640, 400); cap.fill(0xddeeffff)
sw.update_screenshot_buffer(cap); settle(0.4)
check("after a capture: Annotate button shows", sw.annotate_btn.get_visible())
ab, bc = sw.annotate_btn.get_allocation(), sw.btn_cluster.get_allocation()
db = sw.delay_spin.get_parent().get_allocation()
check("Annotate lines up with the buttons' left edge", ab.x == bc.x)
check("Delay lines up with the buttons' right edge", db.x + db.width == bc.x + bc.width)
gw = sw.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "screenshot_with_annotate.png"), "png", [], [])

sw.open_annotate(); settle(0.5)
aw = sw.annotate_window
check("Annotate opens, modal, over the screenshot window", aw is not None and aw.get_modal() and aw.get_transient_for() is sw)
check("embedded: Done instead of file buttons", hasattr(aw, "done_btn") and aw.done_btn.get_visible() and not hasattr(aw, "save_btn"))
check("busy while annotating", sw.is_busy())
aw.tool_buttons["arrow"].set_active(True); color(aw, "Red")
drag(aw.canvas, 100, 200, 400, 200); settle()
gw = aw.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "annotate_embedded.png"), "png", [], [])
aw.done(); settle(0.4)
check("Done closes Annotate", sw.annotate_window is None and not sw.is_busy())
check("thumbnail/Save image has the arrow", pix(sw.active_pixbuf, 250, 200)[0] > 180 and pix(sw.active_pixbuf, 250, 200)[2] < 100)
check("plain capture kept separately", pix(sw.base_pixbuf, 250, 200) == (0xdd, 0xee, 0xff))
check("one editable mark kept", len(sw.shapes) == 1)

sw.open_annotate(); settle(0.4); aw = sw.annotate_window
check("reopen: the arrow is still an editable mark", len(aw.canvas.shapes) == 1 and not aw.modified)
aw.tool_buttons["select"].set_active(True); click(aw.canvas, 250, 200)
aw.on_key_press(aw, Ev(keyval=Gdk.KEY_Delete))
aw.ask_unsaved = lambda: "discard"
aw.close(); settle(0.4)
check("close + Discard: screenshot unchanged", sw.annotate_window is None and len(sw.shapes) == 1)
sw.open_annotate(); settle(0.4); aw = sw.annotate_window
aw.tool_buttons["select"].set_active(True); click(aw.canvas, 250, 200)
aw.on_key_press(aw, Ev(keyval=Gdk.KEY_Delete))
aw.ask_unsaved = lambda: "save"
aw.close(); settle(0.4)
check("close + Keep: arrow deleted from the screenshot", sw.annotate_window is None and sw.shapes == [] and pix(sw.active_pixbuf, 250, 200) == (0xdd, 0xee, 0xff))

sw.open_annotate(); settle(0.3); aw = sw.annotate_window
drag(aw.canvas, 50, 50, 150, 50); aw.done(); settle(0.3)
cap2 = white(300, 200); sw.update_screenshot_buffer(cap2); settle(0.3)
check("a new capture starts with no marks", sw.shapes == [] and sw.base_pixbuf is cap2)
print("FAILURES:", fails or "none")
# Toolbar order: Undo/Redo first, then a divider
w4 = AnnotateWindow(); w4.show_all(); w4.load_pixbuf(white(300, 200), name="t.png"); settle(0.4)
kids = w4.toolbar.get_children()
check("toolbar: Open Save SaveAs Copy | Undo Redo | tools", kids[0] is w4.file_group and isinstance(kids[1], Gtk.Separator)
      and w4.undo_btn.get_parent() is kids[2] and len(w4.file_group.get_children()) == 4
      and w4.file_group.get_children()[3] is w4.copy_btn)
gw = w4.get_window(); Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height()).savev(os.path.join(SP, "annotate_toolbar.png"), "png", [], [])
print("FAILURES:", fails or "none")
