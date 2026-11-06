"""xl-Screenshot: a screenshot tool for Linux Mint and the Cinnamon desktop."""

# Pick the library versions once, before any module imports them
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
