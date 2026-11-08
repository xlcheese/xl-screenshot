"""The older tests were written against the single-file xlscreenshot.py; this
gives them the same names from the package (window, selection, capture...)."""
import sys
import helpers  # noqa: F401  (puts the checkout's code on the path)
from xlscreenshot import config, capture, selection, window, escape_grab, application  # noqa: F401
from xlshared.ui import add_icon_search_path
add_icon_search_path()
_ns = {}
for m in (config, capture, escape_grab, selection, window):
    _ns.update({k: v for k, v in vars(m).items() if not k.startswith("__")})
_ns["XLScreenshotTool"] = window.ScreenshotWindow
sys.modules[__name__].__dict__.update(_ns)
