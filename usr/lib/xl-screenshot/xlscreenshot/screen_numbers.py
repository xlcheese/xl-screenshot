"""Big screen numbers, as --list-screens numbers them, shown on each screen
for a few seconds: which one is --screen 2 at a glance.

Run in its own short-lived process (xl-screenshot --show-screen-numbers),
so the terminal gets its prompt back straight away. A click (or Esc, where
the window has the keyboard) hides them sooner.
"""

import cairo
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from xlshared.ui import PANEL_SHADOW, draw_panel, theme_colors

SHOW_SECONDS = 3
PANEL_W, PANEL_H = 240, 230      # units
TITLE = "xl-Screenshot screen number"


def _wayland():
    return type(Gdk.Display.get_default()).__name__.startswith("GdkWayland")


class NumberWindow(Gtk.Window):
    """One screen's number. On X11: a small window in the middle of the
    screen. On Wayland, where apps can't place windows: a see-through
    window filling the screen, with the number in the middle."""

    def __init__(self, index, monitor, on_close):
        self.fills_screen = _wayland()
        super().__init__(type=Gtk.WindowType.TOPLEVEL if self.fills_screen else Gtk.WindowType.POPUP)
        self.number = str(index + 1)
        g, k = monitor.get_geometry(), monitor.get_scale_factor()
        self.size_text = f"{g.width * k} × {g.height * k}"
        self.set_title(TITLE)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        visual = self.get_screen().get_rgba_visual()
        self.see_through = visual is not None and self.get_screen().is_composited()
        if self.see_through:
            self.set_visual(visual)
        m = PANEL_SHADOW + 4 if self.see_through else 0     # room for the panel's shadow
        if self.fills_screen:
            self.set_default_size(g.width, g.height)
            self.fullscreen_on_monitor(self.get_screen(), index)
        else:
            self.set_default_size(PANEL_W + 2 * m, PANEL_H + 2 * m)
            self.move(g.x + (g.width - PANEL_W) // 2 - m, g.y + (g.height - PANEL_H) // 2 - m)
        self.accent, self.panel, self.border = theme_colors(self)
        fg = self.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        self.fg = (fg.red, fg.green, fg.blue)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", lambda *a: on_close())
        self.connect("key-press-event",
                     lambda w, e: on_close() if e.keyval == Gdk.KEY_Escape else None)

    def _text(self, cr, text, size, bold, y, alpha):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription.from_string("Sans")
        font.set_absolute_size(size * Pango.SCALE)
        font.set_weight(Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
        layout.set_font_description(font)
        layout.set_text(text, -1)
        _ink, logical = layout.get_pixel_extents()
        cr.move_to((self.get_allocated_width() - logical.width) / 2 - logical.x, y)
        cr.set_source_rgba(*self.fg, alpha)
        PangoCairo.show_layout(cr, layout)

    def on_draw(self, widget, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cr.set_operator(cairo.Operator.SOURCE)    # start see-through
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.Operator.OVER)
        x, y = (w - PANEL_W) / 2, (h - PANEL_H) / 2
        if self.see_through:
            draw_panel(cr, x, y, PANEL_W, PANEL_H, self.panel, self.border)
        else:
            cr.set_source_rgb(*self.panel[:3])    # no compositor: a plain square card
            cr.paint()
        # An accent bar along the top, then the number and the screen's size
        cr.set_source_rgba(*self.accent[:3], 1)
        cr.rectangle(x + 24, y + 22, PANEL_W - 48, 5)
        cr.fill()
        self._text(cr, self.number, 140, True, y + 30, 1)
        self._text(cr, self.size_text, 17, False, y + PANEL_H - 44, 0.6)
        return True


def show(seconds=SHOW_SECONDS):
    """Show every screen's number, then exit (returns the exit status)."""
    display = Gdk.Display.get_default()
    if display is None:
        return 1
    windows = []

    def close(*_a):
        for w in windows:
            w.destroy()
        windows.clear()
        Gtk.main_quit()
        return False

    for i in range(display.get_n_monitors()):
        win = NumberWindow(i, display.get_monitor(i), close)
        win.show_all()
        windows.append(win)
    GLib.timeout_add(int(seconds * 1000), close)
    Gtk.main()
    return 0
