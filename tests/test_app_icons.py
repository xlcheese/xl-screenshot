import helpers  # noqa: F401  (paths, a temporary home folder, English)
import sys, os, subprocess
mode = sys.argv[1] if len(sys.argv) > 1 else "app"
import gi; gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
theme = Gtk.IconTheme.get_default()
if mode == "app":
    from xlshared.ui import add_icon_search_path; add_icon_search_path()
    from xlscreenshot.window import ScreenshotWindow
    from xlannotate.window import AnnotateWindow
    check("xl-Screenshot window uses its own icon", ScreenshotWindow().get_icon_name() == "io.github.xlcheese.XlScreenshot")
    check("xl-Annotate window uses its own icon", AnnotateWindow().get_icon_name() == "io.github.xlcheese.XlAnnotate")
for app_id in ("io.github.xlcheese.XlScreenshot", "io.github.xlcheese.XlAnnotate"):
    picks = {}
    for size in (16, 24, 32, 48, 128):
        info = theme.lookup_icon(app_id, size, 0)
        picks[size] = info.get_filename().split("/hicolor/")[1].split("/")[0] if info else None
    print(f"   {app_id.split('.')[-1]}: " + ", ".join(f"{s}px→{p}" for s, p in picks.items()))
    check(f"{app_id.split('.')[-1]}: found, with the small drawings at 16/24/32",
          picks[16] == "16x16" and picks[24] == "24x24" and picks[32] == "32x32" and picks[48] == "scalable" and picks[128] == "scalable")
print("FAILURES:", fails or "none")
