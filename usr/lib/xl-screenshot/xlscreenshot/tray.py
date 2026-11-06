"""The optional system tray icon, and starting xl-Screenshot at login.

Turned on with "Show in System Tray" in xl-Screenshot's menu. While it's on:
clicking the icon starts a Selection capture, right-clicking it shows a
menu, closing the window only hides it, and xl-Screenshot starts at login
(with just the tray icon).
"""

import os
import shutil

import gi
from gi.repository import Gtk

from xlshared.ui import ICONS_DIR
from xlshared.i18n import _
from .config import APP_ID, APP_NAME, APP_FALLBACK_ICON

try:
    gi.require_version("XApp", "1.0")
    from gi.repository import XApp       # Mint's tray icons (Cinnamon's tray applet)
    HAS_XAPP = True
except (ValueError, ImportError):
    HAS_XAPP = False

# The icon: our Selection icon redrawn on the 16px grid tray icons use,
# since a click starts a Selection. Cinnamon's tray only recolours icons
# (dark on a light panel, light on a dark one) when it finds them by name:
# given as a file, an icon shows up black, or not at all.
TRAY_ICON = "xl-screenshot-tray-symbolic"
TRAY_FALLBACK_ICON = "applets-screenshooter-symbolic"

AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_PATH = os.path.join(AUTOSTART_DIR, f"{APP_ID}.desktop")

_SYSTEM_ICON = f"/usr/share/icons/hicolor/scalable/actions/{TRAY_ICON}.svg"
_USER_HICOLOR = os.path.expanduser("~/.local/share/icons/hicolor")
_USER_ICON = os.path.join(_USER_HICOLOR, "scalable", "actions", f"{TRAY_ICON}.svg")
_OUR_ICON = os.path.join(ICONS_DIR, "hicolor", "scalable", "actions", f"{TRAY_ICON}.svg")


def _same_file_contents(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def _tray_icon_name():
    """Make sure Cinnamon can find our tray icon by name, and return the name.

    Once installed (the .deb) the icon is in /usr/share/icons already. When
    running from the unpacked folder, it's copied into ~/.local/share/icons,
    where Cinnamon also looks."""
    if os.path.isfile(_SYSTEM_ICON):
        return TRAY_ICON
    if not os.path.isfile(_OUR_ICON):
        return TRAY_FALLBACK_ICON
    if not _same_file_contents(_OUR_ICON, _USER_ICON):
        try:
            os.makedirs(os.path.dirname(_USER_ICON), exist_ok=True)
            shutil.copyfile(_OUR_ICON, _USER_ICON)
            # Touch the theme folder so Cinnamon notices the new icon
            os.utime(_USER_HICOLOR, None)
        except OSError as e:
            print(f"Could not install the tray icon: {e}")
            return TRAY_FALLBACK_ICON
    return TRAY_ICON


class TrayIcon:
    """The icon in the panel's tray. `window` is the ScreenshotWindow."""

    def __init__(self, window, on_quit):
        self.window = window
        self.on_quit = on_quit
        self.icon = XApp.StatusIcon()
        self.icon.set_name(APP_ID)
        self.icon.set_icon_name(_tray_icon_name())
        self.icon.set_tooltip_text(APP_NAME + "\n" + _("Click for a Selection capture"))
        self.menu = self._build_menu()
        self.icon.set_secondary_menu(self.menu)      # right-click
        self.icon.connect("activate", self.on_activate)
        self.icon.set_visible(True)

    def _build_menu(self):
        menu = Gtk.Menu()

        def item(label, handler):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _mi: handler())
            menu.append(mi)
            return mi

        # Translators: {name} is the program name, xl-Screenshot
        item(_("Show {name}").format(name=APP_NAME), self.window.show_from_tray)
        menu.append(Gtk.SeparatorMenuItem())
        item(_("Screen"), lambda: self.window.tray_capture("screen"))
        item(_("Window"), lambda: self.window.tray_capture("window"))
        item(_("Selection"), lambda: self.window.tray_capture("selection"))
        menu.append(Gtk.SeparatorMenuItem())
        item(_("Quit"), self.on_quit)
        menu.show_all()
        return menu

    def on_activate(self, icon, button, time):
        # Left click: straight into a Selection capture
        if button == 1:
            self.window.tray_capture("selection")

    def destroy(self):
        if self.icon is not None:
            self.icon.set_visible(False)
            self.icon = None


# ---- Start at login ----

def _desktop_quote(text):
    """Quote a path for a .desktop Exec line (handles spaces and quotes)."""
    for ch in ("\\", '"', "`", "$"):
        text = text.replace(ch, "\\" + ch)
    return f'"{text}"'


def set_autostart(enabled, command):
    """Add or remove the login entry. command: how to start xl-Screenshot
    (the plain command once installed, or this folder's launcher)."""
    if not enabled:
        try:
            os.remove(AUTOSTART_PATH)
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"Could not remove {AUTOSTART_PATH}: {e}")
        return
    exec_cmd = command if command == "xl-screenshot" else _desktop_quote(command)
    text = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=" + _("Keep xl-Screenshot in the system tray") + "\n"
        f"Exec={exec_cmd} --tray\n"
        f"Icon={APP_FALLBACK_ICON}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    try:
        os.makedirs(AUTOSTART_DIR, exist_ok=True)
        with open(AUTOSTART_PATH, "w") as f:
            f.write(text)
    except OSError as e:
        print(f"Could not write {AUTOSTART_PATH}: {e}")
