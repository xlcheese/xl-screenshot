"""Facts about the program, and where xl-Screenshot keeps its settings."""

import json
import os

from xlshared.i18n import _
import shutil

# ---- About the program (shown in the menu, window title and About) ----

APP_ID = "io.github.xlcheese.XlScreenshot"   # also the name of the .desktop and icon files
APP_NAME = "xl-Screenshot"
APP_COMMAND = "xl-screenshot"                 # the command that starts it
APP_VERSION = "0.1.1"
APP_FALLBACK_ICON = "applets-screenshooter"   # used until xl-Screenshot has its own icon
APP_WEBSITE = "https://github.com/xlcheese/xl-screenshot"
APP_AUTHORS = ["Wesley Hayslip"]
APP_COPYRIGHT = "Copyright © 2026 Wesley Hayslip"
APP_CREDIT = _("Developed with the help of Claude, an AI assistant by Anthropic")

# ---- Settings ----

CONFIG_DIR = os.path.expanduser("~/.config/xl-screenshot")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# Where versions before the rename kept their settings
OLD_CONFIG_PATH = os.path.expanduser("~/.config/xlscreenshot/config.json")

DEFAULT_CONFIG = {
    "save_format": "png",
    "last_save_dir": "",
    "delay_sec": 0,
    "include_pointer": False,
    "show_tray": False,
}


def _move_old_config():
    """Copy settings from before the rename (~/.config/xlscreenshot) once.

    The old folder is left alone, so nothing is lost if something goes wrong.
    """
    if os.path.exists(CONFIG_PATH) or not os.path.isfile(OLD_CONFIG_PATH):
        return
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        shutil.copy2(OLD_CONFIG_PATH, CONFIG_PATH)
        print(f"Settings copied from {OLD_CONFIG_PATH}")
    except OSError as e:
        print(f"Could not copy old settings: {e}")


def load_config():
    _move_old_config()
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(data, dict):
        return cfg
    for key, default in DEFAULT_CONFIG.items():
        value = data.get(key, default)
        # Ignore values of the wrong type (e.g. a hand-edited config)
        if isinstance(value, type(default)):
            cfg[key] = value
    if cfg["save_format"] not in ("png", "jpeg", "webp"):
        cfg["save_format"] = "png"
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"Could not save config: {e}")
