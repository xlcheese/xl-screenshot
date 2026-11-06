"""The drawing area: shows the image with its marks and handles the tools."""

from gi.repository import Gtk, Gdk, GLib, GObject
from xlshared.i18n import _
import cairo

from .shapes import (ArrowShape, LineShape, BoxShape, RectShape, EllipseShape, HighlightShape,
                     PixelateShape, LoupeShape, TextShape, StepShape, FreehandShape, DEFAULT_FONT,
                     snap_angle, snap_square, draw_shapes, render_flat)
from .tidy import recognize

# How close (in screen pixels) a click must be to a mark or handle to pick it
HIT_TOLERANCE_PX = 6
HANDLE_HIT_PX = 8
HANDLE_SIZE_PX = 8
MARGIN_PX = 12

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.05, 8.0, 1.25

TOOLS = ("select", "arrow", "line", "freehand", "rectangle", "ellipse", "highlight", "text",
         "step", "pixelate", "loupe", "crop")

# Marks drawn by dragging out a box, and by dragging a line
BOX_TOOLS = {"rectangle": RectShape, "ellipse": EllipseShape,
             "highlight": HighlightShape, "pixelate": PixelateShape}
LINE_TOOLS = {"arrow": ArrowShape, "line": LineShape}

# Which size each tool remembers: lines and shapes share one, the others
# each have their own (text size is nothing like line thickness)
SIZE_GROUPS = {"arrow": "line", "line": "line", "freehand": "line",
               "rectangle": "line", "ellipse": "line",
               "text": "text", "step": "step", "pixelate": "pixelate", "loupe": "loupe"}
SHAPE_SIZE_GROUPS = {ArrowShape: "line", LineShape: "line", FreehandShape: "line", RectShape: "line",
                     EllipseShape: "line", TextShape: "text", StepShape: "step",
                     PixelateShape: "pixelate", LoupeShape: "loupe"}
DEFAULT_SIZES = {"line": 6, "text": 6, "step": 6, "pixelate": 6, "loupe": 6}

# The mark class for a tool, so the window can ask what a tool uses
TOOL_CLASSES = {"arrow": ArrowShape, "line": LineShape, "freehand": FreehandShape,
                "rectangle": RectShape,
                "ellipse": EllipseShape, "highlight": HighlightShape, "text": TextShape,
                "step": StepShape, "pixelate": PixelateShape, "loupe": LoupeShape}

# What tidy-up says it turned a drawing into (whole sentences, so they translate well)
TIDY_MESSAGES = {"line": _("Tidied into a straight line"), "arrow": _("Tidied into an arrow"),
                 "ellipse": _("Tidied into an ellipse"), "rectangle": _("Tidied into a rectangle")}

HANDLE_CURSORS = {
    "nw": "nw-resize", "n": "n-resize", "ne": "ne-resize", "e": "e-resize",
    "se": "se-resize", "s": "s-resize", "sw": "sw-resize", "w": "w-resize",
    "start": "crosshair", "end": "crosshair", "size": "se-resize", "zoom": "pointer",
}


def _shift(event):
    return bool(getattr(event, "state", 0) & Gdk.ModifierType.SHIFT_MASK)


class AnnotateCanvas(Gtk.DrawingArea):
    """Holds the image and the list of marks on top of it.

    Every change goes through _push_undo() first, so Undo and Redo always
    work (including Crop, which changes the image itself), and "changed"
    is emitted afterwards.
    """

    __gsignals__ = {
        # The marks or image changed (something to save)
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # A different mark (or none) is selected
        "selection-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # A crop area was drawn or cleared
        "crop-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # The view's zoom changed
        "zoom-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.base = None            # the image, as a GdkPixbuf
        self.shapes = []            # marks, bottom to top
        self.selected = None        # the selected mark (Select tool), or None
        self.crop = None            # the area to keep (Crop tool), a BoxShape, or None
        self.tool = "arrow"

        # Style for new marks (and the selected one, when changed)
        self.stroke = (0.88, 0.11, 0.14, 1.0)
        self.fill = None
        self.dash = "solid"
        self.shadow = False
        self.font = DEFAULT_FONT
        self.sizes = dict(DEFAULT_SIZES)

        # View: None = fit the window (never enlarged), or a zoom factor
        self.zoom = None
        self.hadj = self.vadj = None    # set by set_scroller()
        self._pending_anchor = None

        self._undo = []             # earlier (image, marks) pairs
        self._last_merge = None     # (what, mark) of the last change that can merge
        self._redo = []
        self._draft = None          # mark being drawn right now
        self._draft_start = None
        self._drag = None           # what the mouse is dragging (see on_button_press)
        self._cursor_name = None
        self._text_popover = None
        self._finish_text = None
        self.tidy = True            # turn rough freehand shapes into clean ones
        self._tidy_popover = None

        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.SCROLL_MASK |
                        Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("button-release-event", self.on_button_release)
        self.connect("scroll-event", self.on_scroll)
        self.connect("size-allocate", self.on_size_allocate)

    # ---- Image and marks ----

    def set_image(self, pixbuf, shapes=None):
        """Show a new image (and optionally marks to continue editing)."""
        self.base = pixbuf
        self.shapes = [s.copy() for s in (shapes or [])]
        self.selected = None
        self.crop = None
        self._undo.clear()
        self._redo.clear()
        self._draft = None
        self._drag = None
        self.zoom = None
        self._update_size_request()
        self.queue_draw()
        self.emit("selection-changed")
        self.emit("crop-changed")
        self.emit("zoom-changed")

    def has_image(self):
        return self.base is not None

    def render_flat(self):
        """The image with all marks drawn in, full size."""
        return render_flat(self.base, self.shapes)

    def get_shapes(self):
        return [s.copy() for s in self.shapes]

    # ---- Undo / Redo ----

    def _snapshot(self):
        # The image itself is never changed in place, so keeping a
        # reference is enough
        return (self.base, [s.copy() for s in self.shapes])

    def _push_undo(self, snapshot=None):
        self._undo.append(snapshot if snapshot is not None else self._snapshot())
        self._redo.clear()
        self._last_merge = None

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self):
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        self.base, self.shapes = self._undo.pop()
        self._after_history_change()

    def redo(self):
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        self.base, self.shapes = self._redo.pop()
        self._after_history_change()

    def _after_history_change(self):
        self.selected = None
        self.crop = None
        self._update_size_request()
        self.queue_draw()
        self.emit("selection-changed")
        self.emit("crop-changed")
        self.emit("changed")

    # ---- Style ----

    def size_group(self):
        """Which remembered size the slider shows right now."""
        if self.tool == "select" and self.selected is not None:
            return SHAPE_SIZE_GROUPS.get(type(self.selected))
        return SIZE_GROUPS.get(self.tool)

    def current_size(self):
        group = self.size_group()
        if self.tool == "select" and self.selected is not None and group:
            return self.selected.size
        return self.sizes.get(group, 6)

    def style_for_new(self, tool):
        return {"stroke": self.stroke, "fill": self.fill, "dash": self.dash,
                "shadow": self.shadow, "font": self.font,
                "size": self.sizes.get(SIZE_GROUPS.get(tool), 6)}

    def style_target_class(self):
        """The kind of mark the style controls affect right now (the selected
        mark's, or the current tool's), or None."""
        if self.tool == "select":
            return type(self.selected) if self.selected is not None else None
        return TOOL_CLASSES.get(self.tool)

    def set_style(self, merge=None, **changes):
        """Change style settings for new marks, and for the selected mark
        (only the settings that mark uses). Keys: stroke, fill, size, dash,
        shadow, font. merge: a name for changes that come in a stream (the
        size slider being dragged), so they make one Undo step, not dozens."""
        for key in ("stroke", "fill", "dash", "shadow", "font"):
            if key in changes:
                value = changes[key]
                setattr(self, key, tuple(value) if isinstance(value, (list, tuple)) else value)
        if "size" in changes:
            group = self.size_group()
            if group:
                self.sizes[group] = changes["size"]

        shape = self.selected
        if shape is None or self.tool != "select":
            return
        uses = {"stroke": shape.USES_LINE, "fill": shape.USES_FILL, "dash": shape.USES_DASH,
                "shadow": shape.USES_SHADOW, "size": shape.USES_SIZE,
                "font": isinstance(shape, TextShape)}
        updates = {}
        for key, value in changes.items():
            if uses.get(key):
                value = tuple(value) if isinstance(value, (list, tuple)) else value
                if getattr(shape, key) != value:
                    updates[key] = value
        if updates:
            if not (merge and self._last_merge == (merge, id(shape)) and self._undo):
                self._push_undo()
                if merge:
                    self._last_merge = (merge, id(shape))
            for key, value in updates.items():
                setattr(shape, key, value)
            self.queue_draw()
            self.emit("changed")

    # ---- Editing ----

    def set_tool(self, tool):
        self.close_tidy_offer()
        if tool != "crop" and self.crop is not None:
            self.crop = None
            self.emit("crop-changed")
        self.tool = tool
        self._draft = None
        if tool != "select" and self.selected is not None:
            self.select(None)
        self.queue_draw()
        self._set_cursor(self._default_cursor())

    def select(self, shape):
        if shape is not self.selected:
            self.selected = shape
            self.queue_draw()
            self.emit("selection-changed")

    def delete_selected(self):
        if self.selected is None:
            return False
        self._push_undo()
        self.shapes.remove(self.selected)
        self.selected = None
        self.queue_draw()
        self.emit("selection-changed")
        self.emit("changed")
        return True

    def cancel(self):
        """Esc: stop drawing, clear the crop area, or let go of the selection.
        Returns False if there was nothing to cancel."""
        if self._draft is not None:
            self._draft = None
            self.queue_draw()
        elif self.crop is not None:
            self.crop = None
            self.queue_draw()
            self.emit("crop-changed")
        elif self.selected is not None:
            self.select(None)
        else:
            return False
        return True

    def add_shape(self, shape):
        self._push_undo()
        self.shapes.append(shape)
        self.queue_draw()
        self.emit("changed")

    def set_text(self, shape, text):
        """Change a text mark's words; empty text removes it."""
        if text == shape.text:
            return
        self._push_undo()
        if text:
            shape.text = text
        else:
            self.shapes.remove(shape)
            if self.selected is shape:
                self.selected = None
                self.emit("selection-changed")
        self.queue_draw()
        self.emit("changed")

    # ---- Crop ----

    def _clamp_to_image(self, ix, iy):
        return (max(0.0, min(ix, self.base.get_width())),
                max(0.0, min(iy, self.base.get_height())))

    def apply_crop(self):
        """Keep only the crop area. Marks move with the image; Undo
        brings back the whole image."""
        if self.crop is None or self.base is None:
            return False
        x0, y0 = (int(round(v)) for v in self._clamp_to_image(self.crop.x, self.crop.y))
        x1, y1 = (int(round(v)) for v in self._clamp_to_image(self.crop.x + self.crop.w,
                                                              self.crop.y + self.crop.h))
        if x1 - x0 < 1 or y1 - y0 < 1:
            return False
        self._push_undo()
        self.base = self.base.new_subpixbuf(x0, y0, x1 - x0, y1 - y0).copy()
        for shape in self.shapes:
            shape.move_by(-x0, -y0)
        self.crop = None
        self.selected = None
        self._update_size_request()
        self.queue_draw()
        self.emit("selection-changed")
        self.emit("crop-changed")
        self.emit("changed")
        return True

    # ---- View zoom ----

    def set_scroller(self, scrolled):
        """The scrolled window the canvas sits in (for zooming in on a point)."""
        self.hadj = scrolled.get_hadjustment()
        self.vadj = scrolled.get_vadjustment()

    def view_scale(self):
        return self._transform()[0]

    def _update_size_request(self):
        if self.base is None or self.zoom is None:
            self.set_size_request(-1, -1)      # fit whatever space there is
        else:
            self.set_size_request(int(self.base.get_width() * self.zoom) + 2 * MARGIN_PX,
                                  int(self.base.get_height() * self.zoom) + 2 * MARGIN_PX)

    def zoom_fit(self):
        self.zoom = None
        self._pending_anchor = None
        self._update_size_request()
        self.queue_draw()
        self.emit("zoom-changed")

    def zoom_to(self, zoom, anchor=None):
        """Zoom the view. anchor: a point (in canvas coordinates) that should
        stay under the pointer; the middle of the view if not given."""
        if self.base is None:
            return
        zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
        if self.hadj is not None:
            if anchor is None:
                anchor = (self.hadj.get_value() + self.hadj.get_page_size() / 2,
                          self.vadj.get_value() + self.vadj.get_page_size() / 2)
            ix, iy = self.to_image(*anchor)
            self._pending_anchor = (ix, iy, anchor[0] - self.hadj.get_value(),
                                    anchor[1] - self.vadj.get_value())
        self.zoom = zoom
        self._update_size_request()
        self.queue_draw()
        self.emit("zoom-changed")

    def zoom_in(self, anchor=None):
        self.zoom_to(self.view_scale() * ZOOM_STEP, anchor)

    def zoom_out(self, anchor=None):
        self.zoom_to(self.view_scale() / ZOOM_STEP, anchor)

    def on_size_allocate(self, widget, alloc):
        # When fitting, the scale follows the window size
        if self.zoom is None and self.base is not None:
            self.emit("zoom-changed")
        # After zooming, scroll so the anchor point is where it was
        if self._pending_anchor is not None and self.hadj is not None:
            ix, iy, view_x, view_y = self._pending_anchor
            self._pending_anchor = None
            scale, ox, oy = self._transform()
            self.hadj.set_value(ix * scale + ox - view_x)
            self.vadj.set_value(iy * scale + oy - view_y)

    def on_scroll(self, widget, event):
        """Ctrl + mouse wheel zooms around the pointer; the plain wheel scrolls."""
        if not (event.state & Gdk.ModifierType.CONTROL_MASK) or self.base is None:
            return False
        direction = event.direction
        if direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = event.get_scroll_deltas()
            if dy == 0:
                return True
            direction = Gdk.ScrollDirection.UP if dy < 0 else Gdk.ScrollDirection.DOWN
        if direction == Gdk.ScrollDirection.UP:
            self.zoom_in((event.x, event.y))
        elif direction == Gdk.ScrollDirection.DOWN:
            self.zoom_out((event.x, event.y))
        return True

    # ---- Image <-> screen coordinates ----

    def _transform(self):
        """(scale, offset_x, offset_y). Fitting: shrunk to fit if needed
        (never enlarged) and centred. Zoomed: at that scale, centred if it's
        smaller than the view."""
        if not self.base:
            return 1.0, 0.0, 0.0
        aw, ah = self.get_allocated_width(), self.get_allocated_height()
        iw, ih = self.base.get_width(), self.base.get_height()
        if self.zoom is None:
            scale = min(1.0, (aw - 2 * MARGIN_PX) / iw, (ah - 2 * MARGIN_PX) / ih)
            scale = max(scale, 0.01)
        else:
            scale = self.zoom
        ox = round(max(MARGIN_PX if self.zoom else 0, (aw - iw * scale) / 2))
        oy = round(max(MARGIN_PX if self.zoom else 0, (ah - ih * scale) / 2))
        return scale, ox, oy

    def to_image(self, wx, wy):
        scale, ox, oy = self._transform()
        return (wx - ox) / scale, (wy - oy) / scale

    def to_widget(self, ix, iy):
        scale, ox, oy = self._transform()
        return ix * scale + ox, iy * scale + oy

    def shape_at(self, ix, iy):
        """Top-most mark under an image point, or None."""
        tolerance = HIT_TOLERANCE_PX / self._transform()[0]
        for shape in reversed(self.shapes):
            if shape.contains(ix, iy, tolerance):
                return shape
        return None

    def _active_handles(self):
        """(owner, {name: (ix, iy)}) for the handles showing right now."""
        if self.tool == "crop" and self.crop is not None:
            return self.crop, self.crop.handles()
        if self.tool == "select" and self.selected is not None:
            return self.selected, self.selected.handles()
        return None, {}

    def handle_at(self, wx, wy):
        """Name of the handle under a screen point, or None. Shape-changing
        (green) handles win when two overlap."""
        owner, handles = self._active_handles()
        special = owner.special_handles() if owner is not None else set()
        for name in sorted(handles, key=lambda n: n not in special):
            sx, sy = self.to_widget(*handles[name])
            if abs(sx - wx) <= HANDLE_HIT_PX and abs(sy - wy) <= HANDLE_HIT_PX:
                return name
        return None

    # ---- Drawing ----

    def on_draw(self, widget, cr):
        if not self.base:
            return False
        scale, ox, oy = self._transform()
        iw, ih = self.base.get_width(), self.base.get_height()

        cr.save()
        cr.translate(ox, oy)
        cr.scale(scale, scale)
        cr.rectangle(0, 0, iw, ih)
        cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, self.base, 0, 0)
        cr.get_source().set_filter(cairo.Filter.GOOD if scale < 1 else cairo.Filter.NEAREST
                                   if scale >= 2 else cairo.Filter.GOOD)
        cr.paint()
        draw_shapes(cr, self.shapes, self.base, extra=self._draft)
        cr.restore()

        # Everything below is in screen pixels, so it looks the same at any zoom
        if self.tool == "crop" and self.crop is not None:
            self._draw_crop(cr, ox, oy, iw * scale, ih * scale)
        if self.tool == "select" and self.selected is not None:
            bx, by, bw, bh = self.selected.bounds()
            x1, y1 = self.to_widget(bx, by)
            x2, y2 = self.to_widget(bx + bw, by + bh)
            cr.set_line_width(1)
            for color, offset in (((1, 1, 1), 0), ((0.2, 0.2, 0.2), 4)):
                cr.set_source_rgb(*color)
                cr.set_dash([4, 4], offset)
                cr.rectangle(round(x1) - 3.5, round(y1) - 3.5,
                             round(x2 - x1) + 7, round(y2 - y1) + 7)
                cr.stroke()
            cr.set_dash([])
        self._draw_handles(cr)
        return False

    def _draw_crop(self, cr, ox, oy, shown_w, shown_h):
        x1, y1 = self.to_widget(self.crop.x, self.crop.y)
        x2, y2 = self.to_widget(self.crop.x + self.crop.w, self.crop.y + self.crop.h)
        # Darken what will be cut away
        cr.save()
        cr.set_fill_rule(cairo.FillRule.EVEN_ODD)
        cr.rectangle(ox, oy, shown_w, shown_h)
        cr.rectangle(x1, y1, x2 - x1, y2 - y1)
        cr.set_source_rgba(0, 0, 0, 0.55)
        cr.fill()
        cr.restore()
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(1)
        cr.rectangle(round(x1) + 0.5, round(y1) + 0.5, round(x2 - x1) - 1, round(y2 - y1) - 1)
        cr.stroke()

    def _draw_handles(self, cr):
        owner, handles = self._active_handles()
        special = owner.special_handles() if owner is not None else set()
        half = HANDLE_SIZE_PX / 2
        for name, (hx, hy) in handles.items():
            sx, sy = self.to_widget(hx, hy)
            if name in special:
                # Green and round: changes the shape itself (like Preview)
                cr.arc(sx, sy, half + 1, 0, 6.2832)
                cr.set_source_rgb(0.20, 0.72, 0.30)
            else:
                cr.rectangle(round(sx - half) + 0.5, round(sy - half) + 0.5,
                             HANDLE_SIZE_PX - 1, HANDLE_SIZE_PX - 1)
                cr.set_source_rgb(1, 1, 1)
            cr.fill_preserve()
            cr.set_source_rgb(0.2, 0.2, 0.2)
            cr.set_line_width(1)
            cr.stroke()

    # ---- Mouse ----

    def _default_cursor(self):
        return {"select": "default", "text": "text", "step": "copy",
                "loupe": "zoom-in"}.get(self.tool, "crosshair")

    def _set_cursor(self, name):
        window = self.get_window()
        if not window or name == self._cursor_name:
            return
        self._cursor_name = name
        window.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), name))

    def do_realize(self):
        Gtk.DrawingArea.do_realize(self)
        self._cursor_name = None
        self._set_cursor(self._default_cursor())

    def on_button_press(self, widget, event):
        self.close_tidy_offer()
        self.grab_focus()
        if not self.base or event.button != 1:
            return False
        ix, iy = self.to_image(event.x, event.y)

        if self.tool == "select":
            handle = self.handle_at(event.x, event.y)
            if handle:
                self._drag = {"kind": "handle", "name": handle, "start": self.selected.copy(),
                              "snapshot": self._snapshot()}
                return True
            shape = self.shape_at(ix, iy)
            self.select(shape)
            if shape is None:
                return True
            if event.type == Gdk.EventType._2BUTTON_PRESS and isinstance(shape, TextShape):
                self._drag = None
                self.edit_text(shape)
                return True
            self._drag = {"kind": "move", "origin": (ix, iy), "applied": (0.0, 0.0),
                          "moved": False, "snapshot": self._snapshot()}
            return True

        if self.tool == "crop":
            handle = self.handle_at(event.x, event.y)
            if handle:
                self._drag = {"kind": "crop-handle", "name": handle, "start": self.crop.copy()}
            elif self.crop is not None and self.crop.contains(ix, iy, 0):
                self._drag = {"kind": "crop-move", "last": (ix, iy)}
            else:
                sx, sy = self._clamp_to_image(ix, iy)
                self.crop = BoxShape(sx, sy, 0, 0)
                self._drag = {"kind": "crop-new", "start": (sx, sy)}
                self.emit("crop-changed")
            self.queue_draw()
            return True

        style = self.style_for_new(self.tool)
        if self.tool == "freehand":
            self._draft = FreehandShape([(ix, iy)], **style)
        elif self.tool in LINE_TOOLS:
            self._draft = LINE_TOOLS[self.tool](ix, iy, ix, iy, **style)
        elif self.tool in BOX_TOOLS:
            self._draft = BOX_TOOLS[self.tool](ix, iy, 0, 0, **style)
            self._draft_start = (ix, iy)
        elif self.tool == "step":
            self.add_shape(StepShape(ix, iy, **style))
        elif self.tool == "loupe":
            self.add_shape(LoupeShape(ix, iy, **style))
        elif self.tool == "text":
            # Clicking an existing text edits it; anywhere else starts a new one
            shape = self.shape_at(ix, iy)
            if isinstance(shape, TextShape):
                self.edit_text(shape)
            else:
                self.edit_text(None, ix, iy)
        return True

    def on_motion(self, widget, event):
        if not self.base:
            return False
        ix, iy = self.to_image(event.x, event.y)
        shift = _shift(event)

        if self._draft is not None:
            if isinstance(self._draft, FreehandShape):
                self._draft.add_point(ix, iy)
            elif isinstance(self._draft, LineShape):
                if shift:
                    ix, iy = snap_angle(self._draft.x1, self._draft.y1, ix, iy)
                self._draft.x2, self._draft.y2 = ix, iy
            else:
                sx, sy = self._draft_start
                if shift:
                    ix, iy = snap_square(sx, sy, ix, iy)
                self._draft.set_corners(sx, sy, ix, iy)
            self.queue_draw()
            return True

        drag = self._drag
        if drag is not None:
            kind = drag["kind"]
            if kind == "move" and self.selected is not None:
                ox, oy = drag["origin"]
                tx, ty = ix - ox, iy - oy
                if shift:
                    # Only along the main direction of the drag
                    if abs(tx) >= abs(ty):
                        ty = 0.0
                    else:
                        tx = 0.0
                ax, ay = drag["applied"]
                self.selected.move_by(tx - ax, ty - ay)
                drag["applied"], drag["moved"] = (tx, ty), True
            elif kind == "handle" and self.selected is not None:
                self.selected.drag_handle(drag["name"], ix, iy, drag["start"], constrain=shift)
            elif kind == "crop-new":
                cx, cy = self._clamp_to_image(ix, iy)
                if shift:
                    cx, cy = self._clamp_to_image(*snap_square(*drag["start"], cx, cy))
                self.crop.set_corners(*drag["start"], cx, cy)
            elif kind == "crop-handle":
                cx, cy = self._clamp_to_image(ix, iy)
                self.crop.drag_handle(drag["name"], cx, cy, drag["start"], constrain=shift)
            elif kind == "crop-move":
                lx, ly = drag["last"]
                # Keep the whole area on the image
                dx = max(-self.crop.x, min(ix - lx, self.base.get_width() - self.crop.x - self.crop.w))
                dy = max(-self.crop.y, min(iy - ly, self.base.get_height() - self.crop.y - self.crop.h))
                self.crop.move_by(dx, dy)
                drag["last"] = (lx + dx, ly + dy)
            self.queue_draw()
            return True

        # Not dragging: show what a click would do
        handle = self.handle_at(event.x, event.y)
        if handle:
            self._set_cursor(HANDLE_CURSORS.get(handle, "crosshair"))
        elif self.tool == "select" and self.shape_at(ix, iy) is not None:
            self._set_cursor("move")
        elif self.tool == "crop" and self.crop is not None and self.crop.contains(ix, iy, 0):
            self._set_cursor("move")
        else:
            self._set_cursor(self._default_cursor())
        return False

    def on_button_release(self, widget, event):
        if event.button != 1:
            return False
        if self._draft is not None:
            draft, self._draft = self._draft, None
            if isinstance(draft, FreehandShape):
                draft.finish()
            if draft.is_too_small():
                self.queue_draw()
            elif isinstance(draft, FreehandShape):
                self._add_freehand(draft)
            else:
                self.add_shape(draft)
            return True

        drag, self._drag = self._drag, None
        if drag is None:
            return False
        kind = drag["kind"]
        if kind == "move" and drag["moved"] and drag["applied"] != (0.0, 0.0):
            self._push_undo(drag["snapshot"])
            self.emit("changed")
        elif kind == "handle" and self.selected is not None:
            start = drag["start"]
            if (self.selected.handles() != start.handles() or
                    self.selected.size != start.size):
                self._push_undo(drag["snapshot"])
                self.emit("changed")
        elif kind in ("crop-new", "crop-handle") and self.crop.is_too_small():
            self.crop = None
            self.queue_draw()
            self.emit("crop-changed")
        return True

    # ---- Freehand tidy-up ----

    def _add_freehand(self, drawing):
        """Add a finished freehand stroke, tidied into a clean shape if it's
        clearly a line, arrow, ellipse or rectangle (with a way back)."""
        found = recognize(drawing.points) if self.tidy else None
        if not found:
            self.add_shape(drawing)
            return
        kind = found[0]
        style = {"stroke": drawing.stroke, "size": drawing.size, "dash": drawing.dash,
                 "shadow": drawing.shadow, "fill": None}
        if kind == "line":
            clean = LineShape(*found[1], *found[2], **style)
        elif kind == "arrow":
            clean = ArrowShape(*found[1], *found[2], **style)
        elif kind == "ellipse":
            clean = EllipseShape(*found[1], **style)
        else:
            clean = RectShape(*found[1], **style)
        self.add_shape(clean)
        self._offer_keep_drawing(clean, drawing, kind)

    def keep_drawing(self, clean, drawing):
        """Put the hand-drawn version back in place of the tidied shape.
        (Part of the same Undo step as drawing it.)"""
        if clean in self.shapes:
            self.shapes[self.shapes.index(clean)] = drawing
            if self.selected is clean:
                self.selected = drawing
            self.queue_draw()
            self.emit("changed")
        self.close_tidy_offer()

    def _offer_keep_drawing(self, clean, drawing, kind):
        self.close_tidy_offer()
        bx, by, bw, bh = clean.bounds()
        wx, wy = self.to_widget(bx + bw / 2, by + bh)
        popover = Gtk.Popover(relative_to=self)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(wx), int(wy), 1, 1
        popover.set_pointing_to(rect)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_modal(False)          # don't get in the way of the next stroke
        box = Gtk.Box(spacing=8)
        for side in ("start", "end", "top", "bottom"):
            getattr(box, f"set_margin_{side}")(6)
        label = Gtk.Label(label=TIDY_MESSAGES[kind])
        keep = Gtk.Button(label=_("Keep My Drawing"))
        keep.connect("clicked", lambda b: self.keep_drawing(clean, drawing))
        box.pack_start(label, False, False, 0)
        box.pack_start(keep, False, False, 0)
        popover.add(box)
        popover.show_all()
        self._tidy_popover = popover

    def close_tidy_offer(self):
        if self._tidy_popover is not None:
            popover, self._tidy_popover = self._tidy_popover, None
            popover.popdown()
            GLib.idle_add(popover.destroy)

    # ---- Text entry ----

    def edit_text(self, shape, ix=None, iy=None):
        """Show a box to type in: for a new text at (ix, iy), or to change an
        existing one. Enter keeps it, Shift+Enter starts a new line, Esc
        cancels; clicking elsewhere also keeps it."""
        if self._finish_text is not None:
            self._finish_text(True)

        if shape is not None:
            ix, iy = shape.x, shape.y
        wx, wy = self.to_widget(ix, iy)

        popover = Gtk.Popover(relative_to=self)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(wx), int(wy), 1, 1
        popover.set_pointing_to(rect)
        popover.set_position(Gtk.PositionType.BOTTOM)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for side in ("start", "end", "top", "bottom"):
            getattr(box, f"set_margin_{side}")(6)
        view = Gtk.TextView()
        view.set_size_request(280, -1)
        view.set_wrap_mode(Gtk.WrapMode.NONE)
        view.set_left_margin(4)
        view.set_right_margin(4)
        view.set_top_margin(3)
        view.set_bottom_margin(3)
        buffer = view.get_buffer()
        if shape is not None:
            buffer.set_text(shape.text)
        frame = Gtk.Frame()
        frame.add(view)
        hint = Gtk.Label(label=_("Enter to finish · Shift+Enter for a new line · Esc to cancel"))
        hint.get_style_context().add_class("dim-label")
        box.pack_start(frame, False, False, 0)
        box.pack_start(hint, False, False, 0)
        popover.add(box)

        state = {"done": False}

        def finish(keep):
            if state["done"]:
                return
            state["done"] = True
            self._finish_text = None
            start, end = buffer.get_bounds()
            text = buffer.get_text(start, end, False).strip()
            popover.popdown()
            if not keep:
                return
            if shape is not None:
                self.set_text(shape, text)
            elif text:
                self.add_shape(TextShape(ix, iy, text, **self.style_for_new("text")))

        def on_key(_view, event):
            if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not _shift(event):
                finish(True)
                return True
            if event.keyval == Gdk.KEY_Escape:
                finish(False)
                return True
            return False

        def closed(_popover):
            finish(True)                     # clicking elsewhere keeps the text
            if self._text_popover is popover:
                self._text_popover = None
            GLib.idle_add(popover.destroy)   # not while it's still closing
            self.grab_focus()

        view.connect("key-press-event", on_key)
        popover.connect("closed", closed)
        self._text_popover = popover
        self._finish_text = finish
        popover.show_all()
        view.grab_focus()
        return view

    def finish_text_edit(self, keep=True):
        """Finish the text being typed, if any (as Enter or Esc would)."""
        if self._finish_text is not None:
            self._finish_text(keep)
