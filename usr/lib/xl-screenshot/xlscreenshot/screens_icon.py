"""The Screens button's icon: our Screen drawing once for every monitor,
placed and sized as the monitors are arranged in the display settings.

Each monitor is drawn from the same SVG as the Screen button, "nine-slice"
fashion: its corners, bezel and stand keep the size they have in the Screen
icon and only the middle stretches, so every monitor has the same line weight
as Screen however many there are, and a portrait monitor still looks right.
"""

import math
import os

import cairo
from gi.repository import GdkPixbuf

ICON_HEIGHT = 48     # units: the same height as the other button icons
ICON_MAX_WIDTH = 76  # units: wide layouts may use most of the button
GAP = 2.5            # units between neighbouring monitors
MAX_DRAWN = 4        # more monitors than this are drawn as a 2x2

# Where things are in the Screen SVG (512 x 512 units)
_SVG_NAME = "xl-screenshot-screen-symbolic.svg"
_CURVE_BOTTOM = 404                # the lowest point of the curved bottom bezel
_FRAME = (0, 55, 512, _CURVE_BOTTOM - 55)        # the monitor, curved bezel included
_STAND = (132, _CURVE_BOTTOM, 247, 457 - _CURVE_BOTTOM)   # neck and oval base, below the bezel
_OPENING = (20, 76, 472, 286)      # the screen inside the frame (x, y, w, h)
_CORNER = 44                       # how much of each frame edge keeps its size
_BOTTOM = 70                       # the curved bottom bezel keeps its height too
_SCREEN_SCALE = ICON_HEIGHT / 512  # units per SVG unit in the Screen icon

_art = _frame_art = None


def _svg_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (os.path.join(here, os.pardir, os.pardir, os.pardir, "share"), "/usr/share"):
        path = os.path.normpath(os.path.join(base, "icons", "hicolor", "scalable", "actions", _SVG_NAME))
        if os.path.isfile(path):
            return path
    return None


def _artwork():
    """The Screen SVG as a big image, used as a stencil (its color is ignored),
    and a copy with only the monitor (the stand's neck starts inside the
    curved bezel, and mustn't be stretched with it)."""
    global _art, _frame_art
    if _art is None:
        path = _svg_path()
        if path is None:
            return None
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 1024, 1024)
        _art = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1024, 1024)
        cr = cairo.Context(_art)
        from gi.repository import Gdk
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()
        _frame_art = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1024, 1024)
        cr = cairo.Context(_frame_art)
        cr.set_source_surface(_art, 0, 0)
        cr.paint()
        cr.set_operator(cairo.Operator.CLEAR)
        cr.rectangle(0, _CURVE_BOTTOM * 2, 1024, 1024)
        cr.fill()
    return _art


def _tile(cr, art, src, dst, color):
    """Paint the part src (x, y, w, h, in SVG units) of the stencil into dst."""
    sx, sy, sw, sh = src
    dx, dy, dw, dh = dst
    if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
        return
    k = art.get_width() / 512
    cr.save()
    # A sharp-edged clip on whole pixels: neighbouring pieces then meet
    # exactly, with no faint seam between them
    cr.set_antialias(cairo.Antialias.NONE)
    cr.rectangle(dx, dy, dw, dh)
    cr.clip()
    cr.set_antialias(cairo.Antialias.DEFAULT)
    cr.translate(dx, dy)
    cr.scale(dw / (sw * k), dh / (sh * k))
    cr.translate(-sx * k, -sy * k)
    cr.set_source_rgba(*color)
    cr.mask_surface(art, 0, 0)
    cr.restore()


def _monitor(cr, art, x, y, w, h, f, color, scale=1):
    """One monitor frame filling (x, y, w, h); its edges drawn at scale f.
    The joins between its pieces are put on whole device pixels."""
    fx, fy, fw, fh = _FRAME
    c, b = _CORNER, _BOTTOM
    snap = lambda v: round(v * scale) / scale
    x, y = snap(x), snap(y)
    w, h = snap(x + w) - x, snap(y + h) - y
    cw, ch, cb = snap(min(c * f, w / 2)), snap(min(c * f, h / 2)), snap(min(b * f, h / 2))
    cols = ((fx, c, x, cw), (fx + c, fw - 2 * c, x + cw, w - 2 * cw), (fx + fw - c, c, x + w - cw, cw))
    rows = ((fy, c, y, ch), (fy + c, fh - c - b, y + ch, h - ch - cb), (fy + fh - b, b, y + h - cb, cb))
    for sx, sw, dx, dw in cols:
        for sy, sh, dy, dh in rows:
            _tile(cr, art, (sx, sy, sw, sh), (dx, dy, dw, dh), color)


def _has_below(m, monitors):
    x, y, w, h = m
    return any(o is not m and abs(o[1] - (y + h)) < 8 and o[0] < x + w and o[0] + o[2] > x for o in monitors)


def render(monitors, color, scale=1, max_width=ICON_MAX_WIDTH, height=ICON_HEIGHT):
    """The icon as a cairo surface (device scale `scale`), or None.
    monitors: their (x, y, w, h) from the display settings. color: rgba."""
    art = _artwork()
    if art is None or not monitors:
        return None
    if len(monitors) > MAX_DRAWN:
        # More than four would be too small to read: a 2x2 stands for "many"
        # (the capture still takes every monitor)
        monitors = [(0, 0, 16, 9), (16, 0, 16, 9), (0, 9, 16, 9), (16, 9, 16, 9)]
    f = _SCREEN_SCALE                         # bezels and stands as in the Screen icon
    stand_h = _STAND[3] * f
    x0 = min(m[0] for m in monitors)
    y0 = min(m[1] for m in monitors)
    bw = max(m[0] + m[2] for m in monitors) - x0
    bh = max(m[1] + m[3] for m in monitors) - y0
    # Monitors as big as fits: at most max_width across, `height` tall with the stands
    room_k = (height - stand_h) / bh
    k = min(max_width / bw, room_k)
    # When the width is what limits the icon (side by side, three in a row),
    # stretch it upwards so each monitor's screen opening has the Screen
    # icon's shape. The bezels keep the Screen icon's thickness, so a small
    # monitor needs a little extra height to make up for them. Stacked and
    # 2x2 layouts, limited by the height, keep their real shape
    ky = k
    if max_width / bw < room_k:
        landscape = sorted((m for m in monitors if m[2] >= m[3]), key=lambda m: m[2] / m[3])
        typical = landscape[len(landscape) // 2] if landscape else monitors[0]
        ox, oy_, ow, oh = _OPENING
        side, top, bottom = ox * f, (oy_ - _FRAME[1]) * f, (_FRAME[1] + _FRAME[3] - oy_ - oh) * f
        drawn_w = typical[2] * k - GAP
        wanted_h = (drawn_w - 2 * side) * oh / ow + top + bottom
        ky = max(k, min((wanted_h + GAP) / typical[3], room_k))
    width = math.ceil(bw * k)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, math.ceil(width * scale), math.ceil(height * scale))
    surface.set_device_scale(scale, scale)
    cr = cairo.Context(surface)
    oy = (height - stand_h - bh * ky) / 2     # centred, stands included
    for m in monitors:
        x = (m[0] - x0) * k + GAP / 2
        y = oy + (m[1] - y0) * ky + GAP / 2
        w, h = m[2] * k - GAP, m[3] * ky - GAP
        _monitor(cr, _frame_art, x, y, w, h, f, color, scale)
        if not _has_below(m, monitors):        # stands only under the bottom row
            sw = min(_STAND[2] * f, w * 0.6)
            sh = sw * _STAND[3] / _STAND[2]
            _tile(cr, art, _STAND, (x + (w - sw) / 2, y + h, sw, sh), color)
    return surface
