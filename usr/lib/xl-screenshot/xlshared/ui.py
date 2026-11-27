"""Dialogs, icon lookup and image-format helpers used by both apps."""

import math
import os

from gi.repository import Gtk, GdkPixbuf

from .i18n import _

# share/icons next to our lib folder: the source tree's usr/share/icons when
# run from a checkout, /usr/share/icons once installed
ICONS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir, "share", "icons"
))

# Image formats we can save: file extension -> GdkPixbuf format name, and back
EXT_TO_FORMAT = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp",
                 ".bmp": "bmp", ".tif": "tiff", ".tiff": "tiff"}
FORMAT_TO_EXT = {"png": "png", "jpeg": "jpg", "webp": "webp", "bmp": "bmp", "tiff": "tif"}


def add_icon_search_path():
    """Let GTK find our own icons when running from the source folder."""
    theme = Gtk.IconTheme.get_default()
    if os.path.isdir(ICONS_DIR) and ICONS_DIR not in theme.get_search_path():
        theme.append_search_path(ICONS_DIR)


def themed_icon_name(preferred, fallback):
    """preferred if the icon theme has it, otherwise fallback."""
    return preferred if Gtk.IconTheme.get_default().has_icon(preferred) else fallback


def pixbuf_has_format(name):
    for fmt in GdkPixbuf.Pixbuf.get_formats():
        if fmt.get_name().lower() == name.lower():
            return True
    return False


def save_pixbuf(pixbuf, path, fmt, quality=90):
    """Save in the given GdkPixbuf format (quality 1-100 for JPEG and
    WebP). Raises on failure."""
    if fmt == "webp" and not pixbuf_has_format("webp"):
        raise RuntimeError(_("WebP support missing. Install 'webp-pixbuf-loader'."))
    if fmt in ("jpeg", "bmp") and pixbuf.get_has_alpha():
        # These formats have no transparency: put the image on white
        flat = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8,
                                    pixbuf.get_width(), pixbuf.get_height())
        flat.fill(0xffffffff)
        pixbuf.composite(flat, 0, 0, pixbuf.get_width(), pixbuf.get_height(),
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 255)
        pixbuf = flat
    if fmt in ("jpeg", "webp"):
        pixbuf.savev(path, fmt, ["quality"], [str(quality)])
    else:
        pixbuf.savev(path, fmt, [], [])


def show_error(parent, text, secondary):
    err = Gtk.MessageDialog(
        transient_for=parent, flags=0,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=text
    )
    err.format_secondary_text(secondary)
    err.run()
    err.destroy()


def confirm_overwrite(parent, path):
    dlg = Gtk.MessageDialog(
        transient_for=parent, flags=0,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=_("A file named “{name}” already exists. Do you want to replace it?").format(
            name=os.path.basename(path))
    )
    dlg.format_secondary_text(
        _("The file already exists in “{folder}”. Replacing it will overwrite its contents.").format(
            folder=os.path.dirname(path))
    )
    dlg.add_buttons(_("_Cancel"), Gtk.ResponseType.CANCEL,
                    _("_Replace"), Gtk.ResponseType.ACCEPT)
    dlg.set_default_response(Gtk.ResponseType.CANCEL)
    response = dlg.run()
    dlg.destroy()
    return response == Gtk.ResponseType.ACCEPT


def resolve_save_path(path, default_format):
    """Work out the final path and format from what the user typed.

    If they typed a known image extension, that decides the format.
    Otherwise the default format's extension is added.
    """
    ext = os.path.splitext(path)[1].lower()
    fmt = EXT_TO_FORMAT.get(ext)
    if fmt is None:
        fmt = default_format
        path += "." + FORMAT_TO_EXT[fmt]
    return path, fmt


# ---- The floating panel and selection box style, shared by xl-Screenshot's
# ---- Selection and xl-Annotate's Crop, so the two always look the same

PANEL_PAD = 8          # space between the panel's edge and its buttons
PANEL_SHADOW = 8       # how far the panel's soft shadow reaches
PANEL_GAP = 6          # space between the selection box and the panel
SELECTION_DIM = 0.35   # how much the area outside the box is darkened
SELECTION_HANDLE = 8   # half the size of the square handles


def theme_colors(widget):
    """(accent, panel background, panel border) from the widget's theme."""
    ctx = widget.get_style_context()

    def look(names, fallback):
        for name in names:
            found, c = ctx.lookup_color(name)
            if found:
                return (c.red, c.green, c.blue, c.alpha)
        return fallback

    accent = look(("theme_selected_bg_color", "selected_bg_color"), (0.2, 0.6, 1.0, 1.0))
    background = look(("theme_bg_color",), (0.96, 0.96, 0.95, 1.0))
    border = look(("borders",), (0, 0, 0, 0.25))
    return accent[:3] + (1.0,), background[:3], border[:3] + (0.8,)


def rubberband_colors(widget):
    """(tint, outline): the theme's "rubberband" colors, the see-through box
    you get when drag-selecting files. Cinnamon tints the screen with them
    when you pick a window or an area, so our Selection and Crop do too.
    Themes without one: the old grey dimming and the accent color."""
    path = Gtk.WidgetPath()
    path.append_type(Gtk.IconView)
    ctx = Gtk.StyleContext()
    ctx.set_path(path)
    ctx.set_screen(widget.get_screen())
    ctx.add_class("rubberband")
    bg = ctx.get_property("background-color", Gtk.StateFlags.NORMAL)
    border = ctx.get_property("border-top-color", Gtk.StateFlags.NORMAL)
    accent = theme_colors(widget)[0]
    if bg is None or bg.alpha < 0.02:
        return (0, 0, 0, SELECTION_DIM), accent
    outline = (border.red, border.green, border.blue, 1.0) if border is not None and border.alpha > 0.02 else accent
    return (bg.red, bg.green, bg.blue, bg.alpha), outline


def rounded_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw_panel(cr, x, y, w, h, background, border):
    """A rounded card in the theme's window color with a soft drop shadow,
    to put buttons on over a darkened picture."""
    radius = 8
    cr.save()
    cr.new_path()
    # Soft shadow: a few widening, fading copies, nudged down a little
    for spread in range(PANEL_SHADOW, 0, -1):
        rounded_rect(cr, x - spread, y - spread + 3, w + 2 * spread, h + 2 * spread, radius + spread)
        cr.set_source_rgba(0, 0, 0, 0.035)
        cr.fill()
    rounded_rect(cr, x + 0.5, y + 0.5, w - 1, h - 1, radius)
    cr.set_source_rgb(*background)
    cr.fill_preserve()
    cr.set_source_rgba(*border)
    cr.set_line_width(1)
    cr.stroke()
    cr.restore()


def place_panel(box, panel_w, panel_h, area, gap=PANEL_GAP):
    """Where a panel goes for a selection box: its right edge lined up with
    the box's, just below it; above it when there's no room below; inside its
    bottom edge when there's no room above either. Kept within area.
    box and area are (x, y, w, h); returns the panel's (x, y)."""
    bx, by, bw, bh = box
    ax, ay, aw, ah = area
    px = bx + bw - panel_w
    py = by + bh + gap
    if py + panel_h > ay + ah:
        py = by - panel_h - gap
    if py < ay:
        py = by + bh - panel_h - gap
    px = max(ax, min(px, ax + aw - panel_w))
    py = max(ay, min(py, ay + ah - panel_h))
    return px, py


def draw_selection_box(cr, x, y, w, h, accent, handles):
    """The selection outline in the theme's accent color, and its handles:
    white squares edged in the accent color. handles: centre points."""
    cr.save()
    cr.set_source_rgba(*accent)
    cr.set_line_width(1.5)
    cr.rectangle(x, y, w, h)
    cr.stroke()
    s = SELECTION_HANDLE
    for hx, hy in handles:
        cr.rectangle(hx - s, hy - s, 2 * s, 2 * s)
        cr.set_source_rgba(1, 1, 1, 1)
        cr.fill_preserve()
        cr.set_source_rgba(*accent)
        cr.stroke()
    cr.restore()
