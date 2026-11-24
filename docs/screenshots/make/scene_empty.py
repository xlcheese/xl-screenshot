from common import *
from xlshared.ui import add_icon_search_path
from xlscreenshot.window import ScreenshotWindow
start_wm(); add_icon_search_path()
win = ScreenshotWindow(); win.show_all(); settle(1)
subprocess.run(["xdotool", "mousemove", "2870", "1790"]); settle(0.5)
raw = grab(win); save(decorate(raw), "screenshot-empty")
print(raw.get_width(), raw.get_height())
