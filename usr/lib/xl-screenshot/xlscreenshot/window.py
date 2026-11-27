"""The main xl-Screenshot window: capture buttons, delay, thumbnail, save/copy."""

import os
import time

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from xlshared.ui import (FORMAT_TO_EXT, themed_icon_name, pixbuf_has_format, save_pixbuf,
                         show_error, confirm_overwrite, resolve_save_path)
from xlannotate.window import AnnotateWindow
from xlshared.i18n import _
from .config import (MAX_DELAY_SEC, APP_ID, APP_NAME, APP_VERSION, APP_FALLBACK_ICON, APP_WEBSITE,
                     APP_AUTHORS, APP_COPYRIGHT, APP_CREDIT, load_config, save_config)
from .capture import capture_region, window_capture_rect
from .escape_grab import EscapeKeyGrab
from .selection import SelectionOverlay, WindowPickerOverlay
from .x11_windows import list_windows
from .window_look import finish_window, corner_radius_for
from .capture import screen_scale, get_pointer_position
from . import screens_icon
from .tray import HAS_XAPP
from .cinnamon_service import CinnamonScreenshot, session_is_wayland

# Largest default thumbnail. The width also sets the window's minimum width.
THUMB_DEFAULT_MAX_W = 408
THUMB_DEFAULT_MAX_H = 300

# Capture button icons (our own symbolic SVGs, so they follow the theme's
# text color), with a stock icon in case ours can't be found
BUTTON_ICONS = {
    "screen": ("xl-screenshot-screen-symbolic", "video-display-symbolic"),
    "window": ("xl-screenshot-window-symbolic", "window-new-symbolic"),
    "selection": ("xl-screenshot-selection-symbolic", "edit-select-all-symbolic"),
}
ANNOTATE_ICON = ("xl-screenshot-annotate-symbolic", "document-edit-symbolic")


class ScreenshotWindow(Gtk.ApplicationWindow):
    def __init__(self, application=None):
        super().__init__(application=application, title=APP_NAME)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name(themed_icon_name(APP_ID, APP_FALLBACK_ICON))

        self.config = load_config()
        self.save_format = self.config["save_format"]
        self.last_save_dir = self.config["last_save_dir"]
        self.delay_sec = self.config["delay_sec"]
        self.include_pointer = self.config["include_pointer"]
        self.include_shadow = self.config["include_shadow"]
        self.fast_selection = self.config["fast_selection"]
        # How to capture (xlcheese/xl-screenshot#10): Cinnamon's own screenshot
        # service when it's there (X11 and Wayland alike), otherwise X11 tools.
        # On Wayland without the service there's no way yet: say so, never hang.
        self.wayland = session_is_wayland()
        self.cinnamon = CinnamonScreenshot.find()
        self.active_pixbuf = None   # what the thumbnail shows, and what Save/Copy use
        # The capture without annotations, and the still-editable marks on it
        self.base_pixbuf = None
        self.shapes = []
        self.annotate_window = None

        # True from the moment a capture starts until the window comes back
        self._capturing = False
        self.multi_monitor = False      # set by _update_monitors()
        self._capture_one_screen = False  # Screen with several monitors: just one
        self._screen_monitor = None       # ...and which, on Wayland
        # Pending delayed capture (see start_delay)
        self._delay_source = None
        self._delay_on_cancel = None
        self._escape_grab = None

        self.has_webp = pixbuf_has_format("webp")
        if self.save_format == "webp" and not self.has_webp:
            self.save_format = "png"

        # Thumbnail state (see update_screenshot_buffer / on_preview_draw)
        self.thumb_scale = 1.0      # scale of the default (smallest) thumbnail
        self._scaled_cache = None   # (width, height, pixbuf) of last drawn size
        self._max_size_hint = None  # (w, h) window size where the image is 1:1

        self.hb = Gtk.HeaderBar()
        self.hb.set_show_close_button(True)
        self.set_titlebar(self.hb)

        self.save_btn = Gtk.Button()
        self.save_btn.set_image(Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.MENU))
        self.save_btn.set_sensitive(False)
        self.save_btn.set_tooltip_text(_("Save As…"))
        self.save_btn.connect("clicked", self.on_save_as_clicked)
        self.hb.pack_start(self.save_btn)

        self.copy_btn = Gtk.Button()
        self.copy_btn.set_image(Gtk.Image.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.MENU))
        self.copy_btn.set_sensitive(False)
        self.copy_btn.set_tooltip_text(_("Copy to Clipboard"))
        self.copy_btn.connect("clicked", self.on_copy_clicked)
        self.hb.pack_start(self.copy_btn)

        menu = Gtk.Menu()

        self.menu_pointer = Gtk.CheckMenuItem(label=_("Include Pointer"))
        self.menu_pointer.set_active(self.include_pointer)
        self.menu_pointer.connect("toggled", self.on_menu_toggled)
        menu.append(self.menu_pointer)

        self.menu_shadow = Gtk.CheckMenuItem(label=_("Include Window Shadow"))
        self.menu_shadow.set_active(self.include_shadow and (self.cinnamon is not None or not self.wayland))
        self.menu_shadow.connect("toggled", self.on_shadow_toggled)
        # Cinnamon's service gives the real shadow; on X11 without it, one is drawn
        if self.cinnamon is None and self.wayland:
            self.menu_shadow.set_sensitive(False)
        menu.append(self.menu_shadow)

        self.menu_tray = Gtk.CheckMenuItem(label=_("Show in System Tray"))
        self.menu_tray.set_active(self.config["show_tray"] and HAS_XAPP)
        self.menu_tray.set_tooltip_text(
            _("Keep xl-Screenshot in the tray: click the icon for a Selection capture. "
              "Closing the window hides it, and it starts when you log in."))
        if not HAS_XAPP:
            self.menu_tray.set_sensitive(False)
            self.menu_tray.set_tooltip_text(_("Needs Mint's tray support: sudo apt install gir1.2-xapp-1.0"))
        self.menu_tray.connect("toggled", self.on_tray_toggled)
        menu.append(self.menu_tray)

        menu.append(Gtk.SeparatorMenuItem())

        # Accurate: adjust the box with its handles, then Capture. Fast: the
        # capture is taken as soon as you let go
        self.menu_accurate = Gtk.RadioMenuItem(label=_("Accurate Selection"))
        self.menu_fast = Gtk.RadioMenuItem.new_with_label_from_widget(self.menu_accurate, _("Fast Selection"))
        (self.menu_fast if self.fast_selection else self.menu_accurate).set_active(True)
        self.menu_fast.connect("toggled", self.on_selection_mode_toggled)
        menu.append(self.menu_accurate)
        menu.append(self.menu_fast)

        menu.append(Gtk.SeparatorMenuItem())

        self.menu_png = Gtk.RadioMenuItem(label=_("PNG (Lossless)"))
        self.menu_jpg = Gtk.RadioMenuItem.new_with_label_from_widget(self.menu_png, _("JPEG (Compressed)"))
        self.menu_webp = Gtk.RadioMenuItem.new_with_label_from_widget(self.menu_png, _("WebP (Compressed)"))

        if not self.has_webp:
            self.menu_webp.set_sensitive(False)
            self.menu_webp.set_tooltip_text(_("WebP support not installed. Install 'webp-pixbuf-loader'."))

        menu.append(self.menu_png)
        menu.append(self.menu_jpg)
        menu.append(self.menu_webp)

        # Set the initial choice before connecting, so startup doesn't rewrite the config
        if self.save_format == "jpeg":
            self.menu_jpg.set_active(True)
        elif self.save_format == "webp":
            self.menu_webp.set_active(True)
        else:
            self.menu_png.set_active(True)

        self.menu_png.connect("toggled", self.on_format_toggled)
        self.menu_jpg.connect("toggled", self.on_format_toggled)
        self.menu_webp.connect("toggled", self.on_format_toggled)

        menu.append(Gtk.SeparatorMenuItem())

        about_item = Gtk.MenuItem(label=_("About"))
        about_item.connect("activate", self.on_about_clicked)
        menu.append(about_item)

        menu.show_all()

        menu_button = Gtk.MenuButton()
        menu_button.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.MENU))
        menu_button.set_popup(menu)
        self.hb.pack_end(menu_button)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_margin_start(15)
        self.main_box.set_margin_end(15)
        self.main_box.set_margin_top(15)
        self.main_box.set_margin_bottom(15)
        self.add(self.main_box)

        # The thumbnail is drawn by hand so it can grow with the window,
        # from its default size up to 1:1.
        self.preview_area = Gtk.DrawingArea()
        self.preview_area.connect("draw", self.on_preview_draw)
        self.preview_area.connect("size-allocate", self.on_preview_size_allocate)
        self.preview_area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.preview_area.connect("button-press-event", self.on_preview_button_press)
        # Stay hidden through show_all() until there is a screenshot to show
        self.preview_area.set_no_show_all(True)

        btn_cluster = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_cluster.set_homogeneous(True)       # three or four buttons, all the same width
        # Sets the window's minimum width; the default thumbnail matches it
        btn_cluster.set_size_request(THUMB_DEFAULT_MAX_W + 2, -1)
        self.btn_cluster = btn_cluster
        self.main_box.pack_start(btn_cluster, False, False, 0)

        # Screens: every monitor; only shown when there's more than one. Its
        # icon is drawn from the monitors' layout (see _update_monitors)
        self.screens_btn = self._create_icon_button(_("Screens"), *BUTTON_ICONS["screen"])
        self.screens_btn.connect("clicked", self.on_screens_capture_clicked)
        # Hidden until there are several monitors; what's inside it must be
        # shown now, as show_all() skips the inside of a no-show-all widget
        self.screens_btn.get_child().show_all()
        self.screens_btn.set_no_show_all(True)
        btn_cluster.pack_start(self.screens_btn, True, True, 0)

        screen_btn = self._create_icon_button(_("Screen"), *BUTTON_ICONS["screen"])
        screen_btn.connect("clicked", self.on_screen_capture_clicked)
        btn_cluster.pack_start(screen_btn, True, True, 0)
        self.screen_btn = screen_btn

        window_btn = self._create_icon_button(_("Window"), *BUTTON_ICONS["window"])
        window_btn.connect("clicked", self.on_window_capture_clicked)
        btn_cluster.pack_start(window_btn, True, True, 0)

        selection_btn = self._create_icon_button(_("Selection"), *BUTTON_ICONS["selection"])
        selection_btn.connect("clicked", self.on_selection_clicked)
        btn_cluster.pack_start(selection_btn, True, True, 0)
        self._watch_monitors()

        # Row under the buttons: Annotate on the left (once there's a
        # capture), Delay on the right, lined up with the buttons' right edge
        option_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        option_row.set_margin_top(5)

        self.annotate_btn = Gtk.Button(label=_("Annotate"))
        self.annotate_btn.set_image(Gtk.Image.new_from_icon_name(
            themed_icon_name(*ANNOTATE_ICON), Gtk.IconSize.BUTTON))
        self.annotate_btn.set_always_show_image(True)
        self.annotate_btn.set_tooltip_text(_("Add arrows, boxes and text (or double-click the thumbnail)"))
        self.annotate_btn.connect("clicked", lambda b: self.open_annotate())
        self.annotate_btn.set_no_show_all(True)     # appears after the first capture
        option_row.pack_start(self.annotate_btn, False, False, 0)

        delay_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        delay_lbl = Gtk.Label(label=_("Delay in Seconds:"))
        self.delay_spin = Gtk.SpinButton.new_with_range(0, MAX_DELAY_SEC, 1)
        self.delay_spin.set_value(self.delay_sec)
        self.delay_spin.set_width_chars(3)
        self.delay_spin.connect("value-changed", self.on_delay_changed)

        delay_box.pack_start(delay_lbl, False, False, 0)
        delay_box.pack_start(self.delay_spin, False, False, 0)

        option_row.pack_end(delay_box, False, False, 0)
        self.main_box.pack_start(option_row, False, False, 0)

        self.main_box.pack_end(self.preview_area, True, True, 0)

        # Show everything inside the window now, so that present() alone
        # brings up a complete window (even when we start with --selection
        # and the window first appears after the capture).
        self.connect("delete-event", self.on_delete_event)

        self.hb.show_all()
        self.main_box.show_all()

    # ---- Showing and hiding around a capture ----

    def is_busy(self):
        """True while a capture is in progress (window hidden for it),
        or while xl-Annotate is open on the screenshot."""
        return self._capturing or self.annotate_window is not None

    def present_current(self):
        """Bring forward whichever of our windows the user is working in."""
        if self.annotate_window is not None:
            self.annotate_window.present()
        elif not self._capturing:
            self.present()

    def _begin_capture(self):
        self._capturing = True
        self.hide()

    def restore_window(self):
        """Bring the main window back after a capture attempt."""
        self._capturing = False
        self.present()

    # ---- Thumbnail ----

    def _scaled_pixbuf(self, w, h):
        """The screenshot scaled to w x h, cached so redraws are cheap."""
        if w == self.active_pixbuf.get_width() and h == self.active_pixbuf.get_height():
            return self.active_pixbuf
        if not self._scaled_cache or self._scaled_cache[:2] != (w, h):
            scaled = self.active_pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
            self._scaled_cache = (w, h, scaled)
        return self._scaled_cache[2]

    def on_preview_draw(self, widget, cr):
        if not self.active_pixbuf:
            return False

        img_w, img_h = self.active_pixbuf.get_width(), self.active_pixbuf.get_height()
        area_w, area_h = widget.get_allocated_width(), widget.get_allocated_height()

        # Fit inside the area (leaving 1px for the border), never above 1:1
        # and never below the default thumbnail size.
        scale = min(1.0, (area_w - 2) / img_w, (area_h - 2) / img_h)
        scale = max(scale, self.thumb_scale)
        draw_w = max(1, round(img_w * scale))
        draw_h = max(1, round(img_h * scale))

        # Centre it in the area
        x = 1 + max(0, (area_w - 2 - draw_w) // 2)
        y = 1 + max(0, (area_h - 2 - draw_h) // 2)

        Gdk.cairo_set_source_pixbuf(cr, self._scaled_pixbuf(draw_w, draw_h), x, y)
        cr.rectangle(x, y, draw_w, draw_h)
        cr.fill()

        style_context = widget.get_style_context()
        found, color = style_context.lookup_color("borders")
        if found:
            cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        else:
            cr.set_source_rgba(0.5, 0.5, 0.5, 1.0)
        cr.set_line_width(1)
        cr.rectangle(x - 0.5, y - 0.5, draw_w + 1, draw_h + 1)
        cr.stroke()
        return False

    def on_preview_size_allocate(self, widget, alloc):
        """Stop the window growing past the size where the image is 1:1.

        Everything around the thumbnail (header bar, buttons, margins) is a
        fixed size, so the window's 1:1 size is that fixed part plus the image.
        """
        if not self.active_pixbuf:
            return
        # Use the window's allocation, not get_size(): the size limit is
        # measured the same way, and the allocation is always up to date here.
        win_w = self.get_allocated_width()
        win_h = self.get_allocated_height()
        chrome_w = win_w - alloc.width
        chrome_h = win_h - alloc.height
        # +2 for the 1px border; never below the current size, so a small
        # capture can't force the window under its minimum.
        max_w = max(win_w, chrome_w + self.active_pixbuf.get_width() + 2)
        max_h = max(win_h, chrome_h + self.active_pixbuf.get_height() + 2)

        if self._max_size_hint != (max_w, max_h):
            self._max_size_hint = (max_w, max_h)
            geometry = Gdk.Geometry()
            geometry.max_width = max_w
            geometry.max_height = max_h
            self.set_geometry_hints(None, geometry, Gdk.WindowHints.MAX_SIZE)

    def _create_icon_button(self, label_text, icon_name, fallback_icon_name):
        btn = Gtk.Button()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        image = Gtk.Image.new_from_icon_name(
            themed_icon_name(icon_name, fallback_icon_name), Gtk.IconSize.DIALOG
        )
        image.set_pixel_size(48)

        box.pack_start(image, False, False, 0)
        lbl = Gtk.Label(label=label_text)
        box.pack_start(lbl, False, False, 0)
        btn.add(box)
        return btn

    # ---- Menu and delay settings ----

    # ---- System tray ----

    def tray_is_on(self):
        app = self.get_application()
        return bool(app is not None and getattr(app, "tray", None) is not None)

    def on_tray_toggled(self, menu_item):
        enabled = menu_item.get_active()
        self.config["show_tray"] = enabled
        save_config(self.config)
        app = self.get_application()
        if app is not None and hasattr(app, "set_tray"):
            app.set_tray(enabled)

    def offer_tray_once(self):
        """The first time xl-Screenshot is used, offer to keep it in the tray
        (xlcheese/xl-screenshot#5). Asked once; never again either way."""
        if self.config["tray_offered"]:
            return False
        self.config["tray_offered"] = True
        save_config(self.config)
        if self.config["show_tray"] or not HAS_XAPP or not self.get_visible():
            return False
        dlg = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_("Keep xl-Screenshot in the system tray?"))
        dlg.format_secondary_text(
            _("Click the tray icon for a quick Selection capture. xl-Screenshot will also "
              "start when you log in. You can change this any time with Show in System "
              "Tray in the menu."))
        dlg.add_button(_("_Not Now"), Gtk.ResponseType.CANCEL)
        yes = dlg.add_button(_("_Show in Tray"), Gtk.ResponseType.ACCEPT)
        yes.get_style_context().add_class("suggested-action")
        dlg.set_default_response(Gtk.ResponseType.ACCEPT)
        response = dlg.run()
        dlg.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            self.menu_tray.set_active(True)    # same as ticking it in the menu
        return False

    def on_delete_event(self, widget, event):
        # With the tray icon on, closing the window only hides it, and
        # forgets the capture so it opens fresh next time
        if self.tray_is_on():
            self.hide()
            self.clear_capture()
            return True
        return False

    def clear_capture(self):
        """Forget the last capture: thumbnail, original image and marks.
        (Anything already copied stays on the clipboard.)"""
        self.active_pixbuf = None
        self.base_pixbuf = None
        self.shapes = []
        self._scaled_cache = None
        self.save_btn.set_sensitive(False)
        self.copy_btn.set_sensitive(False)
        self.annotate_btn.hide()
        self.preview_area.hide()
        self._max_size_hint = None
        self.set_geometry_hints(None, None, 0)
        self.resize(1, 1)              # back to the small, empty window

    def show_from_tray(self):
        if self.is_busy():
            self.present_current()
        else:
            self.present()

    def tray_capture(self, kind):
        """Start a capture from the tray icon (works with the window hidden)."""
        if self.is_busy():
            self.present_current()
        elif kind == "screens":
            self.on_screens_capture_clicked(None)
        elif kind == "screen":
            self.on_screen_capture_clicked(None)
        elif kind == "window":
            self.on_window_capture_clicked(None)
        else:
            self.start_selection()

    def on_shadow_toggled(self, menu_item):
        self.include_shadow = menu_item.get_active()
        self.config["include_shadow"] = self.include_shadow
        save_config(self.config)

    def on_selection_mode_toggled(self, menu_item):
        self.fast_selection = self.menu_fast.get_active()
        self.config["fast_selection"] = self.fast_selection
        save_config(self.config)

    def on_menu_toggled(self, menu_item):
        self.include_pointer = self.menu_pointer.get_active()
        self.config["include_pointer"] = self.include_pointer
        save_config(self.config)

    def on_format_toggled(self, menu_item):
        if menu_item.get_active():
            if menu_item == self.menu_jpg:
                self.save_format = "jpeg"
            elif menu_item == self.menu_webp:
                self.save_format = "webp"
            else:
                self.save_format = "png"

            self.config["save_format"] = self.save_format
            save_config(self.config)

    def on_delay_changed(self, spin_button):
        self.delay_sec = int(spin_button.get_value())
        self.config["delay_sec"] = self.delay_sec
        save_config(self.config)

    # ---- Delay (shared by all three capture modes) ----

    def start_delay(self, callback, *args, on_cancel=None):
        """Run callback(*args) after the user's delay (or a short pause so
        our window has time to disappear). During a real delay, pressing Esc
        cancels the capture and calls on_cancel (default: show the window)."""
        self.cancel_delay()
        delay_ms = self.delay_sec * 1000 if self.delay_sec > 0 else 250

        def fire():
            # Let Escape go before capturing, so it never stays grabbed
            self._delay_source = None
            self._release_escape()
            callback(*args)
            return False

        self._delay_source = GLib.timeout_add(delay_ms, fire)
        self._delay_on_cancel = on_cancel or self.restore_window
        if self.delay_sec > 0 and not self.wayland:
            self._escape_grab = EscapeKeyGrab(self.on_delay_escape)

    def on_delay_escape(self):
        on_cancel = self._delay_on_cancel
        self.cancel_delay()
        print("Screenshot cancelled.")
        on_cancel()

    def cancel_delay(self):
        if self._delay_source is not None:
            GLib.source_remove(self._delay_source)
            self._delay_source = None
        self._release_escape()

    def _release_escape(self):
        if self._escape_grab is not None:
            self._escape_grab.release()
            self._escape_grab = None

    # ---- Screen ----

    # ---- Monitors: one, or several (then Screens and Screen) ----

    def monitor_rects(self):
        """Every monitor's (x, y, w, h), in desktop units."""
        display = Gdk.Display.get_default()
        rects = []
        for i in range(display.get_n_monitors()):
            g = display.get_monitor(i).get_geometry()
            rects.append((g.x, g.y, g.width, g.height))
        return rects

    def _watch_monitors(self):
        display = Gdk.Display.get_default()
        display.connect("monitor-added", lambda d, m: self._update_monitors())
        display.connect("monitor-removed", lambda d, m: self._update_monitors())
        self.connect("style-updated", lambda w: self._update_monitors())
        self.connect("notify::scale-factor", lambda w, p: self._update_monitors())
        self._watched_monitors = set()
        self._update_monitors()

    def _update_monitors(self):
        """Show Screens only with several monitors, its icon drawn from their
        layout; called again whenever monitors come, go or move."""
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            monitor = display.get_monitor(i)
            if monitor not in self._watched_monitors:      # moved in the display settings
                self._watched_monitors.add(monitor)
                monitor.connect("notify::geometry", lambda m, p: self._update_monitors())
        rects = self.monitor_rects()
        self.multi_monitor = len(rects) > 1
        if self.multi_monitor:
            fg = self.screens_btn.get_style_context().get_color(Gtk.StateFlags.NORMAL)
            icon = screens_icon.render(rects, (fg.red, fg.green, fg.blue, fg.alpha),
                                       scale=self.get_scale_factor())
            if icon is not None:
                self.screens_btn.get_child().get_children()[0].set_from_surface(icon)
        self.screens_btn.set_visible(self.multi_monitor)
        app = self.get_application()
        tray = getattr(app, "tray", None) if app is not None else None
        if tray is not None:
            tray.show_screens(self.multi_monitor)

    def _monitor_for_screen(self):
        """The monitor Screen captures: where the pointer is (X11, checked at
        capture time, so after a delay it follows you); on Wayland apps
        aren't told, so the one xl-Screenshot was on when Screen was clicked."""
        display = Gdk.Display.get_default()
        monitor = None
        if not self.wayland:
            pos = get_pointer_position()          # device pixels
            if pos is not None:
                scale = screen_scale()
                monitor = display.get_monitor_at_point(int(pos[0] / scale), int(pos[1] / scale))
        if monitor is None and self._screen_monitor is not None:
            return self._screen_monitor
        if monitor is None:
            monitor = display.get_primary_monitor() or display.get_monitor(0)
        g = monitor.get_geometry()
        return (g.x, g.y, g.width, g.height)

    def on_screens_capture_clicked(self, button):
        """Screens: every monitor."""
        self._capture_one_screen = False
        self._begin_capture()
        self.start_delay(self.perform_full_screen_capture)

    def on_screen_capture_clicked(self, button):
        """Screen: with one monitor, the whole screen; with several, the one
        you're on."""
        self._capture_one_screen = self.multi_monitor
        self._screen_monitor = None
        if self.multi_monitor and self.get_visible() and self.get_window() is not None:
            g = Gdk.Display.get_default().get_monitor_at_window(self.get_window()).get_geometry()
            self._screen_monitor = (g.x, g.y, g.width, g.height)
        self._begin_capture()
        self.start_delay(self.perform_full_screen_capture)

    def perform_full_screen_capture(self):
        if self._capture_one_screen:
            return self._capture_monitor(self._monitor_for_screen())
        if self.cinnamon is not None:
            self.cinnamon.screenshot(self.include_pointer, self._capture_done)
            return False
        if self.wayland:
            return self._cannot_capture()
        root = Gdk.get_default_root_window()
        scale = root.get_scale_factor()
        pixbuf = capture_region(0, 0, root.get_width() * scale, root.get_height() * scale,
                                self.include_pointer)
        if pixbuf:
            self.update_screenshot_buffer(pixbuf)
        else:
            print("Screen capture failed.")
            self.restore_window()
        return False

    # ---- Window ----

    def on_window_capture_clicked(self, button):
        self._begin_capture()
        if self.cinnamon is not None:
            # Cinnamon's picker: the screen dims and the window under the pointer lifts
            GLib.timeout_add(250, self._pick_window_with_cinnamon)
        elif self.wayland:
            self._cannot_capture()
        else:
            GLib.timeout_add(250, self.prompt_window_selection)

    def _pick_window_with_cinnamon(self):
        self.cinnamon.select_window(self._cinnamon_window_picked)
        return False

    def _capture_monitor(self, rect):
        """Screen with several monitors: just that one."""
        x, y, w, h = rect
        if self.cinnamon is not None:
            self.cinnamon.screenshot_area(x, y, w, h, self.include_pointer, self._capture_done)
            return False
        if self.wayland:
            return self._cannot_capture()
        scale = screen_scale()
        pixbuf = capture_region(x * scale, y * scale, w * scale, h * scale, self.include_pointer)
        self._capture_done(pixbuf)
        return False

    def _cinnamon_window_picked(self, window_id):
        if window_id is None:          # Esc, or a click on the desktop
            self.restore_window()
            return
        self.start_delay(lambda: self.cinnamon.screenshot_window(
            window_id, self.include_shadow, self.include_pointer, self._capture_done))

    def prompt_window_selection(self):
        """X11 without Cinnamon's service: our look-alike of Cinnamon's window
        picker (the desktop tinted, the window under the pointer lifted)."""
        windows = list_windows()
        if not windows:
            self.restore_window()
            return False
        WindowPickerOverlay(self, windows, self._x11_window_picked)
        return False

    def _x11_window_picked(self, window):
        self.start_delay(self.perform_window_grab, hex(window["id"]), window)

    def perform_window_grab(self, window_id, window=None):
        """Capture a window's rectangle. With the picker's window details, its
        top corners are rounded like the theme's, and with Include Window
        Shadow on, a shadow is drawn (the screen can't give either on X11)."""
        pixbuf = None
        try:
            x, y, w, h = window_capture_rect(window_id)
            if w > 10 and h > 10:
                pixbuf = capture_region(x, y, w, h, self.include_pointer)
        except FileNotFoundError:
            self._show_error(_("Window capture needs xwininfo"),
                             _("Install it with: sudo apt install x11-utils"))
        except Exception as e:
            print(f"Window capture failed: {e}")

        if pixbuf and window is not None:
            radius = corner_radius_for(window)
            maximized = window.get("maximized")
            pixbuf = finish_window(pixbuf, scale=screen_scale(), radius=radius, rounded=radius > 0,
                                   shadow=self.include_shadow and not maximized)
        if pixbuf:
            self.update_screenshot_buffer(pixbuf)
        else:
            self.restore_window()
        return False

    # ---- Selection ----

    def on_selection_clicked(self, button):
        self.start_selection()

    def start_selection(self):
        """Start a Selection capture (the Selection button, or --selection)."""
        if self.is_busy():
            return
        self._begin_capture()
        GLib.timeout_add(250, self.launch_selection_overlay)

    def launch_selection_overlay(self):
        if self.wayland:
            if self.cinnamon is None:
                return self._cannot_capture()
            if os.environ.get("XL_SCREENSHOT_CINNAMON_SELECTION"):
                # Cinnamon's own selection instead of ours (for comparing)
                self.cinnamon.select_area(self._cinnamon_area_picked)
            else:
                # Our overlay, over a picture of the whole desktop from Cinnamon:
                # always without the pointer, or a frozen one would sit there
                # next to the real one while you draw
                self.cinnamon.screenshot(False, self._show_still_overlays, copy=False)
            return False
        Gdk.Display.get_default().flush()
        SelectionOverlay(self)
        return False

    def _show_still_overlays(self, still):
        """Wayland: our Selection overlay on each monitor, over Cinnamon's picture."""
        if still is None:
            self.restore_window()
            return
        group = []
        for monitor in range(Gdk.Display.get_default().get_n_monitors()):
            SelectionOverlay(self, still=still, monitor=monitor, group=group)

    def _cinnamon_area_picked(self, area):
        if area is None:
            self.restore_window()
            return
        self.start_delay(lambda: self.cinnamon.screenshot_area(*area, self.include_pointer, self._capture_done))

    # ---- Results from Cinnamon's service, and when there's no way to capture ----

    def _capture_done(self, pixbuf):
        if pixbuf is not None:
            self.update_screenshot_buffer(pixbuf)
        else:
            self.restore_window()

    def _cannot_capture(self):
        self._show_error(_("xl-Screenshot can't capture on this desktop yet"),
                         _("In a Wayland session, xl-Screenshot captures through Cinnamon's "
                           "screenshot service, which this desktop doesn't have. "
                           "Log in to an X11 session to use it here."))
        self.restore_window()
        return False

    # ---- Preview ----

    def update_screenshot_buffer(self, pixbuf):
        """A new capture: show it, with no annotations yet."""
        self.base_pixbuf = pixbuf
        self.shapes = []
        self.annotate_btn.show()
        self._show_pixbuf(pixbuf)
        self.restore_window()

    def _show_pixbuf(self, pixbuf):
        self.active_pixbuf = pixbuf
        self.save_btn.set_sensitive(True)
        self.copy_btn.set_sensitive(True)

        self._scaled_cache = None

        # Default thumbnail: as wide as the button row (so the side margins
        # match) and at most THUMB_DEFAULT_MAX_H tall; never enlarge small
        # captures. This is also the smallest the thumbnail can be shrunk to.
        img_w, img_h = pixbuf.get_width(), pixbuf.get_height()
        row_w = self.btn_cluster.get_preferred_width()[0]
        max_w = max(THUMB_DEFAULT_MAX_W, row_w - 2)
        self.thumb_scale = min(1.0, max_w / img_w, THUMB_DEFAULT_MAX_H / img_h)
        thumb_w = max(1, round(img_w * self.thumb_scale))
        thumb_h = max(1, round(img_h * self.thumb_scale))
        self.preview_area.set_size_request(thumb_w + 2, thumb_h + 2)

        # Clear the old 1:1 limit and snap back to the default size
        self._max_size_hint = None
        self.set_geometry_hints(None, None, 0)
        self.resize(1, 1)  # shrink to the minimum, which fits the default thumbnail

        self.preview_area.show()
        self.preview_area.queue_draw()

    # ---- Annotate ----

    def on_preview_button_press(self, widget, event):
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.open_annotate()
            return True
        return False

    def open_annotate(self):
        """Open xl-Annotate on the capture. Marks added earlier can still be
        moved, changed or deleted."""
        if self.base_pixbuf is None or self.is_busy():
            if self.annotate_window is not None:
                self.annotate_window.present()
            return
        win = AnnotateWindow(application=self.get_application(), embedded=True,
                             on_done=self.on_annotate_done)
        win.set_transient_for(self)
        win.set_modal(True)               # the screenshot window waits meanwhile
        # Translators: shown as the xl-Annotate window title while it edits a capture
        win.load_pixbuf(self.base_pixbuf, shapes=self.shapes, name=_("Screenshot"))
        win.connect("destroy", self.on_annotate_closed)
        self.annotate_window = win
        win.present()

    def on_annotate_done(self, base, shapes, flat):
        self.base_pixbuf = base
        self.shapes = shapes
        self._show_pixbuf(flat)

    def on_annotate_closed(self, win):
        if self.annotate_window is win:
            self.annotate_window = None
        self.present()

    # ---- Save / Copy ----

    def _show_error(self, text, secondary):
        show_error(self, text, secondary)

    def _resolve_save_path(self, path):
        """Final path and format: a typed image extension decides the
        format, otherwise the default format's extension is added."""
        return resolve_save_path(path, self.save_format)

    def on_save_as_clicked(self, button):
        if not self.active_pixbuf:
            return

        ext = FORMAT_TO_EXT.get(self.save_format, "png")

        dialog = Gtk.FileChooserDialog(
            title=_("Save Screenshot As"), parent=self, action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("_Save"), Gtk.ResponseType.ACCEPT
        )
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        # We check for overwrites ourselves, after the extension is settled
        dialog.set_do_overwrite_confirmation(False)

        if self.last_save_dir and os.path.isdir(self.last_save_dir):
            dialog.set_current_folder(self.last_save_dir)

        # Translators: the start of a saved screenshot's file name (the date and time follow)
        default_name = _("Screenshot") + time.strftime("-%Y-%m-%d_%H-%M-%S") + f".{ext}"
        dialog.set_current_name(default_name)

        filter_type = Gtk.FileFilter()
        if self.save_format == "jpeg":
            filter_type.set_name(_("JPEG Images"))
            filter_type.add_mime_type("image/jpeg")
        elif self.save_format == "webp":
            filter_type.set_name(_("WebP Images"))
            filter_type.add_mime_type("image/webp")
        else:
            filter_type.set_name(_("PNG Images"))
            filter_type.add_mime_type("image/png")
        dialog.add_filter(filter_type)

        all_images = Gtk.FileFilter()
        all_images.set_name(_("All Images"))
        all_images.add_pixbuf_formats()
        dialog.add_filter(all_images)

        while dialog.run() == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            if not filename:
                continue

            save_path, fmt = self._resolve_save_path(filename)

            if os.path.exists(save_path) and not confirm_overwrite(dialog, save_path):
                continue  # back to the file chooser

            try:
                save_pixbuf(self.active_pixbuf, save_path, fmt)
            except Exception as e:
                self._show_error(_("Could not save image"), str(e))
                continue  # let them pick another name/location

            print(f"File saved to: {save_path}")
            self.last_save_dir = os.path.dirname(save_path)
            self.config["last_save_dir"] = self.last_save_dir
            save_config(self.config)
            break

        dialog.destroy()

    def on_copy_clicked(self, button):
        if not self.active_pixbuf:
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(self.active_pixbuf)
        clipboard.store()
        print("Copied to clipboard.")

    def on_about_clicked(self, menu_item):
        dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        dialog.set_program_name(APP_NAME)
        dialog.set_version(APP_VERSION)
        dialog.set_comments(_("A screenshot tool for Linux Mint and the Cinnamon desktop, "
                              "with Screen, Window, and Selection capture modes."))
        dialog.set_logo_icon_name(themed_icon_name(APP_ID, APP_FALLBACK_ICON))
        if APP_WEBSITE:
            dialog.set_website(APP_WEBSITE)
        dialog.set_authors(APP_AUTHORS)
        dialog.set_copyright(f"{APP_COPYRIGHT}\n{APP_CREDIT}")    # the credit sits right below the author
        dialog.set_license_type(Gtk.License.GPL_3_0)    # GTK shows it as "version 3 or later"
        dialog.run()
        dialog.destroy()
