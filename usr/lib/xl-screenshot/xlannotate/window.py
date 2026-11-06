"""The xl-Annotate window: tool bar, colour sidebar and the drawing canvas.

It works two ways:
  * on its own (xl-annotate, or "Annotate Image…" in Nemo): Open, Save and
    Save As in the tool bar, and it closes like any other app;
  * opened from xl-Screenshot (embedded=True): a Done button in the header
    bar instead, which hands the image and its still-editable marks back.

Layout:
  header bar   title, menu (and Done when embedded)
  tool bar     Open Save SaveAs Copy | Undo Redo | tools | Crop | line style, shadow | size
  sidebar      line/fill pair, swap, None + colours, Solid / Sheer, font
  canvas       the image, with zoom buttons in the corner
"""

import os
import time

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango

from xlshared.ui import (EXT_TO_FORMAT, themed_icon_name, pixbuf_has_format,
                         save_pixbuf, show_error, confirm_overwrite, resolve_save_path)
from xlshared.i18n import _
from .config import (APP_ID, APP_NAME, APP_VERSION, APP_FALLBACK_ICON, APP_WEBSITE,
                     APP_AUTHORS, APP_COPYRIGHT, APP_CREDIT, load_config, save_config)
from .canvas import AnnotateCanvas, TOOLS
from .shapes import (COLORS, DASHES, SEE_THROUGH_ALPHA, SIZE_MIN, SIZE_MAX, DEFAULT_FONT,
                     TextShape)

# (tool, our icon, stock fallback icon, tooltip)
TOOL_BUTTONS = (
    ("select", "xl-annotate-select-symbolic", "edit-select-symbolic",
     _("Select: click a mark to move it (Shift: straight across or down), reshape it with its "
     "handles, change its colours and style, or press Delete. Double-click text to edit it.")),
    ("arrow", "xl-annotate-arrow-symbolic", "go-next-symbolic",
     _("Arrow (hold Shift for 45° angles)")),
    ("line", "xl-annotate-line-symbolic", "list-remove-symbolic",
     _("Line (hold Shift for 45° angles)")),
    ("freehand", "xl-annotate-freehand-symbolic", "document-edit-symbolic",
     _("Freehand: draw with the mouse. Rough lines, arrows, circles and boxes are tidied "
     "into clean shapes (you can keep your drawing, or turn this off in the menu).")),
    ("rectangle", "xl-annotate-rectangle-symbolic", "media-playback-stop-symbolic",
     _("Rectangle (hold Shift for a square)")),
    ("ellipse", "xl-annotate-ellipse-symbolic", "media-record-symbolic",
     _("Ellipse (hold Shift for a circle)")),
    ("highlight", "xl-annotate-highlight-symbolic", "format-text-highlight-symbolic",
     _("Highlighter: drag a box over text to mark it")),
    ("text", "xl-annotate-text-symbolic", "insert-text-symbolic",
     _("Text: click where it goes. A fill colour puts a box behind it.")),
    ("step", "xl-annotate-step-symbolic", "zoom-original-symbolic",
     _("Numbered steps: each click adds the next number")),
    ("pixelate", "xl-annotate-pixelate-symbolic", "view-grid-symbolic",
     _("Pixelate: drag a box over anything private (passwords, emails, names)")),
    ("loupe", "xl-annotate-loupe-symbolic", "zoom-in-symbolic",
     _("Loupe: click to magnify a spot. Drag the green handle round the ring to zoom more "
     "or less, and the white one to change its size.")),
    ("crop", "xl-annotate-crop-symbolic", "image-crop-symbolic",
     _("Crop: drag the area to keep")),
)

# What the size slider means, per remembered size
SIZE_TOOLTIPS = {
    "line": _("Line thickness"),
    "text": _("Text size"),
    "step": _("Size of the numbered circles"),
    "pixelate": _("Block size (use bigger blocks to hide text)"),
    "loupe": _("Size of the lens"),
}

DASH_NAMES = {"solid": _("Solid line"), "dashed": _("Dashed line"), "dotted": _("Dotted line")}


def _radio_group(items, make_child, on_toggled, vertical=False):
    """A row of joined toggle buttons where only one can be on.
    items: list of (value, tooltip). Returns (box, {value: button})."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL)
    box.get_style_context().add_class("linked")
    buttons = {}
    first = None
    for value, tooltip in items:
        btn = Gtk.RadioButton.new_from_widget(first)
        first = first or btn
        btn.set_mode(False)            # look like a button, not a radio dot
        btn.set_tooltip_text(tooltip)
        btn.add(make_child(value))
        btn.connect("toggled", on_toggled, value)
        box.pack_start(btn, False, False, 0)
        buttons[value] = btn
    return box, buttons


def _paint_checks(cr, x, y, w, h, square=4):
    """Light/dark grey checkerboard: the usual sign for "transparent"."""
    cr.save()
    cr.rectangle(x, y, w, h)
    cr.clip()
    cr.set_source_rgb(0.85, 0.85, 0.85)
    cr.paint()
    cr.set_source_rgb(0.6, 0.6, 0.6)
    for row in range(int(h // square) + 1):
        for col in range(int(w // square) + 1):
            if (row + col) % 2:
                cr.rectangle(x + col * square, y + row * square, square, square)
    cr.fill()
    cr.restore()


def _paint_color(cr, x, y, w, h, color):
    """A colour sample: None is all checkerboard; a see-through colour is
    split diagonally, solid in the top-left half and over the checkerboard in
    the bottom-right half; a solid colour is just the colour."""
    if color is None:
        _paint_checks(cr, x, y, w, h)
        return
    if color[3] >= 0.99:
        cr.rectangle(x, y, w, h)
        cr.set_source_rgba(*color)
        cr.fill()
        return
    _paint_checks(cr, x, y, w, h)
    cr.rectangle(x, y, w, h)
    cr.set_source_rgba(*color)
    cr.fill()
    cr.move_to(x, y)
    cr.line_to(x + w, y)
    cr.line_to(x, y + h)
    cr.close_path()
    cr.set_source_rgb(*color[:3])
    cr.fill()


def _flatten_toolbar(toolbar):
    """Tool bar buttons are flat: no frame until the pointer is over them (as
    in Xed). Flat buttons don't need joining into strips, so the groups are
    unlinked (joined flat buttons lose an edge when hovered); the dividers
    between groups keep them apart. Picture-only buttons get the theme's
    usual size for icon buttons."""
    for group in toolbar.get_children():
        buttons = group.get_children() if isinstance(group, Gtk.Box) else [group]
        if isinstance(group, Gtk.Box):
            group.get_style_context().remove_class("linked")
        for btn in buttons:
            if not isinstance(btn, Gtk.Button):
                continue
            btn.set_relief(Gtk.ReliefStyle.NONE)
            if not isinstance(btn.get_child(), Gtk.Label):
                btn.get_style_context().add_class("image-button")


class LineFillWell(Gtk.DrawingArea):
    """The line/fill pair at the top of the sidebar, as in GIMP: the line
    colour is always the square in front (top left), the fill colour the
    square behind (bottom right). Click one to choose which the colour
    buttons set; the chosen one is drawn a little bigger."""

    SIZE = 54
    SQ = 28          # square size
    GROW = 6         # how much bigger the chosen square is

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.set_size_request(self.SIZE, self.SIZE)
        self.set_halign(Gtk.Align.CENTER)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.set_tooltip_text(_("Line colour (front) and fill colour (back).\n"
                                "Click one, then pick a colour below."))

    def _rect(self, which, chosen):
        """(x, y, w, h). The line square sits in the top-left corner, the fill
        square in the bottom-right; a chosen square grows around its centre."""
        half = self.SQ / 2 + (self.GROW / 2 if chosen else 0)
        c = 3 + self.SQ / 2 if which == "line" else self.SIZE - 3 - self.SQ / 2
        return (c - half, c - half, 2 * half, 2 * half)

    def on_draw(self, widget, cr):
        stroke, fill, _uses_fill = self.window.shown_colors()
        target = self.window.color_target
        for which in ("fill", "line"):           # line always in front
            x, y, w, h = self._rect(which, which == target)
            _paint_color(cr, x, y, w, h, stroke if which == "line" else fill)
            # A thin neutral edge, so white, None and theme-coloured
            # squares always show
            cr.set_line_width(1)
            cr.set_source_rgba(0.25, 0.25, 0.25, 0.7)
            cr.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
            cr.stroke()
        return False

    def on_press(self, widget, event):
        if event.button != 1:
            return False
        target = self.window.color_target
        # The line square is in front, so it wins where they overlap
        for which in ("line", "fill"):
            x, y, w, h = self._rect(which, which == target)
            if x <= event.x <= x + w and y <= event.y <= y + h:
                self.window.set_color_target(which)
                break
        return True


class AnnotateWindow(Gtk.ApplicationWindow):
    def __init__(self, application=None, embedded=False, on_done=None):
        super().__init__(application=application)
        self.embedded = embedded
        self.on_done = on_done
        self.path = None              # file the image came from (standalone)
        self.doc_name = _("Untitled")
        self.modified = False
        self._syncing = False         # True while controls are updated to match a selection
        self.color_target = "line"    # which colour the colour buttons set: "line" or "fill"

        self.config = load_config()
        self.set_icon_name(themed_icon_name(APP_ID, APP_FALLBACK_ICON))

        self.canvas = AnnotateCanvas()
        self.canvas.connect("changed", self.on_canvas_changed)
        self.canvas.connect("selection-changed", lambda c: self._sync_controls())
        self.canvas.connect("crop-changed", lambda c: self._update_state())
        self.canvas.connect("zoom-changed", lambda c: self._update_zoom_label())

        # ---- Header bar: just the title and the menu ----
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        self.set_titlebar(hb)
        if embedded:
            self.done_btn = Gtk.Button(label=_("Done"))
            self.done_btn.get_style_context().add_class("suggested-action")
            self.done_btn.set_tooltip_text(_("Use the annotated image in xl-Screenshot"))
            self.done_btn.connect("clicked", lambda b: self.done())
            hb.pack_start(self.done_btn)
        menu = Gtk.Menu()
        self.tidy_item = Gtk.CheckMenuItem(label=_("Tidy Up Freehand Drawings"))
        self.tidy_item.set_tooltip_text(_("Turn rough freehand lines, arrows, circles and boxes "
                                        "into clean shapes"))
        self.tidy_item.set_active(self.config["tidy_shapes"])
        self.canvas.tidy = self.config["tidy_shapes"]
        self.tidy_item.connect("toggled", self.on_tidy_toggled)
        menu.append(self.tidy_item)
        menu.append(Gtk.SeparatorMenuItem())
        about_item = Gtk.MenuItem(label=_("About"))
        about_item.connect("activate", lambda i: self.show_about())
        menu.append(about_item)
        menu.show_all()
        menu_button = Gtk.MenuButton()
        menu_button.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.MENU))
        menu_button.set_popup(menu)
        hb.pack_end(menu_button)

        # ---- Tool bar ----
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for side in ("start", "end", "top", "bottom"):
            getattr(toolbar, f"set_margin_{side}")(6)

        def icon_button(icon, fallback, tooltip, handler):
            btn = Gtk.Button()
            btn.set_image(Gtk.Image.new_from_icon_name(
                themed_icon_name(icon, fallback), Gtk.IconSize.BUTTON))
            btn.set_tooltip_text(tooltip)
            btn.connect("clicked", handler)
            return btn

        def linked(*widgets):
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            box.get_style_context().add_class("linked")
            for w in widgets:
                box.pack_start(w, False, False, 0)
            return box

        file_buttons = []
        if not embedded:
            open_btn = icon_button("document-open-symbolic", "document-open",
                                   _("Open an Image (Ctrl+O)"), lambda b: self.open_dialog())
            self.save_btn = icon_button("document-save-symbolic", "document-save",
                                        _("Save (Ctrl+S)"), lambda b: self.save())
            self.save_as_btn = icon_button("document-save-as-symbolic", "document-save-symbolic",
                                           _("Save As… (Shift+Ctrl+S)"), lambda b: self.save_as())
            file_buttons = [open_btn, self.save_btn, self.save_as_btn]
        self.copy_btn = icon_button("edit-copy-symbolic", "edit-copy", _("Copy to Clipboard (Ctrl+C)"),
                                    lambda b: self.copy_to_clipboard())
        self.file_buttons = [b for b in file_buttons[1:]] + [self.copy_btn]   # need an image

        self.undo_btn = icon_button("edit-undo-symbolic", "edit-undo", _("Undo (Ctrl+Z)"),
                                    lambda b: self.canvas.undo())
        self.redo_btn = icon_button("edit-redo-symbolic", "edit-redo", _("Redo (Shift+Ctrl+Z)"),
                                    lambda b: self.canvas.redo())

        def tool_icon(tool):
            _t, icon, fallback, _tip = next(t for t in TOOL_BUTTONS if t[0] == tool)
            return Gtk.Image.new_from_icon_name(themed_icon_name(icon, fallback), Gtk.IconSize.BUTTON)

        tools_box, self.tool_buttons = _radio_group(
            [(t[0], t[3]) for t in TOOL_BUTTONS], tool_icon, self.on_tool_toggled)
        # Crop works on the image itself, so it sits apart from the drawing
        # tools (it's still one of the same set: only one tool is on)
        crop_btn = self.tool_buttons["crop"]
        tools_box.remove(crop_btn)

        dash_box, self.dash_buttons = _radio_group(
            [(d, DASH_NAMES[d]) for d in DASHES], self._make_dash_sample, self.on_dash_toggled)
        self.shadow_btn = Gtk.ToggleButton()
        self.shadow_btn.add(self._make_shadow_sample())
        self.shadow_btn.set_tooltip_text(_("Drop shadow"))
        self.shadow_btn.connect("toggled", self.on_shadow_toggled)
        dash_box.pack_start(self.shadow_btn, False, False, 0)

        self.size_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, SIZE_MIN, SIZE_MAX, 1)
        self.size_scale.set_digits(0)
        self.size_scale.set_draw_value(True)
        self.size_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.size_scale.set_size_request(130, -1)
        self.size_scale.connect("value-changed", self.on_size_changed)

        groups = []
        if file_buttons:
            self.file_group = linked(*file_buttons, self.copy_btn)
        else:
            self.file_group = linked(self.copy_btn)
        groups.append(self.file_group)
        # The slider sits in its own box: the tool bar switches whole groups
        # on and off, and the slider has its own on/off per tool
        size_box = Gtk.Box()
        size_box.pack_start(self.size_scale, False, False, 0)
        groups += [linked(self.undo_btn, self.redo_btn), tools_box, linked(crop_btn),
                   dash_box, size_box]
        for i, group in enumerate(groups):
            if i:
                toolbar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL),
                                   False, False, 0)
            toolbar.pack_start(group, False, False, 0)
        self.toolbar = toolbar
        _flatten_toolbar(toolbar)

        # ---- Sidebar: colours ----
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for side in ("start", "end", "top", "bottom"):
            getattr(sidebar, f"set_margin_{side}")(8)
        self.well = LineFillWell(self)
        sidebar.pack_start(self.well, False, False, 0)

        swap_btn = Gtk.Button(label="⇄")
        swap_btn.set_tooltip_text(_("Swap the line and fill colours"))
        swap_btn.set_relief(Gtk.ReliefStyle.NONE)
        swap_btn.set_halign(Gtk.Align.CENTER)
        swap_btn.connect("clicked", lambda b: self.swap_colors())
        sidebar.pack_start(swap_btn, False, False, 0)

        color_names = ["None"] + [name for name, _rgb in COLORS]
        grid = Gtk.Grid(row_spacing=4, column_spacing=4)
        grid.set_halign(Gtk.Align.CENTER)
        self.color_buttons = {}
        first = None
        for i, name in enumerate(color_names):
            btn = Gtk.RadioButton.new_from_widget(first)
            first = first or btn
            btn.set_mode(False)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_tooltip_text(_("No colour") if name == "None" else _(name))
            btn.add(self._make_swatch(name))
            btn.connect("toggled", self.on_color_toggled, name)
            grid.attach(btn, i % 2, i // 2, 1, 1)
            self.color_buttons[name] = btn
        # Not shown: switched on when the colour isn't one of ours, so no
        # swatch looks chosen
        self._no_match_btn = Gtk.RadioButton.new_from_widget(first)
        sidebar.pack_start(grid, False, False, 0)

        opacity_box, self.opacity_buttons = _radio_group(
            [("solid", _("Solid colour")),
             # xgettext:no-python-format
             ("see-through", _("Semi-transparent ({percent}% opacity)").format(
                 percent=int(SEE_THROUGH_ALPHA * 100)))],
            # Translators: "Sheer" is a see-through colour (the short label beside "Solid")
            lambda v: Gtk.Label(label=_("Solid") if v == "solid" else _("Sheer")),
            self.on_opacity_toggled, vertical=True)
        sidebar.pack_start(opacity_box, False, False, 0)

        # Font (shown for text)
        self.font_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        font_lbl = Gtk.Label(label=_("Font"))
        font_lbl.get_style_context().add_class("dim-label")
        font_lbl.set_halign(Gtk.Align.START)
        # "Aa" drawn in the chosen font: a preview that never changes width
        self.font_button = Gtk.Button()
        self.font_sample = Gtk.Label()
        self.font_button.add(self.font_sample)
        self.font_button.connect("clicked", lambda b: self.choose_font())
        self.font_box.pack_start(font_lbl, False, False, 0)
        self.font_box.pack_start(self.font_button, False, False, 0)
        self.font_box.set_no_show_all(True)
        font_lbl.show()
        self.font_button.show()
        self.font_sample.show()     # inside a no-show-all box, so show it by hand
        sidebar.pack_start(self.font_box, False, False, 0)
        self.sidebar = sidebar

        # ---- Image area: scrolls when zoomed in; hint when there's no image ----
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.add(self.canvas)
        self.canvas.set_scroller(self.scroller)
        overlay = Gtk.Overlay()
        overlay.add(self.scroller)
        self.empty_label = Gtk.Label()
        self.empty_label.set_markup(
            "<big>" + GLib.markup_escape_text(_("Open an image to annotate")) + "</big>\n\n"
            + GLib.markup_escape_text(_("Use the Open button (Ctrl+O), or paste an image with Ctrl+V.")))
        self.empty_label.set_justify(Gtk.Justification.CENTER)
        self.empty_label.get_style_context().add_class("dim-label")
        self.empty_label.set_no_show_all(True)
        overlay.add_overlay(self.empty_label)
        overlay.set_overlay_pass_through(self.empty_label, True)

        # Zoom buttons in the bottom-right corner
        self.zoom_label_btn = Gtk.Button(label="100%")
        self.zoom_label_btn.set_tooltip_text(_("Show at actual size (Ctrl+1)"))
        self.zoom_label_btn.connect("clicked", lambda b: self.canvas.zoom_to(1.0))
        zoom_out = icon_button("zoom-out-symbolic", "zoom-out", _("Zoom out (Ctrl+−, or Ctrl+scroll)"),
                               lambda b: self.canvas.zoom_out())
        zoom_in = icon_button("zoom-in-symbolic", "zoom-in", _("Zoom in (Ctrl++, or Ctrl+scroll)"),
                              lambda b: self.canvas.zoom_in())
        zoom_fit = icon_button("zoom-fit-best-symbolic", "zoom-fit-best", _("Fit the window (Ctrl+0)"),
                               lambda b: self.canvas.zoom_fit())
        self.zoom_box = linked(zoom_out, self.zoom_label_btn, zoom_in, zoom_fit)
        self.zoom_box.set_halign(Gtk.Align.END)
        self.zoom_box.set_valign(Gtk.Align.END)
        self.zoom_box.set_margin_end(14)
        self.zoom_box.set_margin_bottom(14)
        self.zoom_box.set_no_show_all(True)
        for child in self.zoom_box.get_children():
            child.show_all()
        overlay.add_overlay(self.zoom_box)

        # ---- Bar along the bottom while cropping ----
        self.crop_bar = Gtk.ActionBar()
        crop_hint = Gtk.Label(label=_("Drag the area to keep. Adjust it with the handles, "
                                    "or drag it to move it."))
        crop_hint.get_style_context().add_class("dim-label")
        self.crop_bar.pack_start(crop_hint)
        self.crop_apply_btn = Gtk.Button(label=_("Crop"))
        self.crop_apply_btn.get_style_context().add_class("suggested-action")
        self.crop_apply_btn.set_tooltip_text(_("Keep only the chosen area (Enter)"))
        self.crop_apply_btn.connect("clicked", lambda b: self.apply_crop())
        crop_cancel_btn = Gtk.Button(label=_("Cancel"))
        crop_cancel_btn.set_tooltip_text(_("Leave Crop without changing the image (Esc)"))
        crop_cancel_btn.connect("clicked", lambda b: self.leave_crop())
        self.crop_bar.pack_end(self.crop_apply_btn)
        self.crop_bar.pack_end(crop_cancel_btn)
        # The bar stays hidden until Crop is chosen, but what's inside it must
        # be shown now: show_all() skips the inside of a no-show-all widget
        for child in (crop_hint, self.crop_apply_btn, crop_cancel_btn):
            child.show()
        self.crop_bar.set_no_show_all(True)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.pack_start(sidebar, False, False, 0)
        body.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        body.pack_start(overlay, True, True, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(toolbar, False, False, 0)
        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
        vbox.pack_start(body, True, True, 0)
        vbox.pack_start(self.crop_bar, False, False, 0)
        self.add(vbox)

        # ---- Restore last choices (but never start in Crop) ----
        cfg = self.config
        self.canvas.stroke = tuple(cfg["stroke"]) if cfg["stroke"] is not None else None
        self.canvas.fill = tuple(cfg["fill"]) if cfg["fill"] is not None else None
        self.canvas.dash = cfg["dash"] if cfg["dash"] in DASHES else "solid"
        self.canvas.shadow = bool(cfg["shadow"])
        self.canvas.font = cfg["font"] or DEFAULT_FONT
        self.canvas.sizes.update(cfg["sizes"])
        tool = cfg["tool"] if cfg["tool"] in TOOLS and cfg["tool"] != "crop" else "arrow"
        self._syncing = True
        self.tool_buttons[tool].set_active(True)
        self._syncing = False
        self.canvas.set_tool(tool)

        self.connect("delete-event", self.on_delete_event)
        self.connect("key-press-event", self.on_key_press)

        self.set_default_size(1000, 650)
        hb.show_all()
        vbox.show_all()
        self._sync_controls()
        self._update_state()

    # ---- Small drawings for the controls ----

    def _make_swatch(self, name):
        rgb = dict(COLORS).get(name)
        area = Gtk.DrawingArea()
        area.set_size_request(20, 20)

        def draw(widget, cr):
            w, h = widget.get_allocated_width(), widget.get_allocated_height()
            r = min(w, h) / 2 - 1
            cr.arc(w / 2, h / 2, r, 0, 6.2832)
            if rgb is None:
                # Checkerboard: no colour (transparent)
                cr.save()
                cr.clip_preserve()
                _paint_checks(cr, 0, 0, w, h, square=4)
                cr.restore()
                cr.set_source_rgba(0.5, 0.5, 0.5, 0.8)
                cr.set_line_width(1)
                cr.stroke()
                return
            cr.set_source_rgb(*rgb)
            cr.fill_preserve()
            # A thin edge so white and black show on any theme
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.8)
            cr.set_line_width(1)
            cr.stroke()
        area.connect("draw", draw)
        return area

    def _fg(self, widget):
        c = widget.get_style_context().get_color(widget.get_state_flags())
        return (c.red, c.green, c.blue, c.alpha)

    def _make_dash_sample(self, dash):
        area = Gtk.DrawingArea()
        area.set_size_request(22, 18)

        def draw(widget, cr):
            w, h = widget.get_allocated_width(), widget.get_allocated_height()
            cr.set_source_rgba(*self._fg(widget))
            cr.set_line_width(2)
            if dash == "dashed":
                cr.set_dash([5, 3])
            elif dash == "dotted":
                cr.set_line_cap(1)        # round
                cr.set_dash([0, 4])
            cr.move_to(2, h / 2)
            cr.line_to(w - 2, h / 2)
            cr.stroke()
        area.connect("draw", draw)
        return area

    def _make_shadow_sample(self):
        area = Gtk.DrawingArea()
        area.set_size_request(20, 18)

        def draw(widget, cr):
            fg = self._fg(widget)
            cr.set_source_rgba(fg[0], fg[1], fg[2], 0.35)
            cr.rectangle(7, 6, 11, 10)
            cr.fill()
            cr.set_source_rgba(*fg)
            cr.set_line_width(1.5)
            cr.rectangle(3.75, 2.75, 11, 10)
            cr.stroke()
        area.connect("draw", draw)
        return area

    # ---- Keeping the controls in step with the tool / selection ----

    def _style_source(self):
        """The selected mark (Select tool), else None: then the controls show
        the style for new marks."""
        if self.canvas.tool == "select":
            return self.canvas.selected
        return None

    def shown_colors(self):
        """(line, fill, uses_fill) as the sidebar should show them."""
        shape = self._style_source()
        cls = self.canvas.style_target_class()
        uses_fill = cls is None or cls.USES_FILL
        if shape is not None:
            return shape.stroke, shape.fill, uses_fill
        return self.canvas.stroke, self.canvas.fill, uses_fill

    def _sync_controls(self):
        """Show the style of the selected mark, or the style for new marks,
        and enable only the controls that matter for it."""
        canvas = self.canvas
        shape = self._style_source()
        cls = canvas.style_target_class()
        self._syncing = True
        try:
            stroke, fill, _uses_fill = self.shown_colors()
            color = stroke if self.color_target == "line" else fill
            name = "None"
            if color is not None:
                for cname, rgb in COLORS:
                    if all(abs(a - b) < 0.01 for a, b in zip(rgb, color[:3])):
                        name = cname
                        break
                else:
                    name = None
            (self.color_buttons[name] if name is not None else self._no_match_btn).set_active(True)
            see_through = color is not None and color[3] < 0.99
            self.opacity_buttons["see-through" if see_through else "solid"].set_active(True)
            for btn in self.opacity_buttons.values():
                btn.set_sensitive(color is not None)

            dash = shape.dash if shape is not None else canvas.dash
            shadow = shape.shadow if shape is not None else canvas.shadow
            self.dash_buttons[dash if dash in self.dash_buttons else "solid"].set_active(True)
            self.shadow_btn.set_active(bool(shadow))
            for btn in self.dash_buttons.values():
                btn.set_sensitive(cls is None or cls.USES_DASH)
            self.shadow_btn.set_sensitive(cls is None or cls.USES_SHADOW)

            group = canvas.size_group()
            has_size = group is not None and (cls is None or cls.USES_SIZE)
            self.size_scale.set_sensitive(has_size)
            if has_size:
                self.size_scale.set_value(canvas.current_size())
                self.size_scale.set_tooltip_text(SIZE_TOOLTIPS.get(group, _("Size")))
            else:
                self.size_scale.set_tooltip_text(_("Size (not used by this tool)"))

            is_text = cls is TextShape
            self.font_box.set_visible(is_text)
            font = shape.font if (shape is not None and is_text) else canvas.font
            self._show_font(font or DEFAULT_FONT)
        finally:
            self._syncing = False
        self.well.queue_draw()

    def set_color_target(self, which):
        self.color_target = which
        self._sync_controls()

    # ---- Control handlers ----

    def on_tool_toggled(self, button, tool):
        if not button.get_active():
            return
        self.canvas.set_tool(tool)
        if tool != "crop" and not self._syncing:
            self.config["tool"] = tool
            save_config(self.config)
        self._sync_controls()
        self._update_state()

    def _remember_style(self):
        c = self.canvas
        self.config.update({
            "stroke": list(c.stroke) if c.stroke is not None else None,
            "fill": list(c.fill) if c.fill is not None else None,
            "dash": c.dash, "shadow": c.shadow, "font": c.font, "sizes": dict(c.sizes),
        })
        save_config(self.config)

    def _apply(self, merge=None, **changes):
        self.canvas.set_style(merge=merge, **changes)
        self._remember_style()
        self.well.queue_draw()

    def on_color_toggled(self, button, name):
        if not button.get_active() or self._syncing:
            return
        if name == "None":
            color = None
        else:
            alpha = SEE_THROUGH_ALPHA if self.opacity_buttons["see-through"].get_active() else 1.0
            color = tuple(dict(COLORS)[name]) + (alpha,)
        self._apply(**{"stroke" if self.color_target == "line" else "fill": color})
        self._sync_controls()

    def on_opacity_toggled(self, button, value):
        if not button.get_active() or self._syncing:
            return
        stroke, fill, _u = self.shown_colors()
        color = stroke if self.color_target == "line" else fill
        if color is None:
            return
        alpha = SEE_THROUGH_ALPHA if value == "see-through" else 1.0
        self._apply(**{"stroke" if self.color_target == "line" else "fill": color[:3] + (alpha,)})

    def swap_colors(self):
        stroke, fill, _u = self.shown_colors()
        self._apply(stroke=fill, fill=stroke)
        self._sync_controls()

    def on_dash_toggled(self, button, dash):
        if button.get_active() and not self._syncing:
            self._apply(dash=dash)

    def on_shadow_toggled(self, button):
        if not self._syncing:
            self._apply(shadow=button.get_active())

    def on_size_changed(self, scale):
        if not self._syncing:
            self._apply(merge="size", size=int(round(scale.get_value())))

    def _show_font(self, font):
        desc = Pango.FontDescription.from_string(font)
        desc.set_size(14 * Pango.SCALE)
        self.font_sample.set_markup(
            f'<span font_desc="{GLib.markup_escape_text(desc.to_string())}">Aa</span>')
        self.font_button.set_tooltip_text(_("Font: {font}").format(font=font))
        self._font_name = font

    def choose_font(self):
        dialog = Gtk.FontChooserDialog(title=_("Text Font"), transient_for=self, modal=True)
        dialog.set_level(Gtk.FontChooserLevel.FAMILY | Gtk.FontChooserLevel.STYLE)
        dialog.set_font(f"{self._font_name} 14")
        if dialog.run() == Gtk.ResponseType.OK and dialog.get_font():
            self.set_font(dialog.get_font())
        dialog.destroy()

    def set_font(self, font):
        """Use this font (family and style) for text; the size comes from
        the slider, so any size in the name is ignored."""
        desc = Pango.FontDescription.from_string(font or DEFAULT_FONT)
        desc.unset_fields(Pango.FontMask.SIZE)
        name = desc.to_string() or DEFAULT_FONT
        self._apply(font=name)
        self._show_font(name)

    def on_tidy_toggled(self, item):
        self.canvas.tidy = item.get_active()
        self.config["tidy_shapes"] = item.get_active()
        save_config(self.config)

    def apply_crop(self):
        if self.canvas.apply_crop():
            self.leave_crop()

    def leave_crop(self):
        """Back to Select (which also clears any crop area)."""
        self.tool_buttons["select"].set_active(True)

    def on_canvas_changed(self, canvas):
        self.modified = True
        self._update_state()
        self._sync_controls()

    def _update_zoom_label(self):
        self.zoom_label_btn.set_label(f"{round(self.canvas.view_scale() * 100)}%")

    def _update_state(self):
        has_image = self.canvas.has_image()
        # Everything needs an image except Open (Save, Save As and Copy are
        # switched one by one below)
        for child in self.toolbar.get_children():
            if child is not self.file_group:
                child.set_sensitive(has_image)
        self.sidebar.set_sensitive(has_image)
        self.undo_btn.set_sensitive(self.canvas.can_undo())
        self.redo_btn.set_sensitive(self.canvas.can_redo())
        for btn in self.file_buttons:
            btn.set_sensitive(has_image)
        self.crop_bar.set_visible(has_image and self.canvas.tool == "crop")
        self.crop_apply_btn.set_sensitive(self.canvas.crop is not None)
        self.zoom_box.set_visible(has_image)
        if self.embedded:
            self.done_btn.set_sensitive(has_image)
        else:
            self.empty_label.set_visible(not has_image)
        star = "*" if self.modified else ""
        # Just the image name (the app name only while there's no image)
        self.set_title(f"{star}{self.doc_name}" if has_image else APP_NAME)
        self._update_zoom_label()

    # ---- Loading ----

    def load_pixbuf(self, pixbuf, path=None, shapes=None, name=None):
        """Show an image to annotate. shapes: marks to keep editing."""
        self.canvas.set_image(pixbuf, shapes)
        self.path = path
        self.doc_name = name or (os.path.basename(path) if path else _("Untitled"))
        self.modified = False
        self._fit_window_to_image(pixbuf)
        self._update_state()
        self._sync_controls()

    def open_file(self, path):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            # Photos from phones and cameras are often stored sideways
            pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
        except GLib.Error as e:
            show_error(self, _("Could not open image"), f"{path}\n\n{e.message}")
            return False
        self.load_pixbuf(pixbuf, path=os.path.abspath(path))
        self.config["last_open_dir"] = os.path.dirname(os.path.abspath(path))
        save_config(self.config)
        return True

    def _fit_window_to_image(self, pixbuf):
        """Size the window to show the image 1:1 if it fits on screen,
        otherwise as large as comfortably fits."""
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea() if monitor else None
        max_w = int(area.width * 0.9) if area else 1200
        max_h = int(area.height * 0.9) if area else 800
        want_w = pixbuf.get_width() + 140       # sidebar and margins
        want_h = pixbuf.get_height() + 130      # tool bar and header bar
        w = max(900, min(want_w, max_w))
        h = max(520, min(want_h, max_h))
        if self.get_realized():
            self.resize(w, h)
        else:
            self.set_default_size(w, h)

    def open_dialog(self):
        if not self.confirm_discard():
            return
        dialog = Gtk.FileChooserDialog(title=_("Open Image"), parent=self,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(_("_Cancel"), Gtk.ResponseType.CANCEL, _("_Open"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        images = Gtk.FileFilter()
        images.set_name(_("Images"))
        images.add_pixbuf_formats()
        dialog.add_filter(images)
        folder = self.config["last_open_dir"]
        if folder and os.path.isdir(folder):
            dialog.set_current_folder(folder)
        while dialog.run() == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            if filename and self.open_file(filename):
                break
        dialog.destroy()

    def paste(self):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        pixbuf = clipboard.wait_for_image()
        if pixbuf is None:
            return False
        if not self.confirm_discard():
            return False
        self.load_pixbuf(pixbuf, name=_("Pasted Image"))
        return True

    # ---- Saving ----

    def _write(self, path, fmt):
        try:
            save_pixbuf(self.canvas.render_flat(), path, fmt)
        except Exception as e:
            show_error(self, _("Could not save image"), str(e))
            return False
        print(f"File saved to: {path}")
        return True

    def save(self):
        """Save over the opened file (marks are drawn into it).
        Images with no file yet, or in a format we can't write, go to Save As."""
        if not self.canvas.has_image():
            return False
        self.canvas.finish_text_edit()
        fmt = EXT_TO_FORMAT.get(os.path.splitext(self.path or "")[1].lower())
        if not self.path or fmt is None or (fmt == "webp" and not pixbuf_has_format("webp")):
            return self.save_as()
        if not self._write(self.path, fmt):
            return False
        self.modified = False
        self._update_state()
        return True

    def save_as(self):
        if not self.canvas.has_image():
            return False
        self.canvas.finish_text_edit()
        dialog = Gtk.FileChooserDialog(title=_("Save Annotated Image As"), parent=self,
                                       action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons(_("_Cancel"), Gtk.ResponseType.CANCEL, _("_Save"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        dialog.set_do_overwrite_confirmation(False)   # we check after the extension is settled

        if self.path:
            folder = os.path.dirname(self.path)
            stem, ext = os.path.splitext(os.path.basename(self.path))
            if ext.lower() not in EXT_TO_FORMAT:
                ext = ".png"
            # Translators: the suggested file name for a copy; {name} is the original's name
            name = _("{name}-annotated").format(name=stem) + ext
        else:
            folder = self.config["last_save_dir"]
            # Translators: the start of a new annotated image's file name (date and time follow)
            name = _("Annotated") + time.strftime("-%Y-%m-%d_%H-%M-%S.png")
        if folder and os.path.isdir(folder):
            dialog.set_current_folder(folder)
        dialog.set_current_name(name)

        images = Gtk.FileFilter()
        images.set_name(_("Images"))
        for mime in ("image/png", "image/jpeg", "image/webp", "image/bmp", "image/tiff"):
            images.add_mime_type(mime)
        dialog.add_filter(images)

        saved = False
        while dialog.run() == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            if not filename:
                continue
            path, fmt = resolve_save_path(filename, "png")
            if os.path.exists(path) and not confirm_overwrite(dialog, path):
                continue
            if not self._write(path, fmt):
                continue
            self.path = path
            self.doc_name = os.path.basename(path)
            self.modified = False
            self.config["last_save_dir"] = os.path.dirname(path)
            save_config(self.config)
            saved = True
            break
        dialog.destroy()
        self._update_state()
        return saved

    def copy_to_clipboard(self):
        if not self.canvas.has_image():
            return
        self.canvas.finish_text_edit()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(self.canvas.render_flat())
        clipboard.store()
        print("Copied to clipboard.")

    # ---- Done (opened from xl-Screenshot) ----

    def done(self):
        self.canvas.finish_text_edit()
        if self.on_done and self.canvas.has_image():
            self.on_done(self.canvas.base, self.canvas.get_shapes(), self.canvas.render_flat())
        self.modified = False
        self.destroy()

    # ---- Closing ----

    def ask_unsaved(self):
        """Ask what to do with unsaved changes.
        Returns "save", "discard" or "cancel". (Tests replace this.)"""
        if self.embedded:
            text = _("Keep your annotations?")
            secondary = _("Keep updates the screenshot. Discard throws these changes away.")
            buttons = (_("_Discard"), Gtk.ResponseType.REJECT, _("_Cancel"), Gtk.ResponseType.CANCEL,
                       _("_Keep"), Gtk.ResponseType.ACCEPT)
        else:
            text = _("Save changes to “{name}”?").format(name=self.doc_name)
            secondary = _("If you don't save, your annotations will be lost.")
            buttons = (_("_Don't Save"), Gtk.ResponseType.REJECT, _("_Cancel"), Gtk.ResponseType.CANCEL,
                       _("_Save"), Gtk.ResponseType.ACCEPT)
        dlg = Gtk.MessageDialog(transient_for=self, flags=0,
                                message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.NONE, text=text)
        dlg.format_secondary_text(secondary)
        dlg.add_buttons(*buttons)
        dlg.set_default_response(Gtk.ResponseType.ACCEPT)
        response = dlg.run()
        dlg.destroy()
        return {Gtk.ResponseType.ACCEPT: "save",
                Gtk.ResponseType.REJECT: "discard"}.get(response, "cancel")

    def confirm_discard(self):
        """True if it's fine to replace or close the current image."""
        self.canvas.finish_text_edit()
        if not self.modified:
            return True
        answer = self.ask_unsaved()
        if answer == "discard":
            return True
        if answer == "save":
            if self.embedded:
                self.done()
                return False          # done() already closed the window
            return self.save()
        return False

    def on_delete_event(self, widget, event):
        # Returning True keeps the window open
        return not self.confirm_discard()

    # ---- Keyboard ----

    def on_key_press(self, widget, event):
        # Let text boxes have their keys (typing, Delete, Ctrl+C in the text...)
        if isinstance(self.get_focus(), (Gtk.Entry, Gtk.TextView)):
            return False
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        key = Gdk.keyval_to_lower(event.keyval)

        if ctrl and key == Gdk.KEY_z:
            self.canvas.redo() if shift else self.canvas.undo()
        elif ctrl and key == Gdk.KEY_y:
            self.canvas.redo()
        elif ctrl and key == Gdk.KEY_c:
            self.copy_to_clipboard()
        elif ctrl and key in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.canvas.zoom_in()
        elif ctrl and key in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.canvas.zoom_out()
        elif ctrl and key in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self.canvas.zoom_fit()
        elif ctrl and key in (Gdk.KEY_1, Gdk.KEY_KP_1):
            self.canvas.zoom_to(1.0)
        elif ctrl and not self.embedded and key == Gdk.KEY_s:
            self.save_as() if shift else self.save()
        elif ctrl and not self.embedded and key == Gdk.KEY_o:
            self.open_dialog()
        elif ctrl and not self.embedded and key == Gdk.KEY_v:
            self.paste()
        elif not ctrl and key in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            if not self.canvas.delete_selected():
                return False
        elif not ctrl and key == Gdk.KEY_Escape:
            if not self.canvas.cancel() and self.canvas.tool == "crop":
                self.leave_crop()
        elif not ctrl and key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self.canvas.tool == "crop":
            self.apply_crop()
        else:
            return False
        return True

    # ---- About ----

    def show_about(self):
        dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        dialog.set_program_name(APP_NAME)
        dialog.set_version(APP_VERSION)
        dialog.set_comments(_("Simple, light markup for images and screenshots: "
                            "arrows, boxes and text that stay editable until you save."))
        dialog.set_logo_icon_name(themed_icon_name(APP_ID, APP_FALLBACK_ICON))
        if APP_WEBSITE:
            dialog.set_website(APP_WEBSITE)
        dialog.set_authors(APP_AUTHORS)
        dialog.set_copyright(f"{APP_COPYRIGHT}\n{APP_CREDIT}")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.run()
        dialog.destroy()
