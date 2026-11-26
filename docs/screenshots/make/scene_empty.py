from common import *
from xlshared.ui import add_icon_search_path
# Two monitors side by side, so the picture shows the Screens button too
class _Monitor:
    def __init__(self, x): self.x = x
    def get_geometry(self):
        g = Gdk.Rectangle(); g.x, g.y, g.width, g.height = self.x, 0, 1920, 1080; return g
    def connect(self, *a): return 0
    def __hash__(self): return self.x
    def __eq__(self, o): return isinstance(o, _Monitor) and o.x == self.x
_MONITORS = [_Monitor(0), _Monitor(1920)]
Gdk.Display.get_n_monitors = lambda self: len(_MONITORS)
Gdk.Display.get_monitor = lambda self, i: _MONITORS[i]
from xlscreenshot.window import ScreenshotWindow
start_wm(); add_icon_search_path()
win = ScreenshotWindow(); win.show_all(); settle(1)
subprocess.run(["xdotool", "mousemove", "2870", "1790"]); settle(0.5)
raw = grab(win); save(decorate(raw), "screenshot-empty")
print(raw.get_width(), raw.get_height())
