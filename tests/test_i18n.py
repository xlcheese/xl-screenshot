import helpers  # paths, a temporary home folder, English
import sys, os, tempfile, subprocess, time
lang = sys.argv[1] if len(sys.argv) > 1 else "de"
os.environ["LANGUAGE"] = lang; subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
import gi; gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
from xlshared.i18n import _, LOCALE_DIR
from xlshared.ui import add_icon_search_path; add_icon_search_path()
from xlscreenshot.window import ScreenshotWindow
from xlannotate.window import AnnotateWindow
def settle(t=0.6):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)
def texts(w, out):
    if isinstance(w, (Gtk.Label,)): out.append(w.get_text())
    if isinstance(w, Gtk.Button) and w.get_label(): out.append(w.get_label())
    t = w.get_tooltip_text()
    if t: out.append(t)
    if isinstance(w, Gtk.Container):
        for c in w.get_children(): texts(c, out)
    return out
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
expect = {"de": ("Bildschirm", "Auswahl", "Verzögerung in Sekunden:", "Rückgängig (Strg+Z)"),
          "fr": ("Écran", "Sélection", "Délai en secondes :", "Annuler (Ctrl+Z)"),
          "es": ("Pantalla", "Selección", "Retardo en segundos:", "Deshacer (Ctrl+Z)"),
          "pt_BR": ("Tela", "Seleção", "Atraso em segundos:", "Desfazer (Ctrl+Z)")}[lang]
check(f"{lang}: catalogue found in {LOCALE_DIR}", _("Screen") == expect[0])
w = ScreenshotWindow(); w.show_all(); settle()
got = texts(w, [])
check(f"{lang}: xl-Screenshot shows {expect[:3]}", all(e in got for e in expect[:3]))
english = [t for t in got if t in ("Screen", "Window", "Selection", "Annotate", "Delay in Seconds:")]
check(f"{lang}: no English left on the main window {english}", not english)
win = w.get_window(); Gdk.pixbuf_get_from_window(win, 0, 0, win.get_width(), win.get_height()).savev(os.path.join(helpers.PICTURES, f"i18n_shot_{lang}.png"), "png", [], [])
a = AnnotateWindow(); a.set_default_size(1000, 640); a.show_all(); settle(1)
got = texts(a, [])
check(f"{lang}: xl-Annotate tooltips translated", expect[3] in got)
from xlannotate import window as aw
check(f"{lang}: colour names translated", _("Red") != "Red")
win = a.get_window(); Gdk.pixbuf_get_from_window(win, 0, 0, win.get_width(), win.get_height()).savev(os.path.join(helpers.PICTURES, f"i18n_annotate_{lang}.png"), "png", [], [])
print("FAILURES:", fails or "none")
