"""Grabbing pixels from the screen: the whole desktop, a region, or a window."""

import subprocess

from gi.repository import Gdk
import cairo


def grab_screen():
    """Return a pixbuf of the whole desktop (all monitors), or None."""
    root = Gdk.get_default_root_window()
    return Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())


def get_pointer_position():
    """Pointer position in desktop (root window) coordinates, or None."""
    try:
        seat = Gdk.Display.get_default().get_default_seat()
        _screen, x, y = seat.get_pointer().get_position()
        return x, y
    except Exception:
        return None


def draw_cursor_on_pixbuf(pixbuf, origin_x, origin_y, pointer_pos):
    """Draw an arrow pointer onto pixbuf.

    origin_x/origin_y are the desktop coordinates of the pixbuf's top-left
    corner, so the pointer lands in the right place on cropped captures.
    """
    if pointer_pos is None:
        return pixbuf

    w, h = pixbuf.get_width(), pixbuf.get_height()
    cx = pointer_pos[0] - origin_x
    cy = pointer_pos[1] - origin_y

    # Pointer is completely outside this image: nothing to draw
    if cx < -12 or cy < -20 or cx >= w or cy >= h:
        return pixbuf

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()

    # Standard left-pointing arrow, tip at (cx, cy)
    points = [(0, 0), (0, 17), (4, 13), (7, 20), (9, 19), (6, 12), (12, 12)]
    cr.move_to(cx + points[0][0] + 0.5, cy + points[0][1] + 0.5)
    for px, py in points[1:]:
        cr.line_to(cx + px + 0.5, cy + py + 0.5)
    cr.close_path()

    cr.set_source_rgba(0, 0, 0, 1)
    cr.set_line_width(1.5)
    cr.set_line_join(cairo.LineJoin.MITER)
    cr.stroke_preserve()
    cr.set_source_rgba(1, 1, 1, 1)
    cr.fill()

    surface.flush()
    result = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)
    return result if result else pixbuf


def capture_region(x, y, w, h, include_pointer):
    """Grab the desktop and crop to (x, y, w, h).

    The rectangle is clipped to the desktop, so windows that hang off an
    edge are captured correctly. Returns a new pixbuf, or None on failure.
    """
    pointer_pos = get_pointer_position() if include_pointer else None

    full = grab_screen()
    if full is None:
        return None

    screen_w, screen_h = full.get_width(), full.get_height()
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(screen_w, x + w)
    y2 = min(screen_h, y + h)
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None

    region = full.new_subpixbuf(x1, y1, x2 - x1, y2 - y1).copy()
    if include_pointer:
        region = draw_cursor_on_pixbuf(region, x1, y1, pointer_pos)
    return region


def xprop_cardinals(window_id, prop):
    """Read a 4-value CARDINAL property (left, right, top, bottom) via xprop."""
    try:
        out = subprocess.check_output(
            ["xprop", "-id", window_id, prop],
            stderr=subprocess.DEVNULL, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    if "=" not in out:
        return None  # e.g. "_NET_FRAME_EXTENTS:  not found."
    try:
        values = [int(v) for v in out.split("=", 1)[1].split(",")]
    except ValueError:
        return None
    return values if len(values) == 4 else None


def get_window_geometry(window_id):
    """Return (x, y, w, h) of a client window in desktop coordinates."""
    out = subprocess.check_output(
        ["xwininfo", "-id", window_id], stderr=subprocess.DEVNULL, text=True
    )
    geo = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Absolute upper-left X:"):
            geo["x"] = int(line.split()[-1])
        elif line.startswith("Absolute upper-left Y:"):
            geo["y"] = int(line.split()[-1])
        elif line.startswith("Width:"):
            geo["w"] = int(line.split()[-1])
        elif line.startswith("Height:"):
            geo["h"] = int(line.split()[-1])
    if len(geo) != 4:
        raise RuntimeError("Could not parse xwininfo output")
    return geo["x"], geo["y"], geo["w"], geo["h"]


def window_capture_rect(window_id):
    """The area to capture for a window, including its titlebar and borders.

    Raises FileNotFoundError if xwininfo is missing, or another exception if
    the window can't be measured.
    """
    x, y, w, h = get_window_geometry(window_id)

    # GTK apps that draw their own titlebar (client-side decorations)
    # include an invisible shadow area in their window size.
    # _GTK_FRAME_EXTENTS tells us how much of that to trim off.
    gtk_ext = xprop_cardinals(window_id, "_GTK_FRAME_EXTENTS")
    if gtk_ext:
        left, right, top, bottom = gtk_ext
        x += left
        y += top
        w -= left + right
        h -= top + bottom

    # Add the window manager's titlebar and borders around the client,
    # so every window type is captured with its titlebar.
    # (Zero for client-side-decorated apps, which already include theirs.)
    frame = xprop_cardinals(window_id, "_NET_FRAME_EXTENTS")
    if frame:
        left, right, top, bottom = frame
        x -= left
        y -= top
        w += left + right
        h += top + bottom

    return x, y, w, h
