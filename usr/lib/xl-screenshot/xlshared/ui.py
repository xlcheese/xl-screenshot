"""Dialogs, icon lookup and image-format helpers used by both apps."""

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


def save_pixbuf(pixbuf, path, fmt):
    """Save in the given GdkPixbuf format. Raises on failure."""
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
        pixbuf.savev(path, fmt, ["quality"], ["90"])
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
