"""Facts about xl-Annotate, and where it keeps its settings."""

import json
import os

from xlshared.i18n import _

APP_ID = "io.github.xlcheese.XlAnnotate"     # also the name of the .desktop and icon files
APP_NAME = "xl-Annotate"
APP_COMMAND = "xl-annotate"
APP_VERSION = "0.1.1"
APP_FALLBACK_ICON = "applications-graphics"  # used until xl-Annotate has its own icon
APP_WEBSITE = "https://github.com/xlcheese/xl-screenshot"
APP_AUTHORS = ["Wesley Hayslip"]
APP_COPYRIGHT = "Copyright © 2026 Wesley Hayslip"
APP_CREDIT = _("Developed with the help of Claude, an AI assistant by Anthropic")

CONFIG_DIR = os.path.expanduser("~/.config/xl-annotate")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "tool": "arrow",
    "stroke": [0.88, 0.11, 0.14, 1.0],   # line colour (r, g, b, alpha), or None
    "fill": None,                        # fill colour, or None
    "dash": "solid",
    "shadow": False,
    "font": "Sans Bold",
    "sizes": {"line": 6, "text": 6, "step": 6, "pixelate": 6, "loupe": 6},
    "tidy_shapes": True,                 # tidy rough freehand shapes into clean ones
    "last_open_dir": "",
    "last_save_dir": "",
}


def _valid_color(value):
    return value is None or (isinstance(value, list) and len(value) == 4 and
                             all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in value))


def load_config():
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_CONFIG.items()}
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(data, dict):
        return cfg
    for key, default in DEFAULT_CONFIG.items():
        if key not in data:
            continue
        value = data[key]
        if key in ("stroke", "fill"):
            if _valid_color(value):
                cfg[key] = value
        elif key == "sizes":
            if isinstance(value, dict):
                for group, size in value.items():
                    if group in cfg["sizes"] and isinstance(size, (int, float)) and 1 <= size <= 20:
                        cfg["sizes"][group] = size
        elif isinstance(value, type(default)):
            cfg[key] = value
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"Could not save config: {e}")
