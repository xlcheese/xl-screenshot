"""The full-screen overlay for drawing a Selection rectangle."""

import math

from gi.repository import Gtk, Gdk, GLib

# The panel behind Cancel / Capture Selection reaches this far past the buttons
PANEL_PAD = 8

from .capture import capture_region
from xlshared.i18n import _


class SelectionOverlay(Gtk.Window):
    """The selection screen: a still picture of the desktop, dimmed, with the
    chosen area at normal brightness.

    It's an override-redirect window (GTK calls it a "popup"): the window
    manager leaves it alone. In Cinnamon that means it's drawn above the
    panels and appears and disappears instantly, with no window effects.
    Such windows don't get keyboard focus by themselves, so the overlay grabs
    the mouse and keyboard while it's up (that's what keeps Esc working)."""

    def __init__(self, parent_tool):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.parent_tool = parent_tool
        # Never shown on screen, but names the overlay in window lists
        self.set_title("xl-Screenshot Selection")
        self.captured = False

        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_accept_focus(True)
        self.set_can_focus(True)

        root = Gdk.get_default_root_window()
        screen_w = root.get_width()
        screen_h = root.get_height()
        # Cover the whole desktop (every monitor)
        self.set_default_size(screen_w, screen_h)
        self.resize(screen_w, screen_h)
        self.move(0, 0)
        self._grab_tries = 0
        self._grabbed = False
        # Where the overlay's top-left corner really is on the desktop
        # (normally 0, 0); drawing, button placement and the captured area
        # all allow for it, in case a window manager puts it elsewhere.
        self.origin_x = self.origin_y = 0

        self.start_x = -1
        self.start_y = -1
        self.rect_x = 0
        self.rect_y = 0
        self.rect_w = 0
        self.rect_h = 0

        self.is_dragging = False
        self.active_handle = None
        # Edges (x1, y1, x2, y2) of the rectangle when a handle drag started
        self.drag_edges = None
        self.handle_size = 8
        self._current_cursor = Gdk.CursorType.CROSSHAIR

        style_context = self.get_style_context()
        found, color = style_context.lookup_color("theme_selected_bg_color")
        if not found:
            found, color = style_context.lookup_color("selected_bg_color")
        if found:
            self.theme_color = (color.red, color.green, color.blue, 1.0)
        else:
            self.theme_color = (0.2, 0.6, 1.0, 1.0)

        # Colours for the panel behind Cancel / Capture Selection
        found, color = style_context.lookup_color("theme_bg_color")
        self.panel_color = (color.red, color.green, color.blue) if found else (0.96, 0.96, 0.95)
        found, color = style_context.lookup_color("borders")
        self.panel_border = (color.red, color.green, color.blue, 0.8) if found else (0, 0, 0, 0.25)

        self.bg_pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, screen_w, screen_h)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.KEY_PRESS_MASK)

        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", self.on_destroy)
        self.connect("configure-event", self.on_configure)

        self.fixed = Gtk.Fixed()
        self.add(self.fixed)

        self.control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.cancel_btn = Gtk.Button(label=_("Cancel"))
        self.cancel_btn.connect("clicked", self.on_cancel_clicked)
        self.control_box.pack_start(self.cancel_btn, False, False, 0)

        self.capture_btn = Gtk.Button(label=_("Capture Selection"))
        self.capture_btn.get_style_context().add_class("suggested-action")
        self.capture_btn.connect("clicked", self.on_capture_confirmed)
        self.control_box.pack_start(self.capture_btn, False, False, 0)

        self.fixed.put(self.control_box, 10, 10)

        self.connect("map-event", lambda w, e: self._grab_input())
        self.connect("unmap-event", lambda w, e: self._release_input())

        self.show_all()
        self.control_box.hide()
        self.set_cursor(Gdk.CursorType.CROSSHAIR)
        self.present()

    def _grab_input(self):
        """Take the mouse and keyboard, so Esc and clicks reach us. Another
        program can briefly hold a grab (e.g. just after a click), so retry
        a few times."""
        seat = Gdk.Display.get_default().get_default_seat()
        status = seat.grab(self.get_window(), Gdk.SeatCapabilities.ALL, True, None, None, None, None)
        self._grabbed = status == Gdk.GrabStatus.SUCCESS
        if not self._grabbed and self._grab_tries < 20:
            self._grab_tries += 1
            GLib.timeout_add(50, lambda: (self.get_mapped() and self._grab_input(), False)[1])
        return False

    def _release_input(self):
        if self._grabbed:
            Gdk.Display.get_default().get_default_seat().ungrab()
            self._grabbed = False
        return False

    def on_configure(self, widget, event):
        _ok, ox, oy = self.get_window().get_origin()
        if (ox, oy) != (self.origin_x, self.origin_y):
            self.origin_x, self.origin_y = ox, oy
            self.queue_draw()
        return False

    def set_cursor(self, cursor_type):
        display = Gdk.Display.get_default()
        cursor = Gdk.Cursor.new_for_display(display, cursor_type)
        self.get_window().set_cursor(cursor)

    def get_handles(self):
        x, y, w, h = self.rect_x, self.rect_y, self.rect_w, self.rect_h
        s = self.handle_size
        return {
            "nw": (x - s, y - s, s*2, s*2),
            "ne": (x + w - s, y - s, s*2, s*2),
            "se": (x + w - s, y + h - s, s*2, s*2),
            "sw": (x - s, y + h - s, s*2, s*2),
            "n":  (x + w//2 - s, y - s, s*2, s*2),
            "s":  (x + w//2 - s, y + h - s, s*2, s*2),
            "w":  (x - s, y + h//2 - s, s*2, s*2),
            "e":  (x + w - s, y + h//2 - s, s*2, s*2),
        }

    def _handle_at(self, cx, cy):
        for h_type, (hx, hy, hw, hh) in self.get_handles().items():
            if hx <= cx <= hx + hw and hy <= cy <= hy + hh:
                return h_type
        return None

    def _paint_screen(self, cr, rect=None):
        """Paint the still picture of the desktop (or just rect of it). On a
        HiDPI desktop it has more pixels than we have units: draw it at 1/scale."""
        scale = self.get_scale_factor()
        cr.save()
        if rect:
            cr.rectangle(*rect)
            cr.clip()
        cr.scale(1 / scale, 1 / scale)
        Gdk.cairo_set_source_pixbuf(cr, self.bg_pixbuf, -self.origin_x * scale, -self.origin_y * scale)
        cr.paint()
        cr.restore()

    def on_draw(self, widget, cr):
        # Dimmed screenshot everywhere...
        self._paint_screen(cr)
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.paint()

        if self.rect_w > 0 and self.rect_h > 0:
            # ...except inside the selection, which shows it undimmed
            self._paint_screen(cr, (self.rect_x, self.rect_y, self.rect_w, self.rect_h))

            cr.set_source_rgba(*self.theme_color)
            cr.set_line_width(1.5)
            cr.rectangle(self.rect_x, self.rect_y, self.rect_w, self.rect_h)
            cr.stroke()

            for hx, hy, hw, hh in self.get_handles().values():
                cr.rectangle(hx, hy, hw, hh)
                cr.set_source_rgba(1, 1, 1, 1)
                cr.fill_preserve()
                cr.set_source_rgba(*self.theme_color)
                cr.stroke()

        if self.control_box.get_visible():
            a = self.control_box.get_allocation()
            self._draw_panel(cr, a.x - PANEL_PAD, a.y - PANEL_PAD,
                             a.width + 2 * PANEL_PAD, a.height + 2 * PANEL_PAD)

    @staticmethod
    def _rounded_rect(cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _draw_panel(self, cr, x, y, w, h):
        """A rounded card in the theme's window colour, with a soft drop
        shadow, behind Cancel / Capture Selection, so they stand out on the
        darkened screen. (Drawn here, under the buttons, which GTK draws
        on top afterwards.)"""
        radius = 8
        cr.save()
        cr.new_path()
        # Soft shadow: a few widening, fading copies, nudged down a little
        for spread in range(8, 0, -1):
            self._rounded_rect(cr, x - spread, y - spread + 3, w + 2 * spread, h + 2 * spread,
                               radius + spread)
            cr.set_source_rgba(0, 0, 0, 0.035)
            cr.fill()
        self._rounded_rect(cr, x + 0.5, y + 0.5, w - 1, h - 1, radius)
        cr.set_source_rgb(*self.panel_color)
        cr.fill_preserve()
        cr.set_source_rgba(*self.panel_border)
        cr.set_line_width(1)
        cr.stroke()
        cr.restore()

    def position_control_box(self):
        _min, natural = self.control_box.get_preferred_size()
        btn_w, btn_h = natural.width, natural.height

        # Keep the buttons on the monitor that holds the selection
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_point(
            self.origin_x + self.rect_x + self.rect_w // 2,
            self.origin_y + self.rect_y + self.rect_h // 2
        )
        if monitor:
            geo = monitor.get_geometry()
            mon_x, mon_y, mon_w, mon_h = geo.x, geo.y, geo.width, geo.height
        else:
            root = Gdk.get_default_root_window()
            mon_x, mon_y, mon_w, mon_h = 0, 0, root.get_width(), root.get_height()
        # Desktop coordinates -> overlay coordinates
        mon_x -= self.origin_x
        mon_y -= self.origin_y

        # Work with the whole panel (buttons plus the card around them)
        pad = PANEL_PAD
        panel_w, panel_h = btn_w + 2 * pad, btn_h + 2 * pad
        gap = 6

        # Panel's right edge lines up with the selection's, just below it
        px = self.rect_x + self.rect_w - panel_w
        py = self.rect_y + self.rect_h + gap

        # Not enough room below the selection: put it above
        if py + panel_h > mon_y + mon_h:
            py = self.rect_y - panel_h - gap
        # Not enough room above either: put it inside the selection's bottom edge
        if py < mon_y:
            py = self.rect_y + self.rect_h - panel_h - gap

        px = max(mon_x, min(px, mon_x + mon_w - panel_w))
        py = max(mon_y, min(py, mon_y + mon_h - panel_h))
        target_x, target_y = px + pad, py + pad

        self.fixed.move(self.control_box, target_x, target_y)

    def _pointer_over_control_box(self, cx, cy):
        if not self.control_box.get_visible():
            return False
        alloc = self.control_box.get_allocation()
        return (alloc.x <= cx <= alloc.x + alloc.width and
                alloc.y <= cy <= alloc.y + alloc.height)

    def _handle_cursor_at(self, cx, cy):
        return {
            "nw": Gdk.CursorType.TOP_LEFT_CORNER,
            "ne": Gdk.CursorType.TOP_RIGHT_CORNER,
            "se": Gdk.CursorType.BOTTOM_RIGHT_CORNER,
            "sw": Gdk.CursorType.BOTTOM_LEFT_CORNER,
            "n":  Gdk.CursorType.TOP_SIDE,
            "s":  Gdk.CursorType.BOTTOM_SIDE,
            "w":  Gdk.CursorType.LEFT_SIDE,
            "e":  Gdk.CursorType.RIGHT_SIDE,
        }.get(self._handle_at(cx, cy))

    def _set_cursor_if_changed(self, cursor_type):
        if cursor_type != self._current_cursor:
            self._current_cursor = cursor_type
            self.set_cursor(cursor_type)

    def on_button_press(self, widget, event):
        if event.button == 1:
            if self.rect_w > 0 and self.rect_h > 0:
                handle = self._handle_at(event.x, event.y)
                if handle:
                    self.active_handle = handle
                    self.drag_edges = (self.rect_x, self.rect_y,
                                       self.rect_x + self.rect_w,
                                       self.rect_y + self.rect_h)
                    self.is_dragging = True
                    return True

            self.start_x = int(event.x)
            self.start_y = int(event.y)
            self.rect_x, self.rect_y = self.start_x, self.start_y
            self.rect_w, self.rect_h = 0, 0
            self.active_handle = None
            self.drag_edges = None
            self.is_dragging = True
            self.control_box.hide()
            self._set_cursor_if_changed(Gdk.CursorType.CROSSHAIR)
        return True

    def on_motion_notify(self, widget, event):
        cx, cy = int(event.x), int(event.y)

        if self.is_dragging:
            if self.active_handle:
                # Always work from the edges as they were when the drag
                # started, so dragging past the opposite edge flips cleanly.
                x1, y1, x2, y2 = self.drag_edges
                if "n" in self.active_handle: y1 = cy
                if "s" in self.active_handle: y2 = cy
                if "w" in self.active_handle: x1 = cx
                if "e" in self.active_handle: x2 = cx
                self.rect_x, self.rect_y = min(x1, x2), min(y1, y2)
                self.rect_w, self.rect_h = abs(x2 - x1), abs(y2 - y1)
            else:
                self.rect_x = min(self.start_x, cx)
                self.rect_y = min(self.start_y, cy)
                self.rect_w = abs(cx - self.start_x)
                self.rect_h = abs(cy - self.start_y)

            self.queue_draw()
            if self.control_box.get_visible():
                self.position_control_box()
            return True

        if self._pointer_over_control_box(cx, cy):
            self._set_cursor_if_changed(Gdk.CursorType.LEFT_PTR)
            return True

        if self.rect_w > 0 and self.rect_h > 0:
            handle_cursor = self._handle_cursor_at(cx, cy)
            if handle_cursor is not None:
                self._set_cursor_if_changed(handle_cursor)
                return True

        self._set_cursor_if_changed(Gdk.CursorType.CROSSHAIR)
        return True

    def on_button_release(self, widget, event):
        if event.button == 1:
            self.is_dragging = False
            self.active_handle = None
            self.drag_edges = None
            self._set_cursor_if_changed(Gdk.CursorType.CROSSHAIR)
            if self.rect_w > 5 and self.rect_h > 5:
                # Show before positioning: a hidden box measures as 0x0,
                # which would put the buttons off to the right of the selection.
                self.control_box.show_all()
                self.position_control_box()
                self.queue_draw()       # the panel behind the buttons
        return True

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.on_cancel_clicked(None)
            return True
        return False

    def on_destroy(self, widget):
        self._release_input()
        # Always bring the main window back, whether we captured or cancelled
        if self.parent_tool and not self.captured:
            self.parent_tool.restore_window()

    def on_cancel_clicked(self, button):
        self.destroy()

    def on_capture_confirmed(self, button):
        if self.rect_w > 5 and self.rect_h > 5:
            self.hide()
            # The selection is in overlay units; capture in desktop pixels
            scale = self.get_scale_factor()
            rect = tuple(round(v * scale) for v in (self.rect_x + self.origin_x, self.rect_y + self.origin_y,
                                                    self.rect_w, self.rect_h))

            def do_capture():
                pixbuf = capture_region(*rect, self.parent_tool.include_pointer)
                if pixbuf:
                    self.captured = True
                    self.parent_tool.update_screenshot_buffer(pixbuf)
                self.destroy()
                return False

            # Esc during the delay closes the overlay, which brings back the main window
            self.parent_tool.start_delay(do_capture, on_cancel=self.destroy)
        else:
            self.destroy()
