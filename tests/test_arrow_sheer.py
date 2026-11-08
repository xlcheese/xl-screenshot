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
    check(f"{label} arrow: one even colour (shaft = overlap = head)", shaft == overlap == tip)
    # The shadow on its own (just below the shaft, outside the arrow) must be
    # an even grey too: no darker band where the shaft meets the head
    a.shadow = True
    f2 = S.render_flat(base, [a])
    below = [pix(f2, x, 66) for x in range(60, int(bx - 4))]
    check(f"{label} arrow with shadow: the shadow is even along the shaft", len(set(below)) == 1 and below[0] != (255, 255, 255))
a = S.ArrowShape(20, 60, 380, 60, stroke=(0.88, 0.11, 0.14, 0.4), size=10, dash="dashed")
f3 = S.render_flat(base, [a])
check("sheer dashed arrow: dashes still have gaps", len({pix(f3, x, 60) for x in range(30, 300)}) >= 2)
print("FAILURES:", fails or "none")
