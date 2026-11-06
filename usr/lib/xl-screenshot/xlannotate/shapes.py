"""Annotation marks: each one draws itself and can be hit-tested, moved
and (for boxes, lines and the loupe) reshaped with handles.

All coordinates are in image pixels, so marks stay put whatever size the
image is shown at, and are drawn at full quality when the image is saved.

Every mark has the same style settings:
  stroke  line colour, (r, g, b, a) or None
  fill    fill colour, (r, g, b, a) or None
  size    1-20; what it means depends on the mark (line thickness, text
          size, circle size, pixel block size, lens size)
  dash    "solid", "dashed" or "dotted"
  shadow  True/False
Marks ignore the settings that don't apply to them (an arrow has no fill).
"""

import copy
import math

from gi.repository import Gdk, GdkPixbuf, Pango, PangoCairo

from xlshared.i18n import N_
import cairo

SIZE_MIN, SIZE_MAX = 1, 20
SEE_THROUGH_ALPHA = 0.4
DASHES = ("solid", "dashed", "dotted")
DEFAULT_FONT = "Sans Bold"

# Colour choices: (name, (r, g, b)). Solid or see-through is chosen separately.
COLORS = (
    (N_("Red"), (0.88, 0.11, 0.14)),
    (N_("Orange"), (1.00, 0.47, 0.00)),
    (N_("Yellow"), (0.96, 0.83, 0.18)),
    (N_("Green"), (0.18, 0.76, 0.49)),
    (N_("Blue"), (0.21, 0.52, 0.89)),
    (N_("Purple"), (0.57, 0.25, 0.78)),
    (N_("Pink"), (0.96, 0.36, 0.65)),
    (N_("Black"), (0.0, 0.0, 0.0)),
    (N_("White"), (1.0, 1.0, 1.0)),
)

FALLBACK_STROKE = (0.0, 0.0, 0.0, 1.0)   # for marks that need a colour when the line is None


# What the size slider means for each kind of mark
def line_width(size):
    return float(size)


def text_size(size):
    return 8 + 3 * size            # 11 … 68 px


def step_radius(size):
    return 6 + 1.8 * size          # 8 … 42 px


def pixel_block(size):
    return int(2 + 2 * size)       # 4 … 42 px blocks


def loupe_radius(size):
    return 20 + 5 * size           # 25 … 120 px


def _distance_to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def is_light(color):
    r, g, b = color[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b > 0.6


def snap_angle(x0, y0, x, y):
    """(x, y) moved so the line from (x0, y0) is at a multiple of 45°."""
    dx, dy = x - x0, y - y0
    length = math.hypot(dx, dy)
    angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
    return x0 + length * math.cos(angle), y0 + length * math.sin(angle)


def snap_square(x0, y0, x, y):
    """(x, y) moved so the box from (x0, y0) is a square."""
    d = max(abs(x - x0), abs(y - y0))
    return x0 + math.copysign(d, x - x0 or 1), y0 + math.copysign(d, y - y0 or 1)


def _apply_dash(cr, dash, width):
    if dash == "dashed":
        cr.set_line_cap(cairo.LineCap.BUTT)
        cr.set_dash([width * 3, width * 2])
    elif dash == "dotted":
        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.set_dash([0, width * 2])
    else:
        cr.set_dash([])


class Shape:
    """Base class. Subclasses say which style settings they use."""

    USES_LINE = True
    USES_FILL = False
    USES_DASH = False
    USES_SHADOW = True
    USES_SIZE = True

    def __init__(self, stroke=FALLBACK_STROKE, fill=None, size=6, dash="solid",
                 shadow=False, font=DEFAULT_FONT):
        self.stroke = tuple(stroke) if stroke is not None else None
        self.fill = tuple(fill) if fill is not None else None
        self.size = size
        self.dash = dash
        self.shadow = shadow
        self.font = font

    def copy(self):
        return copy.deepcopy(self)

    def ink(self):
        """The line colour, for marks that must have one."""
        return self.stroke or FALLBACK_STROKE

    def draw(self, cr, base=None, number=None):
        """base: the image (pixelate, loupe). number: step number."""
        raise NotImplementedError

    def bounds(self):
        """(x, y, w, h) that fully contains the drawn mark."""
        raise NotImplementedError

    def contains(self, x, y, tolerance):
        raise NotImplementedError

    def move_by(self, dx, dy):
        raise NotImplementedError

    def is_too_small(self):
        return False

    # Reshaping: marks without handles return {}
    def handles(self):
        return {}

    def special_handles(self):
        """Handles that change the shape itself rather than its size
        (drawn green, as in Preview)."""
        return set()

    def drag_handle(self, name, x, y, start, constrain=False):
        """Move handle `name` to (x, y). start: a copy taken when the drag
        began. constrain: Shift is held."""


# ---- Line-shaped marks: two ends to drag ----

class LineShape(Shape):
    """A straight line from (x1, y1) to (x2, y2)."""

    USES_DASH = True

    def __init__(self, x1, y1, x2, y2, **style):
        super().__init__(**style)
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

    def is_too_small(self):
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1) < 4

    def _stroke_line(self, cr, to_x, to_y, color=None):
        width = line_width(self.size)
        cr.set_source_rgba(*(color or self.ink()))
        cr.set_line_width(width)
        cr.set_line_cap(cairo.LineCap.ROUND)
        _apply_dash(cr, self.dash, width)
        cr.move_to(self.x1, self.y1)
        cr.line_to(to_x, to_y)
        cr.stroke()

    def draw(self, cr, base=None, number=None):
        cr.save()
        self._stroke_line(cr, self.x2, self.y2)
        cr.restore()

    def _pad(self):
        return line_width(self.size)

    def bounds(self):
        pad = self._pad()
        x = min(self.x1, self.x2) - pad
        y = min(self.y1, self.y2) - pad
        return (x, y, abs(self.x2 - self.x1) + 2 * pad, abs(self.y2 - self.y1) + 2 * pad)

    def contains(self, x, y, tolerance):
        d = _distance_to_segment(x, y, self.x1, self.y1, self.x2, self.y2)
        return d <= line_width(self.size) / 2 + tolerance

    def move_by(self, dx, dy):
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def handles(self):
        return {"start": (self.x1, self.y1), "end": (self.x2, self.y2)}

    def drag_handle(self, name, x, y, start, constrain=False):
        if name == "start":
            if constrain:
                x, y = snap_angle(start.x2, start.y2, x, y)
            self.x1, self.y1 = x, y
        elif name == "end":
            if constrain:
                x, y = snap_angle(start.x1, start.y1, x, y)
            self.x2, self.y2 = x, y


class ArrowShape(LineShape):
    """A straight arrow from (x1, y1) to the head at (x2, y2)."""

    def _head_size(self):
        return max(12.0, line_width(self.size) * 4.0)

    def draw(self, cr, base=None, number=None):
        length = math.hypot(self.x2 - self.x1, self.y2 - self.y1)
        if length < 1:
            return
        ux, uy = (self.x2 - self.x1) / length, (self.y2 - self.y1) / length
        head = min(self._head_size(), length)
        half = head * 0.55
        # Point where the head starts
        bx, by = self.x2 - ux * head, self.y2 - uy * head

        r, g, b, alpha = self.ink()
        sheer = alpha < 0.999
        cr.save()
        if sheer:
            # Shaft and head overlap. Drawn see-through one after the other,
            # the overlap would come out darker, so draw them solid on a
            # layer and fade the whole layer once.
            cr.push_group()
        solid = (r, g, b, 1.0)
        # Shaft stops a little inside the head so the round cap doesn't poke out
        self._stroke_line(cr, bx + ux * head * 0.3, by + uy * head * 0.3, solid)
        # Head (never dashed)
        cr.set_dash([])
        cr.set_source_rgba(*solid)
        cr.move_to(self.x2, self.y2)
        cr.line_to(bx - uy * half, by + ux * half)
        cr.line_to(bx + uy * half, by - ux * half)
        cr.close_path()
        cr.fill()
        if sheer:
            cr.pop_group_to_source()
            cr.paint_with_alpha(alpha)
        cr.restore()

    def _pad(self):
        return self._head_size() * 0.6 + line_width(self.size)

    def contains(self, x, y, tolerance):
        if super().contains(x, y, tolerance):
            return True
        # The head is wider than the shaft
        return math.hypot(x - self.x2, y - self.y2) <= self._head_size() * 0.6 + tolerance


# ---- Freehand: a drawn path ----

def _path_length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def smooth_points(points, min_step=2.0, passes=2):
    """Take the jitter out of a mouse-drawn path: drop points closer than
    min_step to the last one kept, then round off the corners (Chaikin's
    method). The first and last points stay where they were."""
    if len(points) < 3:
        return list(points)
    kept = [points[0]]
    for p in points[1:-1]:
        if math.hypot(p[0] - kept[-1][0], p[1] - kept[-1][1]) >= min_step:
            kept.append(p)
    kept.append(points[-1])
    for _ in range(passes):
        if len(kept) < 3:
            break
        new = [kept[0]]
        for a, b in zip(kept, kept[1:]):
            new.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            new.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        new.append(kept[-1])
        kept = new
    return kept


class FreehandShape(Shape):
    """A line drawn with the mouse: a list of points. Its eight handles
    stretch the whole drawing (Shift keeps its proportions)."""

    USES_DASH = True

    def __init__(self, points, **style):
        super().__init__(**style)
        self.points = [tuple(p) for p in points]

    def add_point(self, x, y):
        last = self.points[-1] if self.points else None
        if last is None or math.hypot(x - last[0], y - last[1]) >= 1.0:
            self.points.append((x, y))

    def finish(self):
        """Smooth the path once drawing is done."""
        self.points = smooth_points(self.points)

    def length(self):
        return _path_length(self.points)

    def is_too_small(self):
        return len(self.points) < 2 or self.length() < 4

    def draw(self, cr, base=None, number=None):
        if not self.points:
            return
        width = line_width(self.size)
        cr.save()
        cr.new_path()
        cr.set_source_rgba(*self.ink())
        cr.set_line_width(width)
        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.set_line_join(cairo.LineJoin.ROUND)
        _apply_dash(cr, self.dash, width)
        cr.move_to(*self.points[0])
        if len(self.points) == 1:
            cr.line_to(*self.points[0])
        for p in self.points[1:]:
            cr.line_to(*p)
        cr.stroke()
        cr.restore()

    def _box(self):
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def bounds(self):
        x0, y0, x1, y1 = self._box()
        pad = line_width(self.size)
        return (x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)

    def contains(self, x, y, tolerance):
        reach = line_width(self.size) / 2 + tolerance
        if len(self.points) == 1:
            return math.hypot(x - self.points[0][0], y - self.points[0][1]) <= reach
        return any(_distance_to_segment(x, y, *a, *b) <= reach
                   for a, b in zip(self.points, self.points[1:]))

    def move_by(self, dx, dy):
        self.points = [(px + dx, py + dy) for px, py in self.points]

    def handles(self):
        x0, y0, x1, y1 = self._box()
        w, h = x1 - x0, y1 - y0
        return {
            "nw": (x0, y0), "n": (x0 + w / 2, y0), "ne": (x1, y0), "e": (x1, y0 + h / 2),
            "se": (x1, y1), "s": (x0 + w / 2, y1), "sw": (x0, y1), "w": (x0, y0 + h / 2),
        }

    def drag_handle(self, name, x, y, start, constrain=False):
        sx0, sy0, sx1, sy1 = start._box()
        sw, sh = sx1 - sx0, sy1 - sy0
        x1, y1, x2, y2 = sx0, sy0, sx1, sy1
        if constrain and len(name) == 2 and sw > 0 and sh > 0:
            # Corner with Shift: same proportions, anchored at the opposite corner
            ax = sx1 if "w" in name else sx0
            ay = sy1 if "n" in name else sy0
            scale = max(abs(x - ax) / sw, abs(y - ay) / sh)
            x = ax + math.copysign(scale * sw, (x - ax) or 1)
            y = ay + math.copysign(scale * sh, (y - ay) or 1)
        if "n" in name:
            y1 = y
        if "s" in name:
            y2 = y
        if "w" in name:
            x1 = x
        if "e" in name:
            x2 = x
        # Map every point from the old box to the new one (a flipped box
        # mirrors the drawing)
        def mx(px):
            return x1 + (px - sx0) / sw * (x2 - x1) if sw > 0 else px + (x1 - sx0)

        def my(py):
            return y1 + (py - sy0) / sh * (y2 - y1) if sh > 0 else py + (y1 - sy0)
        self.points = [(mx(px), my(py)) for px, py in start.points]


# ---- Box-shaped marks: eight handles to drag ----

class BoxShape(Shape):
    """Anything defined by a rectangle. (x, y) is the top-left corner."""

    def __init__(self, x, y, w, h, **style):
        super().__init__(**style)
        self.x, self.y, self.w, self.h = x, y, w, h

    def set_corners(self, x1, y1, x2, y2):
        self.x, self.y = min(x1, x2), min(y1, y2)
        self.w, self.h = abs(x2 - x1), abs(y2 - y1)

    def is_too_small(self):
        return self.w < 4 or self.h < 4

    def bounds(self):
        return (self.x, self.y, self.w, self.h)

    def contains(self, x, y, tolerance):
        return (self.x - tolerance <= x <= self.x + self.w + tolerance and
                self.y - tolerance <= y <= self.y + self.h + tolerance)

    def move_by(self, dx, dy):
        self.x += dx
        self.y += dy

    def handles(self):
        x, y, w, h = self.x, self.y, self.w, self.h
        return {
            "nw": (x, y), "n": (x + w / 2, y), "ne": (x + w, y), "e": (x + w, y + h / 2),
            "se": (x + w, y + h), "s": (x + w / 2, y + h), "sw": (x, y + h), "w": (x, y + h / 2),
        }

    def drag_handle(self, name, x, y, start, constrain=False):
        # Work from the box as it was when the drag began, so dragging
        # past the opposite edge flips it cleanly
        x1, y1 = start.x, start.y
        x2, y2 = start.x + start.w, start.y + start.h
        if constrain and len(name) == 2:
            # Corner with Shift: keep it square, anchored at the opposite corner
            ax = x2 if "w" in name else x1
            ay = y2 if "n" in name else y1
            x, y = snap_square(ax, ay, x, y)
        if "n" in name:
            y1 = y
        if "s" in name:
            y2 = y
        if "w" in name:
            x1 = x
        if "e" in name:
            x2 = x
        self.set_corners(x1, y1, x2, y2)


class RectShape(BoxShape):
    """A rectangle: an outline, a fill, or both."""

    USES_FILL = True
    USES_DASH = True

    def _path(self, cr):
        cr.rectangle(self.x, self.y, self.w, self.h)

    def draw(self, cr, base=None, number=None):
        cr.save()
        if self.fill is not None:
            self._path(cr)
            cr.set_source_rgba(*self.fill)
            cr.fill()
        if self.stroke is not None:
            width = line_width(self.size)
            self._path(cr)
            cr.set_source_rgba(*self.stroke)
            cr.set_line_width(width)
            cr.set_line_join(cairo.LineJoin.ROUND)
            _apply_dash(cr, self.dash, width)
            cr.stroke()
        cr.restore()

    def bounds(self):
        half = line_width(self.size) / 2 if self.stroke is not None else 0
        return (self.x - half, self.y - half, self.w + 2 * half, self.h + 2 * half)

    def contains(self, x, y, tolerance):
        reach = line_width(self.size) / 2 + tolerance
        inside_outer = (self.x - reach <= x <= self.x + self.w + reach and
                        self.y - reach <= y <= self.y + self.h + reach)
        if self.fill is not None:
            return inside_outer
        # Outline only: just the line counts, so marks inside can still be clicked
        inside_inner = (self.x + reach < x < self.x + self.w - reach and
                        self.y + reach < y < self.y + self.h - reach)
        return inside_outer and not inside_inner


class EllipseShape(RectShape):
    """An ellipse (or circle) inside the box."""

    def _path(self, cr):
        if self.w < 0.5 or self.h < 0.5:
            return
        cr.save()
        cr.translate(self.x + self.w / 2, self.y + self.h / 2)
        cr.scale(self.w / 2, self.h / 2)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()

    def contains(self, x, y, tolerance):
        rx, ry = self.w / 2, self.h / 2
        if rx < 0.5 or ry < 0.5:
            return False
        cx, cy = self.x + rx, self.y + ry
        reach = line_width(self.size) / 2 + tolerance
        # Distance from the edge, measured along the line to the centre
        d = math.hypot((x - cx) / rx, (y - cy) / ry)
        edge_dist = abs(d - 1) * min(rx, ry)
        if self.fill is not None:
            return d <= 1 or edge_dist <= reach
        return edge_dist <= reach


class HighlightShape(BoxShape):
    """A marker box. It's blended like a real highlighter (multiply), so dark
    text under it stays dark and sharp. Uses the line colour."""

    USES_SHADOW = False
    USES_SIZE = False

    def draw(self, cr, base=None, number=None):
        cr.save()
        cr.set_operator(cairo.Operator.MULTIPLY)
        cr.set_source_rgba(*self.ink())
        cr.rectangle(self.x, self.y, self.w, self.h)
        cr.fill()
        cr.restore()


# A few recent pixelated areas, so redrawing while you work stays quick
_pixelate_cache = []
_PIXELATE_CACHE_SIZE = 4


class PixelateShape(BoxShape):
    """Hides what's underneath by turning it into blocks. The size slider
    sets the block size."""

    USES_LINE = False
    USES_SHADOW = False

    @property
    def block(self):
        return pixel_block(self.size)

    def _pixelated(self, base, x0, y0, w, h):
        key = (x0, y0, w, h, self.block)
        for k_base, k, pixbuf in _pixelate_cache:
            if k_base is base and k == key:
                return pixbuf
        b = self.block
        sw, sh = max(1, math.ceil(w / b)), max(1, math.ceil(h / b))
        small = base.new_subpixbuf(x0, y0, w, h).scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
        big = small.scale_simple(sw * b, sh * b, GdkPixbuf.InterpType.NEAREST)
        _pixelate_cache.append((base, key, big))
        del _pixelate_cache[:-_PIXELATE_CACHE_SIZE]
        return big

    def draw(self, cr, base=None, number=None):
        if base is None:
            return
        # Only the part that's on the image
        x0, y0 = max(0, int(self.x)), max(0, int(self.y))
        x1 = min(base.get_width(), math.ceil(self.x + self.w))
        y1 = min(base.get_height(), math.ceil(self.y + self.h))
        if x1 - x0 < 1 or y1 - y0 < 1:
            return
        big = self._pixelated(base, x0, y0, x1 - x0, y1 - y0)
        cr.save()
        cr.rectangle(x0, y0, x1 - x0, y1 - y0)
        cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, big, x0, y0)
        cr.get_source().set_filter(cairo.Filter.NEAREST)
        cr.paint()
        cr.restore()


# ---- Loupe: a magnifying lens ----

LOUPE_ZOOM_MIN, LOUPE_ZOOM_MAX = 1.5, 6.0
_DIAL_SPAN = 270.0      # the zoom handle travels 3/4 of the way round the ring


class LoupeShape(Shape):
    """A round lens centred on (cx, cy) showing the image underneath
    enlarged. The blue handle sets its size; the green handle is a dial
    for how much it zooms (round clockwise for more)."""

    USES_DASH = False

    def __init__(self, cx, cy, zoom=2.0, **style):
        super().__init__(**style)
        self.cx, self.cy, self.zoom = cx, cy, zoom

    @property
    def radius(self):
        return loupe_radius(self.size)

    def _ring_width(self):
        return max(2.0, self.radius * 0.06)

    def draw(self, cr, base=None, number=None):
        r = self.radius
        cr.save()
        cr.new_path()
        cr.arc(self.cx, self.cy, r, 0, 2 * math.pi)
        if base is not None:
            cr.save()
            cr.clip_preserve()
            cr.set_source_rgb(1, 1, 1)
            cr.fill_preserve()
            cr.translate(self.cx, self.cy)
            cr.scale(self.zoom, self.zoom)
            cr.translate(-self.cx, -self.cy)
            Gdk.cairo_set_source_pixbuf(cr, base, 0, 0)
            cr.get_source().set_filter(cairo.Filter.GOOD)
            cr.paint()
            cr.restore()
        cr.set_source_rgba(*self.ink())
        cr.set_line_width(self._ring_width())
        cr.stroke()
        cr.restore()

    def bounds(self):
        r = self.radius + self._ring_width()
        return (self.cx - r, self.cy - r, 2 * r, 2 * r)

    def contains(self, x, y, tolerance):
        return math.hypot(x - self.cx, y - self.cy) <= self.radius + tolerance

    def move_by(self, dx, dy):
        self.cx += dx
        self.cy += dy

    def _dial_angle(self):
        t = (self.zoom - LOUPE_ZOOM_MIN) / (LOUPE_ZOOM_MAX - LOUPE_ZOOM_MIN)
        return math.radians(-90 + t * _DIAL_SPAN)

    def handles(self):
        r = self.radius
        a = self._dial_angle()
        return {
            "size": (self.cx + r * math.cos(math.radians(45)), self.cy + r * math.sin(math.radians(45))),
            "zoom": (self.cx + r * math.cos(a), self.cy + r * math.sin(a)),
        }

    def special_handles(self):
        return {"zoom"}

    def drag_handle(self, name, x, y, start, constrain=False):
        if name == "size":
            dist = math.hypot(x - self.cx, y - self.cy)
            self.size = max(SIZE_MIN, min(SIZE_MAX, (dist - 20) / 5))
        elif name == "zoom":
            # Angle round the ring, clockwise from the top, 0…360
            ang = (math.degrees(math.atan2(y - self.cy, x - self.cx)) + 90) % 360
            if ang > _DIAL_SPAN:      # in the gap: go to the nearer end
                ang = _DIAL_SPAN if ang < (360 + _DIAL_SPAN) / 2 else 0
            self.zoom = LOUPE_ZOOM_MIN + ang / _DIAL_SPAN * (LOUPE_ZOOM_MAX - LOUPE_ZOOM_MIN)


# ---- Point marks: text and numbered steps ----

# A scratch surface for measuring text without drawing it
_measure_cr = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


def _make_layout(cr, text, size, font=DEFAULT_FONT):
    layout = PangoCairo.create_layout(cr)
    desc = Pango.FontDescription.from_string(font or DEFAULT_FONT)
    desc.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(desc)
    layout.set_text(text, -1)
    return layout


class TextShape(Shape):
    """Text, one or more lines. (x, y) is the top-left corner of the words.
    The line colour colours the letters; the fill colour (if any) puts a
    box behind them, which keeps text readable on busy screenshots."""

    USES_FILL = True

    def __init__(self, x, y, text, **style):
        super().__init__(**style)
        self.x, self.y, self.text = x, y, text

    @property
    def text_size(self):
        return text_size(self.size)

    def _padding(self):
        return self.text_size * 0.25

    def _text_extents(self, cr):
        _ink, logical = _make_layout(cr, self.text, self.text_size, self.font).get_pixel_extents()
        return logical

    def draw(self, cr, base=None, number=None):
        cr.save()
        layout = _make_layout(cr, self.text, self.text_size, self.font)
        if self.fill is not None:
            _ink, logical = layout.get_pixel_extents()
            p = self._padding()
            x, y = self.x + logical.x - p, self.y + logical.y - p
            w, h = logical.width + 2 * p, logical.height + 2 * p
            r = min(p, w / 2, h / 2)
            cr.new_path()
            cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
            cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
            cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
            cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
            cr.close_path()
            cr.set_source_rgba(*self.fill)
            cr.fill()
        cr.move_to(self.x, self.y)
        cr.set_source_rgba(*self.ink())
        PangoCairo.show_layout(cr, layout)
        cr.restore()

    def bounds(self):
        logical = self._text_extents(_measure_cr)
        p = self._padding() if self.fill is not None else 0
        return (self.x + logical.x - p, self.y + logical.y - p,
                max(1, logical.width) + 2 * p, max(1, logical.height) + 2 * p)

    def contains(self, x, y, tolerance):
        bx, by, bw, bh = self.bounds()
        return (bx - tolerance <= x <= bx + bw + tolerance and
                by - tolerance <= y <= by + bh + tolerance)

    def move_by(self, dx, dy):
        self.x += dx
        self.y += dy


class StepShape(Shape):
    """A numbered circle centred on (x, y), in the line colour. The number
    isn't stored: steps are numbered 1, 2, 3… in the order they were added,
    so deleting one renumbers the rest."""

    def __init__(self, x, y, **style):
        super().__init__(**style)
        self.x, self.y = x, y

    @property
    def radius(self):
        return step_radius(self.size)

    def draw(self, cr, base=None, number=None):
        r = self.radius
        cr.save()
        # Start a fresh path, or cairo joins the circle to wherever the
        # previous mark finished drawing with a straight line
        cr.new_path()
        cr.arc(self.x, self.y, r, 0, 2 * math.pi)
        cr.set_source_rgba(*self.ink())
        cr.fill_preserve()
        # Thin white ring so it stands out on dark and busy backgrounds
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.set_line_width(max(1.5, r * 0.1))
        cr.stroke()
        layout = _make_layout(cr, str(number or "?"), r * 1.1)
        _ink, logical = layout.get_pixel_extents()
        cr.move_to(self.x - logical.width / 2 - logical.x, self.y - logical.height / 2 - logical.y)
        cr.set_source_rgb(*((0, 0, 0) if is_light(self.ink()) else (1, 1, 1)))
        PangoCairo.show_layout(cr, layout)
        cr.restore()

    def bounds(self):
        r = self.radius + 2
        return (self.x - r, self.y - r, 2 * r, 2 * r)

    def contains(self, x, y, tolerance):
        return math.hypot(x - self.x, y - self.y) <= self.radius + tolerance

    def move_by(self, dx, dy):
        self.x += dx
        self.y += dy


# ---- Drawing everything ----

def _draw_with_shadow(cr, shape, base, number):
    """Draw the mark once into a temporary layer, then use that layer's
    shape as a soft grey shadow underneath it."""
    cr.push_group()
    shape.draw(cr, base, number)
    layer = cr.pop_group()
    off = 2.0 + line_width(shape.size) * 0.3
    for dx, dy, alpha in ((off, off, 0.22), (off + 1.5, off + 1.5, 0.10),
                          (off - 1, off + 1, 0.08), (off + 1, off - 1, 0.08)):
        cr.save()
        cr.translate(dx, dy)
        cr.set_source_rgba(0, 0, 0, alpha)
        cr.mask(layer)
        cr.restore()
    cr.set_source(layer)
    cr.paint()


def draw_shapes(cr, shapes, base, extra=None):
    """Draw marks in order, numbering the steps. extra: one more mark being
    drawn right now (not in the list yet)."""
    number = 0
    for shape in list(shapes) + ([extra] if extra is not None else []):
        n = None
        if isinstance(shape, StepShape):
            number += 1
            n = number
        if shape.shadow and shape.USES_SHADOW:
            _draw_with_shadow(cr, shape, base, n)
        else:
            shape.draw(cr, base, n)


def render_flat(base_pixbuf, shapes):
    """The image with all marks drawn in, at full size, as a new pixbuf."""
    w, h = base_pixbuf.get_width(), base_pixbuf.get_height()
    # Keep images without transparency that way (smaller files, JPEG-friendly)
    fmt = cairo.FORMAT_ARGB32 if base_pixbuf.get_has_alpha() else cairo.FORMAT_RGB24
    surface = cairo.ImageSurface(fmt, w, h)
    cr = cairo.Context(surface)
    Gdk.cairo_set_source_pixbuf(cr, base_pixbuf, 0, 0)
    cr.paint()
    draw_shapes(cr, shapes, base_pixbuf)
    surface.flush()
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)
