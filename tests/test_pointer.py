"""Include Pointer on X11 without Cinnamon's service: the real pointer, as the
theme draws it (from X11's XFixes), not a stand-in arrow."""
import helpers  # noqa: F401  (paths, a temporary home folder, English)
from gi.repository import Gdk
from xlscreenshot import capture

fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def pixels(pb):
    return pb.get_pixels(), pb.get_rowstride(), pb.get_n_channels()
def same(a, b):
    """The same picture (RGB only)."""
    if (a.get_width(), a.get_height()) != (b.get_width(), b.get_height()):
        return False
    pa, ra, na = pixels(a); pb, rb, nb = pixels(b)
    return all(pa[y * ra + x * na: y * ra + x * na + 3] == pb[y * rb + x * nb: y * rb + x * nb + 3]
               for y in range(a.get_height()) for x in range(a.get_width()))

pointer = capture.get_pointer_image()
check("X11 tells us what the pointer looks like (XFixes)", pointer is not None)
surface, left, top = pointer
# Xvfb's pointer sits in the middle of the screen; capture around it
x, y = left - 20, top - 20
plain = capture.capture_region(x, y, 60, 60, False)
with_pointer = capture.capture_region(x, y, 60, 60, True)
check("Include Pointer changes the picture", not same(plain, with_pointer))
check("…to exactly the real pointer, where it is",
      same(with_pointer, capture.draw_pointer_image(plain, x, y, pointer)))
standin = capture.draw_cursor_on_pixbuf(plain, x, y, (left + 7, top + 7))
check("…not the stand-in arrow", not same(with_pointer, standin))
outside = capture.capture_region(0, 0, 40, 40, True)
check("a capture away from the pointer has no pointer", same(outside, capture.capture_region(0, 0, 40, 40, False)))
real = capture.get_pointer_image
capture.get_pointer_image = lambda: None
check("without XFixes: the stand-in arrow, as before",
      not same(capture.capture_region(x, y, 60, 60, True), plain))
capture.get_pointer_image = real
print("FAILURES:", fails or "none")
