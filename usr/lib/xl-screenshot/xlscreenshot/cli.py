"""Capturing from the command line, for scripts and keyboard shortcuts:

    xl-screenshot --area 100,100,400,300 --file ~/area.png

takes the picture, saves it (or copies it, or opens it in xl-Annotate) and
exits, with no window and no tray icon. Many options follow scrot's, and
scrot's spellings are accepted too. Positions and sizes are in real pixels.

The captures are the app's own: a hidden xl-Screenshot window does the work,
so Selection, the window picker, the delay (and Esc during it, on X11) and
Cinnamon's screenshot service all behave exactly as they do in the app.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from xlshared.i18n import _
from xlshared.ui import EXT_TO_FORMAT, FORMAT_TO_EXT, add_icon_search_path, save_pixbuf
from .config import APP_NAME, APP_VERSION

# Options the app itself handles (anything else means a command-line capture)
APP_OPTIONS = {"-s", "--selection", "-t", "--tray", "-v", "--version"}
FORMATS = ("png", "jpeg", "webp")
FOLDER_NAME = "xl-Screenshot"

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
POINTER = -1          # --screen without a number: the screen the pointer is on


def wants_cli(argv):
    """True when the command line asks for a command-line capture (or help)."""
    for arg in argv[1:]:
        name = arg.split("=", 1)[0]
        if name not in APP_OPTIONS:
            return True
    return False


# ---- Options ----

def _rect(text):
    """X,Y,W,H (as scrot), or WxH+X+Y (as xrandr and --list-screens print)."""
    geometry = re.fullmatch(r"\s*(\d+)x(\d+)\+(-?\d+)\+(-?\d+)\s*", text)
    try:
        if geometry:
            w, h, x, y = (int(g) for g in geometry.groups())
        else:
            x, y, w, h = (int(p) for p in text.split(","))
    except ValueError:
        if text.rstrip().endswith(","):
            # "--area 1800, 400, 500, 500": the shell split it at the spaces
            raise argparse.ArgumentTypeError(
                _("expected X,Y,W,H with no spaces, e.g. 100,100,400,300 "
                  "(or in quotes: \"100, 100, 400, 300\")"))
        raise argparse.ArgumentTypeError(_("expected X,Y,W,H, e.g. 100,100,400,300"))
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError(_("the width and height must be more than 0"))
    return x, y, w, h


def _screen_number(text):
    """A screen number, or (as in --screen shot.png) the file name that followed."""
    try:
        return int(text)
    except ValueError:
        return text


def _window_id(text):
    try:
        return int(text, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(_("expected a window id, e.g. 0x3a00007"))


def _quality(text):
    try:
        q = int(text)
    except ValueError:
        q = 0
    if not 1 <= q <= 100:
        raise argparse.ArgumentTypeError(_("expected a number from 1 to 100"))
    return q


def _seconds(text):
    try:
        s = float(text)
    except ValueError:
        s = -1
    if s < 0:
        raise argparse.ArgumentTypeError(_("expected a number of seconds"))
    return s


def build_parser():
    p = argparse.ArgumentParser(
        prog="xl-screenshot", add_help=False,
        usage=_("xl-screenshot [WHAT TO CAPTURE] [OPTIONS] [FILE]"),
        description=_("Without options, xl-Screenshot opens its window. With any of the "
                      "options below (except --selection, --tray and --version on their "
                      "own), it captures, saves and exits, with no window."),
        epilog=_("Positions and sizes are in real pixels. Screens are numbered as "
                 "--list-screens shows. Without a file name, captures go to "
                 "Pictures/xl-Screenshot. The saved file's path is printed."))
    what = p.add_argument_group(_("What to capture (one of)")).add_mutually_exclusive_group()
    what.add_argument("--screens", "-m", "--multidisp", action="store_true",
                      help=_("every screen (the default)"))
    what.add_argument("--screen", "-M", "--monitor", nargs="?", type=_screen_number, const=POINTER, metavar="N",
                      help=_("screen N, or without N the one the pointer is on (X11)"))
    what.add_argument("--area", "-a", "--autoselect", type=_rect, metavar="X,Y,W,H",
                      help=_("a rectangle, e.g. 100,100,400,300"))
    what.add_argument("--selection", "-s", "--select", action="store_true",
                      help=_("draw the area, as with the Selection button"))
    what.add_argument("--window", action="store_true",
                      help=_("pick a window, as with the Window button"))
    what.add_argument("--focused", "-u", "--focussed", action="store_true",
                      help=_("the window that has the focus"))
    what.add_argument("--window-id", "-w", type=_window_id, metavar="WID",
                      help=_("a window by its X11 id (see xwininfo); X11 only"))

    out = p.add_argument_group(_("Where it goes"))
    out.add_argument("file", nargs="?", metavar="FILE", help=argparse.SUPPRESS)
    out.add_argument("--file", "-F", dest="file_opt", metavar="FILE",
                     help=_("save here; - writes the image to standard output. "
                            "Takes %%Y, %%m, %%d, %%H, %%M, %%S (see strftime), $w and $h "
                            "(the image's width and height) and $$ (a $)"))
    out.add_argument("--overwrite", "-o", action="store_true",
                     help=_("replace a file that is already there (otherwise a number is added)"))
    out.add_argument("--format", choices=FORMATS + ("jpg",), type=str.lower, metavar="FMT",
                     help=_("png, jpeg or webp (otherwise from the file name, or png)"))
    out.add_argument("--quality", "-q", type=_quality, default=90, metavar="1-100",
                     help=_("JPEG and WebP quality (default 90)"))
    out.add_argument("--clipboard", action="store_true",
                     help=_("copy the image (saved too only if a file is given)"))
    out.add_argument("--annotate", action="store_true",
                     help=_("open the capture in xl-Annotate"))

    opt = p.add_argument_group(_("Options"))
    opt.add_argument("--delay", "-d", type=_seconds, default=0, metavar="SEC",
                     help=_("wait this many seconds first (on X11, Esc cancels)"))
    opt.add_argument("--pointer", "-p", action="store_true", help=_("include the pointer"))
    opt.add_argument("--shadow", action="store_true", help=_("windows: include the shadow"))
    opt.add_argument("--list-screens", action="store_true",
                     help=_("list the screens, with their numbers, and exit; in a terminal, "
                            "each screen also shows its number for a few seconds"))
    opt.add_argument("--identify", action="store_true",
                     help=_("list the screens and show their numbers, even from a script"))
    opt.add_argument("--no-identify", action="store_true",
                     help=_("with --list-screens: never show the numbers on the screens"))

    app = p.add_argument_group(_("The app"))
    app.add_argument("--tray", "-t", action="store_true",
                     help=_("start with just the tray icon (used when logging in)"))
    app.add_argument("--version", "-v", action="store_true", help=_("show the version and exit"))
    app.add_argument("--help", "-h", action="help", help=_("show this help and exit"))
    p.add_argument("--hold-clipboard", metavar="PNG", help=argparse.SUPPRESS)
    p.add_argument("--show-screen-numbers", action="store_true", help=argparse.SUPPRESS)
    return p


# ---- Screens ----

def screen_rects():
    """Every monitor as (x, y, w, h) in real pixels, in the display's order."""
    display = Gdk.Display.get_default()
    rects = []
    for i in range(display.get_n_monitors()):
        m = display.get_monitor(i)
        g, k = m.get_geometry(), m.get_scale_factor()
        rects.append((g.x * k, g.y * k, g.width * k, g.height * k, m.is_primary()))
    return rects


def desktop_scale():
    """Real pixels per desktop unit (Cinnamon has one scale for every monitor)."""
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor() or display.get_monitor(0)
    return monitor.get_scale_factor() if monitor is not None else 1


# ---- File names ----

def expand_name(pattern, pixbuf):
    """strftime's % codes, then $w, $h and $$."""
    name = time.strftime(pattern)
    return re.sub(r"\$([wh$])", lambda m: {"w": str(pixbuf.get_width()),
                                             "h": str(pixbuf.get_height()),
                                             "$": "$"}.get(m.group(1), m.group(0)), name)


def default_folder():
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or \
        os.path.join(os.path.expanduser("~"), "Pictures")
    return os.path.join(pictures, FOLDER_NAME)


def unused_name(path):
    """path, or path with _1, _2... added before the extension if it's taken."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{stem}_{n}{ext}"):
        n += 1
    return f"{stem}_{n}{ext}"


def choose_format(path, wanted):
    """--format, or the file name's image extension, or PNG."""
    if wanted:
        return "jpeg" if wanted == "jpg" else wanted
    return EXT_TO_FORMAT.get(os.path.splitext(path or "")[1].lower(), "png")


# ---- The clipboard ----

def copy_to_clipboard(pixbuf):
    """Copy the image so it can still be pasted after we exit: handed to the
    desktop's clipboard keeper where there is one, otherwise to a small
    process that holds it until something else is copied."""
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_image(pixbuf)
    display = Gdk.Display.get_default()
    if display.supports_clipboard_persistence():
        clipboard.store()
        return
    fd, path = tempfile.mkstemp(prefix="xl-screenshot-clip-", suffix=".png",
                                dir=GLib.get_user_runtime_dir() or None)
    os.close(fd)
    pixbuf.savev(path, "png", [], [])
    launcher = os.path.realpath(LAUNCHER[0])
    subprocess.Popen([sys.executable, launcher, "--hold-clipboard", path],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def hold_clipboard(path):
    """The keeper: own the clipboard until something else is copied."""
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.Error:
        return EXIT_FAILED
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_image(pixbuf)
    size = (pixbuf.get_width(), pixbuf.get_height())

    def watch():
        # Our own copying is done: from now on, any change of owner means
        # something else was copied. (And if that already happened, go.)
        clipboard.connect("owner-change", lambda *a: Gtk.main_quit())
        now = clipboard.wait_for_image()
        if now is None or (now.get_width(), now.get_height()) != size:
            Gtk.main_quit()
        return False
    GLib.timeout_add(500, watch)
    Gtk.main()
    return EXIT_OK


# ---- Capturing ----

def _error(text):
    print(f"xl-screenshot: {text}", file=sys.stderr)


class Capture:
    """Runs one capture with a hidden xl-Screenshot window, then saves."""

    def __init__(self, args):
        from .window import ScreenshotWindow
        self.args = args
        self.result = None
        self.done = False
        cli = self

        class Engine(ScreenshotWindow):
            # The app's capture code, minus the window: results come to us
            def update_screenshot_buffer(self, pixbuf):
                self._capturing = False
                cli.finish(pixbuf)

            def restore_window(self):
                self._capturing = False
                cli.finish(None)

            def present(self, *a):
                pass

            def _show_error(self, text, secondary):
                _error(f"{text}. {secondary}")

        self.engine = Engine()
        e = self.engine
        e.include_pointer = args.pointer
        e.include_shadow = args.shadow
        e.delay_sec = args.delay        # seconds; the app's spin box stops at 11, scripts needn't
        if e.cinnamon is not None and args.clipboard:
            e.cinnamon.copy_captures = True

    def finish(self, pixbuf):
        if self.done:
            return
        self.done = True
        self.result = pixbuf
        GLib.idle_add(Gtk.main_quit)

    def start(self):
        a, e = self.args, self.engine
        e._capturing = True
        if a.selection:
            e._capturing = False
            e.start_selection()
        elif a.window:
            e.on_window_capture_clicked(None)
        elif a.area is not None:
            e.start_delay(self._capture_area, a.area)
        elif a.screen is not None:
            e.start_delay(self._capture_screen, a.screen)
        elif a.focused:
            e.start_delay(self._capture_focused)
        elif a.window_id is not None:
            e.start_delay(self._capture_window_id, a.window_id)
        else:
            e._capture_one_screen = False
            e.start_delay(e.perform_full_screen_capture)

    def _capture_area(self, rect):
        x, y, w, h = rect
        e = self.engine
        if e.cinnamon is not None:
            k = desktop_scale()     # Cinnamon takes desktop units
            e.cinnamon.screenshot_area(round(x / k), round(y / k), max(1, round(w / k)),
                                       max(1, round(h / k)), e.include_pointer, e._capture_done)
        elif e.wayland:
            e._cannot_capture()
        else:
            from .capture import capture_region
            e._capture_done(capture_region(x, y, w, h, e.include_pointer))
        return False

    def _capture_screen(self, number):
        e = self.engine
        if number == POINTER:                # the one the pointer is on
            e._capture_one_screen = True
            e._screen_monitor = None
            return e.perform_full_screen_capture()
        x, y, w, h, _primary = screen_rects()[number - 1]
        return self._capture_area((x, y, w, h))

    def _capture_focused(self):
        e = self.engine
        if e.cinnamon is not None and "ScreenshotWindow" in e.cinnamon.methods:
            e.cinnamon.screenshot_focused_window(e.include_shadow, e.include_pointer, e._capture_done)
            return False
        if e.wayland:
            return e._cannot_capture()
        from .x11_windows import active_window_id
        wid = active_window_id()
        if wid is None:
            _error(_("no window has the focus"))
            e._capture_done(None)
            return False
        return self._capture_window_id(wid)

    def _capture_window_id(self, wid):
        from .x11_windows import list_windows
        window = next((w for w in list_windows() if w["id"] == wid), None)
        return self.engine.perform_window_grab(hex(wid), window)


def check(args):
    """Problems with the options that can be found before capturing."""
    if isinstance(args.screen, str):           # --screen FILE: no number, then the file
        if args.file:
            return _("expected a screen number after --screen, not {text!r}").format(text=args.screen)
        args.file, args.screen = args.screen, POINTER
    if args.file and args.file_opt:
        return _("give the file once: as --file FILE or as FILE")
    target = args.file_opt or args.file
    if target == "-" and args.annotate:
        return _("--annotate needs a file, not standard output (-)")
    if args.tray:
        return _("--tray can't be used with capture options")
    if args.screen is not None and args.screen != POINTER and args.screen < 1:
        return _("screens are numbered from 1 (see --list-screens)")
    return None


def save(pixbuf, args):
    """Save as asked; returns the path saved to (or "-"), or None."""
    target = args.file_opt or args.file
    if target is None and args.clipboard and not args.annotate:
        return ""                          # just the clipboard
    if target == "-":
        fmt = choose_format(None, args.format)
        fd, tmp = tempfile.mkstemp(suffix="." + FORMAT_TO_EXT[fmt], dir=GLib.get_user_runtime_dir() or None)
        os.close(fd)
        try:
            save_pixbuf(pixbuf, tmp, fmt, args.quality)
            with open(tmp, "rb") as f:
                shutil.copyfileobj(f, sys.stdout.buffer)
            sys.stdout.buffer.flush()
        finally:
            os.unlink(tmp)
        return "-"
    if target is None:
        folder = default_folder()
        fmt = choose_format(None, args.format)
        # Translators: the start of a saved screenshot's file name (the date and time follow)
        path = os.path.join(folder, _("Screenshot") + time.strftime("-%Y-%m-%d_%H-%M-%S")
                            + "." + FORMAT_TO_EXT[fmt])
    else:
        path = os.path.abspath(os.path.expanduser(expand_name(target, pixbuf)))
        fmt = choose_format(path, args.format)
        if os.path.splitext(path)[1].lower() not in EXT_TO_FORMAT:
            path += "." + FORMAT_TO_EXT[fmt]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not args.overwrite:
        path = unused_name(path)
    save_pixbuf(pixbuf, path, fmt, args.quality)
    return path


def list_screens():
    for n, (x, y, w, h, primary) in enumerate(screen_rects(), 1):
        line = f"{n}: {w}x{h}+{x}+{y}"
        print(line + ("  " + _("(primary)") if primary else ""))


LAUNCHER = [sys.argv[0]]      # how we were started (to start the clipboard keeper)


def run(argv):
    LAUNCHER[0] = argv[0]
    parser = build_parser()
    args = parser.parse_args(argv[1:])
    if args.hold_clipboard:
        return hold_clipboard(args.hold_clipboard)
    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return EXIT_OK
    problem = check(args)
    if problem:
        parser.print_usage(sys.stderr)
        _error(problem)
        return EXIT_USAGE
    if Gdk.Display.get_default() is None:
        _error(_("no desktop to capture (is DISPLAY or WAYLAND_DISPLAY set?)"))
        return EXIT_FAILED
    if args.show_screen_numbers:
        from . import screen_numbers
        return screen_numbers.show()
    if args.list_screens or args.identify:
        list_screens()
        sys.stdout.flush()
        # The numbers on the screens too, when someone is reading this in a
        # terminal (not when a script reads the list), in a process of their
        # own so the prompt comes straight back
        if args.identify or (sys.stdout.isatty() and not args.no_identify):
            subprocess.Popen([sys.executable, os.path.realpath(LAUNCHER[0]), "--show-screen-numbers"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        return EXIT_OK
    add_icon_search_path()

    count = len(screen_rects())
    if args.screen not in (None, POINTER) and args.screen > count:
        _error(_("there is no screen {n}; this desktop has {count} (see --list-screens)")
               .format(n=args.screen, count=count))
        return EXIT_USAGE

    capture = Capture(args)
    if args.screen == POINTER and capture.engine.wayland:
        _error(_("on Wayland, apps aren't told where the pointer is: give the screen's "
                 "number, --screen N (see --list-screens)"))
        return EXIT_USAGE
    if args.window_id is not None and capture.engine.wayland:
        _error(_("--window-id works on X11 only; on Wayland, use --window or --focused"))
        return EXIT_USAGE

    GLib.idle_add(lambda: capture.start() and False)
    Gtk.main()
    pixbuf = capture.result
    if pixbuf is None:
        _error(_("nothing was captured (canceled, or the capture failed)"))
        return EXIT_FAILED

    try:
        path = save(pixbuf, args)
    except Exception as e:                  # a folder we can't write to, a missing format...
        _error(_("could not save the image: {error}").format(error=e))
        return EXIT_FAILED
    if args.clipboard and not (capture.engine.cinnamon is not None and capture.engine.cinnamon.copied):
        if capture.engine.wayland:
            _error(_("could not copy to the clipboard"))
            return EXIT_FAILED
        copy_to_clipboard(pixbuf)
    if args.annotate:
        launcher = os.path.join(os.path.dirname(os.path.realpath(argv[0])), "xl-annotate")
        command = [launcher] if os.path.isfile(launcher) else ["xl-annotate"]
        subprocess.Popen(command + [path], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if path and path != "-":
        print(path)
    return EXIT_OK
