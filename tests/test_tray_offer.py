import helpers  # paths, a temporary home folder, English
"""The one-time "keep it in the tray?" question (xlcheese/xl-screenshot#5)."""
import json, os, subprocess, sys, time
subprocess.Popen(["openbox"], stderr=subprocess.DEVNULL); time.sleep(1)
from gi.repository import Gtk
from xlscreenshot import config as C
from xlscreenshot.window import ScreenshotWindow
from xlscreenshot.tray import HAS_XAPP
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
def settle(t=0.4):
    end = time.time() + t
    while time.time() < end:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(0.02)
check("Mint's tray support is installed (needed for these checks)", HAS_XAPP)

asked = []
answer = [Gtk.ResponseType.ACCEPT]
def fake_run(dialog):
    asked.append(dialog.get_property("text")); return answer[0]
Gtk.Dialog.run = fake_run
def saved():
    with open(C.CONFIG_PATH) as f: return json.load(f)
def fresh(settings=None):
    """Start from no settings file (a first-time user), or from the given settings."""
    if os.path.exists(C.CONFIG_PATH): os.remove(C.CONFIG_PATH)
    if settings is not None:
        os.makedirs(C.CONFIG_DIR, exist_ok=True)
        with open(C.CONFIG_PATH, "w") as f: json.dump(settings, f)
    asked.clear()
    win = ScreenshotWindow(); win.show_all(); settle()
    return win

# 1. first-time user says yes
win = fresh(); answer[0] = Gtk.ResponseType.ACCEPT
check("first use: the question is asked", (win.offer_tray_once(), len(asked))[1] == 1)
check("…it asks about the system tray", asked and "system tray" in asked[0])
check("yes: Show in System Tray is ticked and saved", win.menu_tray.get_active() and saved()["show_tray"] is True)
check("…and it is remembered as asked", saved()["tray_offered"] is True)
win.offer_tray_once(); check("never asked a second time", len(asked) == 1)
win.destroy()

# 2. first-time user says no
win = fresh(); answer[0] = Gtk.ResponseType.CANCEL
win.offer_tray_once()
check("no: the question was asked", len(asked) == 1)
check("…the tray stays off", not win.menu_tray.get_active() and saved()["show_tray"] is False)
check("…and it is remembered as asked", saved()["tray_offered"] is True)
win.destroy()
win = ScreenshotWindow(); win.show_all(); settle(); win.offer_tray_once()
check("…so the next start doesn't ask again", len(asked) == 1)
win.destroy()

# 3. someone who already used xl-Screenshot (settings from before this question existed)
win = fresh({"save_format": "jpeg", "show_tray": False})
win.offer_tray_once()
check("existing user: not asked", len(asked) == 0 and win.config["save_format"] == "jpeg")
win.destroy()

# 4. tray already on
win = fresh({"show_tray": True, "tray_offered": False})
win.offer_tray_once()
check("tray already on: not asked", len(asked) == 0)
win.destroy()

# 5. a real first start: the question pops up over the window; a second start doesn't ask
if os.path.exists(C.CONFIG_PATH): os.remove(C.CONFIG_PATH)
app = os.path.join(helpers.BIN, "xl-screenshot")
def windows(pid):
    out = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(pid)], capture_output=True, text=True).stdout
    return len(out.split())
p = subprocess.Popen([sys.executable, app], stderr=subprocess.DEVNULL); time.sleep(3)
check(f"real first start: window and question both showing ({windows(p.pid)} windows)", windows(p.pid) == 2)
p.kill(); p.wait(); time.sleep(0.5)
check("…and it was remembered at once", saved()["tray_offered"] is True)
p = subprocess.Popen([sys.executable, app], stderr=subprocess.DEVNULL); time.sleep(3)
check(f"second start: just the window ({windows(p.pid)} window)", windows(p.pid) == 1)
p.kill(); p.wait()
print("FAILURES:", fails or "none")
