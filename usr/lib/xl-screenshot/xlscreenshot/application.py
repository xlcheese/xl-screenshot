"""Starting xl-Screenshot: one running copy, and the command-line options."""

import os
import sys

from gi.repository import Gtk, Gio, GLib

from xlshared.ui import add_icon_search_path
from xlshared.i18n import _
from .config import APP_ID, APP_NAME, APP_COMMAND, APP_VERSION
from .window import ScreenshotWindow
from .tray import HAS_XAPP, TrayIcon, set_autostart


def launcher_command():
    """How to start xl-Screenshot again (for the login entry): the plain
    command once installed, or this folder's launcher when run from it."""
    path = os.path.realpath(sys.argv[0])
    if os.path.basename(path) == APP_COMMAND and not path.startswith("/usr/"):
        return path
    return APP_COMMAND


class ScreenshotApp(Gtk.Application):
    """Only one xl-Screenshot runs at a time. Starting it again (from the
    menu, a keyboard shortcut or, later, the tray icon) talks to the copy
    that is already running instead of opening a second window."""

    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.tray = None
        self.command = launcher_command()
        self.add_main_option("selection", ord("s"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _("Start a Selection capture right away"), None)
        self.add_main_option("tray", ord("t"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _("Start with just the tray icon (used when logging in)"), None)
        self.add_main_option("version", ord("v"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _("Show the version and quit"), None)

    def do_handle_local_options(self, options):
        if options.contains("version"):
            print(f"{APP_NAME} {APP_VERSION}")
            return 0          # done; don't start the app
        return -1             # carry on as normal

    def do_startup(self):
        Gtk.Application.do_startup(self)
        add_icon_search_path()

    def do_command_line(self, command_line):
        """Runs in the first copy, for its own start and every later start."""
        options = command_line.get_options_dict().end().unpack()

        first_start = self.window is None
        if first_start:
            self.window = ScreenshotWindow(application=self)
            if self.window.config["show_tray"]:
                self.set_tray(True)

        if options.get("tray") and self.tray is not None:
            if first_start:
                return 0                  # at login: just the tray icon
            self.window.show_from_tray()
        elif self.window.is_busy():
            self.window.present_current()   # capturing or annotating already
        elif options.get("selection"):
            self.window.start_selection()
        else:
            self.window.present()
        return 0

    # ---- System tray ----

    def set_tray(self, enabled):
        """Show or remove the tray icon, and start (or not) at login."""
        if enabled and HAS_XAPP:
            if self.tray is None:
                self.tray = TrayIcon(self.window, self.quit_from_tray)
            set_autostart(True, self.command)
        else:
            if self.tray is not None:
                self.tray.destroy()
                self.tray = None
            set_autostart(False, self.command)

    def quit_from_tray(self):
        """Quit for real (closing the window only hides it while the tray is on)."""
        w = self.window
        aw = w.annotate_window
        if aw is not None:
            # Ask about unsaved annotations now (close() would only ask later)
            if aw.confirm_discard():
                aw.modified = False
                aw.destroy()                # Discard (or nothing to keep)
            elif w.annotate_window is not None:
                return                      # Cancel: keep everything open
            # (Keep: the annotations went to the screenshot and Annotate closed)
        w.cancel_delay()
        if self.tray is not None:
            self.tray.destroy()
            self.tray = None
        self.quit()


def main():
    GLib.set_prgname(APP_COMMAND)
    GLib.set_application_name(APP_NAME)
    return ScreenshotApp().run(sys.argv)
