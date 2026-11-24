import helpers  # noqa: F401  (paths, a temporary home folder, English)
import sys
import gi; gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0"); gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0"); gi.require_version("PangoCairo", "1.0")
from gi.repository import GdkPixbuf
from xlannotate import shapes as S
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def pix(pb, x, y):
    o = int(y) * pb.get_rowstride() + int(x) * pb.get_n_channels(); return tuple(pb.get_pixels()[o:o+3])
base = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 400, 120); base.fill(0xffffffff)
for alpha, label in ((0.4, "sheer"), (1.0, "solid")):
    a = S.ArrowShape(20, 60, 380, 60, stroke=(0.88, 0.11, 0.14, alpha), size=10)
    head = a._head_size(); bx = 380 - head
    flat = S.render_flat(base, [a])
    shaft = pix(flat, 150, 60)
    overlap = pix(flat, bx + head * 0.15, 60)        # where the shaft runs into the head
    tip = pix(flat, 380 - head * 0.15, 60)
    print(f"  {label}: shaft {shaft}  overlap {overlap}  head {tip}")
    check(f"{label} arrow: one even color (shaft = overlap = head)", shaft == overlap == tip)
    # The shadow on its own (just below the shaft, outside the arrow) must be
    # an even grey too: no darker band where the shaft meets the head
    a.shadow = True
    f2 = S.render_flat(base, [a])
    below = [pix(f2, x, 66) for x in range(60, int(bx - 4))]
    check(f"{label} arrow with shadow: the shadow is even along the shaft", len(set(below)) == 1 and below[0] != (255, 255, 255))
a = S.ArrowShape(20, 60, 380, 60, stroke=(0.88, 0.11, 0.14, 0.4), size=10, dash="dashed")
f3 = S.render_flat(base, [a])
check("sheer dashed arrow: dashes still have gaps", len({pix(f3, x, 60) for x in range(30, 300)}) >= 2)

# Rectangles and ellipses with a see-through line and fill: no darker band where
# the line's inside half lies on the fill (found testing 0.2.0~test3)
RED_SHEER, GREEN_SHEER = (0.88, 0.11, 0.14, 0.4), (0.18, 0.76, 0.49, 0.4)
big = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 400, 240); big.fill(0xffffffff)
for cls, label in ((S.RectShape, "rectangle"), (S.EllipseShape, "ellipse")):
    for line, fill, kind in ((RED_SHEER, GREEN_SHEER, "sheer line, sheer fill"),
                             (RED_SHEER, (0.18, 0.76, 0.49, 1.0), "sheer line, solid fill"),
                             ((0.88, 0.11, 0.14, 1.0), GREEN_SHEER, "solid line, sheer fill")):
        m = cls(100, 20, 200, 200, stroke=line, fill=fill, size=10)      # a 10 px line on the edge at x=100
        flat = S.render_flat(big, [m])
        outer, inner, middle = pix(flat, 97, 120), pix(flat, 103, 120), pix(flat, 200, 120)
        check(f"{label}, {kind}: the line is one even color across its width ({outer} / {inner})", outer == inner)
        check(f"{label}, {kind}: the fill still shows inside", middle not in ((255, 255, 255), outer))
solid = S.render_flat(big, [S.RectShape(100, 20, 200, 200, stroke=(0.88, 0.11, 0.14, 1), fill=(0.18, 0.76, 0.49, 1), size=10)])
check("solid line and fill look just as before", pix(solid, 103, 120) == pix(solid, 97, 120) and pix(solid, 200, 120)[1] > 150)
dashed = S.render_flat(big, [S.RectShape(100, 20, 200, 200, stroke=RED_SHEER, fill=GREEN_SHEER, size=10, dash="dashed")])
check("a dashed sheer outline still has gaps", len({pix(dashed, 103, y) for y in range(40, 200)}) >= 2)
print("FAILURES:", fails or "none")
