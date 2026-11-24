from common import *
import scenery
from xlshared.ui import add_icon_search_path
from xlannotate.window import AnnotateWindow
from xlannotate import shapes as S
start_wm(); add_icon_search_path()
IW, IH = 1840, 1100
img, poi = scenery.draw(IW, IH)
pb = pixbuf_from_surface(img)
RED = (0.88, 0.11, 0.14, 1.0); WHITE = (1, 1, 1, 1)
cx, cy = poi["cabin"]; sx, sy = poi["summit"]
marks = []
# the trail from the cabin up to the summit, dotted
trail = [(cx + 40, cy - 70), (cx + 120, cy - 120), (cx + 190, cy - 200), (cx + 170, cy - 280),
         (cx + 240, cy - 350), (cx + 230, cy - 420), (sx - 10, sy + 70), (sx, sy + 18)]
pts = []
for (x0, y0), (x1, y1) in zip(trail, trail[1:]):
    for i in range(12):
        t = i / 12; pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
pts.append(trail[-1])
marks.append(S.FreehandShape(S.smooth_points(pts, passes=3), stroke=WHITE, size=6, dash="dotted", shadow=True))
for i in (1, 3, 6):
    x, y = trail[i]
    marks.append(S.StepShape(x + 46, y, stroke=RED, size=9, shadow=True))
marks.append(S.LoupeShape(cx - 10, cy - 30, zoom=1.8, stroke=WHITE, size=14, shadow=True))
note = S.TextShape(60, 440, "Sunrise hike:\n3 hours to the top", stroke=WHITE, fill=RED, size=10, shadow=True)
marks.append(note)
note_arrow = S.ArrowShape(330, 430, sx - 40, sy + 14, stroke=RED, size=8, shadow=True)
note_arrow.set_middle((330 + sx - 40) / 2 - 40, (430 + sy + 14) / 2 - 60)     # a gentle curve
marks.append(note_arrow)
win = AnnotateWindow()
win.load_pixbuf(pb, name="Mountain Lake.png", shapes=marks)
win.resize(1060, 640); win.show_all(); settle(1.5)
win.canvas.zoom_fit(); settle(0.8)
win.canvas.select(None); settle(0.5)
raw = grab(win)
save(decorate(raw), "annotate")
S.render_flat(pb, marks).savev(f"{OUT}/annotated-image.png", "png", [], [])
print("annotate", raw.get_width(), raw.get_height())
