#!/bin/bash
# Runs inside xvfb-run + dbus-run-session
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/usr/bin/xl-screenshot"
PY="${PYTHON:-python3}"
VERSION=$(sed -n '1s/.*(\(.*\)).*/\1/p' "$ROOT/debian/changelog")
export HOME=$(mktemp -d); cd "$HOME"    # logs and pictures go in here
fails=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fails=$((fails+1)); fi; }
visible() { xdotool search --onlyvisible --name "^xl-Screenshot$" 2>/dev/null | head -1; }
nproc_app() { pgrep -fc "python3.* $APP" ; }
openbox >/dev/null 2>&1 & sleep 1

# old settings to move over
mkdir -p $HOME/.config/xlscreenshot
echo '{"save_format": "jpeg", "delay_sec": 7, "include_pointer": true, "last_save_dir": "/tmp"}' > $HOME/.config/xlscreenshot/config.json

check "--version prints name and version" '[ "$("$PY" $APP --version)" = "xl-Screenshot $VERSION" ]'

"$PY" $APP > app.log 2>&1 &
sleep 2
check "first launch shows the window" '[ -n "$(visible)" ]'
check "old settings copied to ~/.config/xl-screenshot" 'grep -q "\"delay_sec\": 7" $HOME/.config/xl-screenshot/config.json && grep -q jpeg $HOME/.config/xl-screenshot/config.json'
check "old settings left in place" '[ -f $HOME/.config/xlscreenshot/config.json ]'
check "window class is xl-screenshot" 'xprop -id $(visible) WM_CLASS | grep -q "xl-screenshot"'

timeout 5 "$PY" $APP; rc=$?
sleep 1
check "second launch exits right away (rc=$rc)" '[ $rc -eq 0 ]'
check "still only one copy running" '[ "$(nproc_app)" = "1" ]'
check "window still showing" '[ -n "$(visible)" ]'

timeout 5 "$PY" $APP --selection; sleep 1.2
check "--selection to running copy hides the window" '[ -z "$(visible)" ]'
ov=$(xdotool search --onlyvisible --name "^xl-Screenshot Selection$" 2>/dev/null | head -1)
check "selection overlay is up" '[ -n "$ov" ]'
xwd -id $ov -silent 2>/dev/null | head -c 0
timeout 5 "$PY" $APP --selection; sleep 0.5
check "--selection while busy doesn't start a second overlay" '[ "$(xdotool search --onlyvisible --name "^xl-Screenshot Selection$" | wc -l)" = "1" ]'
xdotool windowactivate --sync $ov 2>/dev/null; xdotool key Escape; sleep 1
check "Esc on the overlay brings the window back" '[ -n "$(visible)" ]'

# quit: close the window
w=$(visible); xdotool windowactivate --sync $w; xdotool key --clearmodifiers alt+F4
sleep 1
check "closing the window quits the app" '[ "$(nproc_app)" = "0" ]'

# first launch straight into --selection
"$PY" $APP --selection >> app.log 2>&1 &
sleep 2
check "--selection at startup: no main window flash" '[ -z "$(visible)" ]'
ov=$(xdotool search --onlyvisible --name "^xl-Screenshot Selection$" 2>/dev/null | head -1)
check "--selection at startup: overlay is up" '[ -n "$ov" ]'
xdotool windowactivate --sync $ov 2>/dev/null; xdotool key Escape; sleep 1.2
w=$(visible)
check "after cancelling, the window appears" '[ -n "$w" ]'
import -window $w startup_selection_window.png 2>/dev/null || "$PY" - "$w" <<'PY'
import sys, gi; gi.require_version('Gdk','3.0'); gi.require_version('GdkX11','3.0'); gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gdk, GdkX11
d = GdkX11.X11Display.get_default(); win = GdkX11.X11Window.foreign_new_for_display(d, int(sys.argv[1]))
Gdk.pixbuf_get_from_window(win, 0, 0, win.get_width(), win.get_height()).savev("startup_selection_window.png", "png", [], [])
PY
pkill -f "python3.* $APP"; sleep 0.5
echo "--- app log:"; cat app.log
echo "FAILURES: $fails"
