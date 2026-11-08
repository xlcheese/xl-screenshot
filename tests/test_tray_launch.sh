#!/bin/bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/usr/bin/xl-screenshot"
PY="${PYTHON:-python3}"
VERSION=$(sed -n '1s/.*(\(.*\)).*/\1/p' "$ROOT/debian/changelog")
export HOME=$(mktemp -d); cd "$HOME"    # logs and pictures go in here
fails=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fails=$((fails+1)); fi; }
visible() { xdotool search --onlyvisible --name "^xl-Screenshot$" 2>/dev/null | head -1; }
running() { pgrep -fc "python3.* $APP"; }
openbox >/dev/null 2>&1 & sleep 1
mkdir -p $HOME/.config/xl-screenshot
echo '{"show_tray": true}' > $HOME/.config/xl-screenshot/config.json

"$PY" $APP --tray > tlog.txt 2>&1 &
sleep 2.5
check "login start (--tray): no window" '[ -z "$(visible)" ]'
check "login start (--tray): keeps running in the tray" '[ "$(running)" = "1" ]'
check "login entry written, pointing at this launcher" 'grep -q "^Exec=\"$APP\" --tray" $HOME/.config/autostart/io.github.xlcheese.XlScreenshot.desktop'
timeout 5 "$PY" $APP; sleep 1.2
check "start it from the menu: window shows" '[ -n "$(visible)" ]'
w=$(visible); xdotool windowactivate --sync $w; xdotool key --clearmodifiers alt+F4; sleep 1
check "Alt+F4: window hides" '[ -z "$(visible)" ]'
check "…still running in the tray" '[ "$(running)" = "1" ]'
timeout 5 "$PY" $APP --selection; sleep 1.2
check "--selection while in the tray: selection screen" '[ -n "$(xdotool search --onlyvisible --name "^xl-Screenshot Selection$")" ]'
ov=$(xdotool search --onlyvisible --name "^xl-Screenshot Selection$" | head -1); xdotool windowactivate --sync $ov; xdotool key Escape; sleep 1
check "Esc: window comes back" '[ -n "$(visible)" ]'
pkill -f "python3.* $APP"; sleep 0.5
grep -v "dbind\|^$" tlog.txt
echo "FAILURES: $fails"
