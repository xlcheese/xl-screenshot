"""Making an X11 Window capture look like Cinnamon's: rounded top corners
and, if wanted, a drawn shadow.

On X11 we capture a rectangle of the screen, so a rounded window comes with
bits of the desktop in its corners, and its shadow (already blended into what
was behind it) can't be captured at all. So the corners are cut out
transparently at the theme's radius, and a shadow is drawn around it, in the
style of Mint-Y's. (Cinnamon's own screenshot service, where there is one,
gives the real thing instead.)
"""

import math

import cairo
from gi.repository import Gdk, Gtk

DEFAULT_RADIUS = 8      # Mint-Y's (and Adwaita's) window corners
SHADOW_REACH = 14       # how far the shadow spreads, in units
SHADOW_DROP = 3         # how far below the window it sits


def theme_corner_radius(kind="csd"):
    """How much the GTK3 theme rounds a window's top corners, in units.
    kind "csd": windows that draw their own title bar (Nemo, Text Editor...);
    "ssd": title bars Cinnamon draws for other apps, which also come from
    the GTK3 theme (window.ssd). Read from the live screen, so changes made
    with a theme tool, or in ~/.config/gtk-3.0/gtk.css, count too."""
    path = Gtk.WidgetPath()
    path.append_type(Gtk.Window)
    path.iter_set_object_name(-1, "window")
    path.iter_add_class(-1, kind)
    path.append_type(Gtk.Widget)
    path.iter_set_object_name(-1, "decoration")
    ctx = Gtk.StyleContext()
    ctx.set_path(path)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        ctx.set_screen(screen)
    try:
        radius = ctx.get_property("border-radius", Gtk.StateFlags.NORMAL)
    except (TypeError, ValueError):
        radius = None
    if not isinstance(radius, int):
        return None
    return max(0, min(radius, 24))


def corner_radius_for(window):
    """The top-corner radius (units) for a window from x11_windows: square
    when maximized or without a title bar, otherwise the GTK3 theme's."""
    if window.get("maximized") or not (window.get("csd") or window.get("framed")):
        return 0
    radius = None
    if not window.get("csd"):
        radius = theme_corner_radius("ssd")       # a title bar Cinnamon draws
    if radius is None:
        radius = theme_corner_radius("csd")
    return DEFAULT_RADIUS if radius is None else radius


def _top_rounded(cr, x, y, w, h, r, bottom=0):
    """A rectangle with its top corners rounded by r, and its bottom corners
    by `bottom` (square, unless given)."""
    cr.new_path()
    cr.move_to(x, y + h - bottom)
    cr.line_to(x, y + r)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.line_to(x + w - r, y)
    cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
    cr.line_to(x + w, y + h - bottom)
    if bottom:
        cr.arc(x + w - bottom, y + h - bottom, bottom, 0, 0.5 * math.pi)
        cr.arc(x + bottom, y + h - bottom, bottom, 0.5 * math.pi, math.pi)
    else:
        cr.line_to(x + w, y + h)
        cr.line_to(x, y + h)
    cr.close_path()


def finish_window(pixbuf, scale=1, shadow=False, rounded=True, radius=None):
    """The captured window with its top corners rounded (transparent outside)
    and, if shadow, a soft drop shadow around it. scale: device pixels per
    unit (2 on a HiDPI desktop). Returns a new pixbuf with transparency."""
    w, h = pixbuf.get_width(), pixbuf.get_height()
    if radius is None:
        radius = theme_corner_radius() or DEFAULT_RADIUS
    r = radius * scale if rounded else 0
    r = min(r, w / 2, h / 2)
    m = math.ceil((SHADOW_REACH + SHADOW_DROP) * scale) if shadow else 0
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w + 2 * m, h + 2 * m)
    cr = cairo.Context(out)
    if shadow:
        reach = SHADOW_REACH * scale
        drop = SHADOW_DROP * scale
        steps = 28
        # Many faint copies, each a little bigger: they add up to a soft
        # shadow, darkest at the window and fading smoothly to nothing (the
        # same idea as the Selection panel's shadow). The faintness grows
        # with distance squared, like a blur's falloff.
        for i in range(steps, 0, -1):
            t = i / steps
            spread = reach * t
            # Every corner rounds by as much as the copy has spread, the
            # square bottom ones too: a blurred corner fades like the sides
            _top_rounded(cr, m - spread, m - spread + drop, w + 2 * spread, h + 2 * spread,
                         r + spread, bottom=spread)
            cr.set_source_rgba(0, 0, 0, 0.034 * (1 - t) ** 2 + 0.005)
            cr.fill()
        # A hairline right round the window, as Mint-Y draws
        _top_rounded(cr, m - scale, m - scale, w + 2 * scale, h + 2 * scale, r + scale if r else 0)
        cr.set_source_rgba(0, 0, 0, 0.23)
        cr.fill()
    # The window itself, clipped to its rounded shape (this also clears the
    # shadow under it, so a see-through window doesn't look darker)
    cr.save()
    _top_rounded(cr, m, m, w, h, r)
    cr.clip()
    cr.set_operator(cairo.Operator.SOURCE)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, m, m)
    cr.paint()
    cr.restore()
    out.flush()
    return Gdk.pixbuf_get_from_surface(out, 0, 0, out.get_width(), out.get_height())
