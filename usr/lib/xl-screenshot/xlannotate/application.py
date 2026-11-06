"""Starting xl-Annotate on its own (menu, Nemo, or the xl-annotate command)."""

import sys

from gi.repository import Gtk, Gio, GLib

from xlshared.ui import add_icon_search_path
from xlshared.i18n import _
from .config import APP_ID, APP_NAME, APP_COMMAND, APP_VERSION
from .window import AnnotateWindow


class AnnotateApp(Gtk.Application):
    """One running copy; every image opened gets its own window."""

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.add_main_option("version", ord("v"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, _("Show the version and quit"), None)

    def do_handle_local_options(self, options):
        if options.contains("version"):
            print(f"{APP_NAME} {APP_VERSION}")
            return 0
        return -1

    def do_startup(self):
        Gtk.Application.do_startup(self)
        add_icon_search_path()

    def do_activate(self):
        # Started with no image: an empty window with an Open button
        AnnotateWindow(application=self).present()

    def do_open(self, files, n_files, hint):
        for gfile in files:
            path = gfile.get_path()
            window = AnnotateWindow(application=self)
            if path and window.open_file(path):
                window.present()
            else:
                window.destroy()


def main():
    GLib.set_prgname(APP_COMMAND)
    GLib.set_application_name(APP_NAME)
    return AnnotateApp().run(sys.argv)
