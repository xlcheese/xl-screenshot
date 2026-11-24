"""Shared set-up for the README screenshots: Mint-Y theme, fonts, helpers.

Run make-screenshots rather than these scripts on their own (see README.md here)."""
import os, sys, time, tempfile, subprocess
THEME = sys.argv[1] if len(sys.argv) > 1 else "Mint-Y"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.environ.get("XL_SHOTS_OUT") or os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
home = tempfile.mkdtemp()
os.environ["HOME"] = home
os.environ["GDK_SCALE"] = "2"
# Mint-Y comes with Linux Mint; elsewhere, MINT_THEMES_DIR can name a folder
# holding themes/Mint-Y, themes/Mint-Y-Dark and icons/Mint-Y
extra = os.environ.get("MINT_THEMES_DIR")
os.environ["XDG_DATA_DIRS"] = ((extra + ":") if extra else "") + "/usr/local/share:/usr/share"
os.makedirs(f"{home}/.config/gtk-3.0")
with open(f"{home}/.config/gtk-3.0/settings.ini", "w") as f:
    f.write(f"[Settings]\ngtk-theme-name={THEME}\ngtk-icon-theme-name=Mint-Y\n"
            "gtk-font-name=Ubuntu 10\ngtk-xft-antialias=1\ngtk-xft-hinting=1\n"
            "gtk-xft-hintstyle=hintslight\ngtk-xft-rgba=none\n"
            "gtk-decoration-layout=:minimize,maximize,close\n")
sys.path.insert(0, os.path.join(ROOT, "usr", "lib", "xl-screenshot"))
import gi
gi.require_version("Gtk", "3.0"); gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import cairo
DARK = "Dark" in THEME
SUFFIX = "dark" if DARK else "light"
SCALE = 2

def settle(t=0.6):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)

def grab(widget):
    """The window as a pixbuf, at device pixels."""
    w = widget.get_window()
    pb = Gdk.pixbuf_get_from_window(w, 0, 0, w.get_width(), w.get_height())
    return pb

def surface_from_pixbuf(pb):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
    cr = cairo.Context(s); Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0); cr.paint()
    return s

def rounded_top(cr, x, y, w, h, r):
    cr.new_path()
    cr.move_to(x, y + h); cr.line_to(x, y + r)
    cr.arc(x + r, y + r, r, 3.14159, 4.71239)
    cr.line_to(x + w - r, y)
    cr.arc(x + w - r, y + r, r, 4.71239, 6.28318)
    cr.line_to(x + w, y + h); cr.close_path()

def blur_alpha(surface, radius):
    """Box-blur a surface three times (close to a Gaussian) using numpy."""
    import numpy as np
    w, h = surface.get_width(), surface.get_height()
    a = np.ndarray((h, w, 4), np.uint8, surface.get_data()).astype(np.float32)
    k = max(1, int(radius))
    for _ in range(3):
        for axis in (0, 1):
            c = np.cumsum(np.pad(a, [(k + 1, k) if i == axis else (0, 0) for i in range(3)], mode="edge"), axis=axis)
            sl1 = [slice(None)] * 3; sl2 = [slice(None)] * 3
            sl1[axis] = slice(2 * k + 1, None); sl2[axis] = slice(None, -2 * k - 1)
            a = (c[tuple(sl1)] - c[tuple(sl2)]) / (2 * k + 1)
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    np.ndarray((h, w, 4), np.uint8, out.get_data())[:] = np.clip(a, 0, 255).astype(np.uint8)
    out.mark_dirty()
    return out

def decorate(pb, radius=8, margin=40):
    """Round the window's top corners and add Mint-Y's drop shadow
    (what Muffin's compositor would show). Returns a cairo surface."""
    r, m = radius * SCALE, margin * SCALE
    w, h = pb.get_width(), pb.get_height()
    W, H = w + 2 * m, h + 2 * m
    shadow = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(shadow)
    # a wide soft shadow, a little below the window...
    rounded_top(cr, m, m + 10 * SCALE, w, h, r)
    cr.set_source_rgba(0, 0, 0, 0.30 if not DARK else 0.45); cr.fill()
    shadow = blur_alpha(shadow, 9 * SCALE)
    # ...and a tighter one close in, as Mint-Y's own (0 3px 9px)
    close = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cc = cairo.Context(close)
    rounded_top(cc, m, m + 3 * SCALE, w, h, r)
    cc.set_source_rgba(0, 0, 0, 0.30 if not DARK else 0.4); cc.fill()
    close = blur_alpha(close, 3 * SCALE)
    cr = cairo.Context(shadow); cr.set_source_surface(close, 0, 0); cr.paint()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(out)
    cr.set_source_surface(shadow, 0, 0); cr.paint()
    # a hairline round the window, as Mint-Y's "0 0 0 1px rgba(0,0,0,0.23)"
    rounded_top(cr, m - SCALE, m - SCALE, w + 2 * SCALE, h + 2 * SCALE, r + SCALE)
    cr.set_source_rgba(0, 0, 0, 0.23); cr.fill()
    rounded_top(cr, m, m, w, h, r); cr.clip()
    Gdk.cairo_set_source_pixbuf(cr, pb, m, m); cr.paint()
    return out

def save(surface, name):
    path = f"{OUT}/{name}-{SUFFIX}.png"
    surface.write_to_png(path)
    return path

def start_wm():
    subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)

def wallpaper(w, h):
    """A soft abstract backdrop in Mint greens (made here, no outside artwork)."""
    import math
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    g = cairo.LinearGradient(0, 0, w, h)
    if DARK:
        g.add_color_stop_rgb(0, 0.07, 0.16, 0.15); g.add_color_stop_rgb(1, 0.05, 0.08, 0.11)
        blobs = [(0.15, 0.2, 0.55, (0.20, 0.55, 0.33, 0.55)), (0.85, 0.85, 0.6, (0.08, 0.38, 0.45, 0.5)),
                 (0.7, 0.1, 0.4, (0.30, 0.60, 0.30, 0.25))]
    else:
        g.add_color_stop_rgb(0, 0.80, 0.91, 0.84); g.add_color_stop_rgb(1, 0.70, 0.84, 0.86)
        blobs = [(0.15, 0.2, 0.55, (0.55, 0.82, 0.55, 0.6)), (0.85, 0.85, 0.6, (0.45, 0.75, 0.80, 0.55)),
                 (0.7, 0.1, 0.4, (0.95, 0.97, 0.90, 0.6))]
    cr.set_source(g); cr.paint()
    for fx, fy, fr, (r, gg, b, a) in blobs:
        rad = cairo.RadialGradient(fx * w, fy * h, 0, fx * w, fy * h, fr * max(w, h))
        rad.add_color_stop_rgba(0, r, gg, b, a); rad.add_color_stop_rgba(1, r, gg, b, 0)
        cr.set_source(rad); cr.paint()
    return s

def pixbuf_from_surface(s):
    return Gdk.pixbuf_get_from_surface(s, 0, 0, s.get_width(), s.get_height())

def widget_box(widget, toplevel, offset=(0, 0)):
    """A widget's rectangle in the toplevel's device pixels, plus an offset."""
    x, y = widget.translate_coordinates(toplevel, 0, 0)
    a = widget.get_allocation()
    return (x * SCALE + offset[0], y * SCALE + offset[1], a.width * SCALE, a.height * SCALE)
