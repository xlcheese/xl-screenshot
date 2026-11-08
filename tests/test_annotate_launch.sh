#!/bin/bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/usr/bin/xl-annotate"
PY="${PYTHON:-python3}"
VERSION=$(sed -n '1s/.*(\(.*\)).*/\1/p' "$ROOT/debian/changelog")
export HOME=$(mktemp -d); cd "$HOME"    # logs and pictures go in here
fails=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fails=$((fails+1)); fi; }
openbox >/dev/null 2>&1 & sleep 1
"$PY" -c "
import gi; gi.require_version('GdkPixbuf','2.0'); from gi.repository import GdkPixbuf
for n in ('one.png','two.png'):
    p=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,False,8,300,200); p.fill(0xffffffff); p.savev('$HOME/'+n,'png',[],[])
"
check "--version" '[ "$("$PY" $APP --version)" = "xl-Annotate $VERSION" ]'
"$PY" $APP $HOME/one.png > alog.txt 2>&1 &
sleep 2.5
check "opens the file in a window" '[ -n "$(xdotool search --onlyvisible --name "^one.png$")" ]'
timeout 5 "$PY" $APP $HOME/two.png; rc=$?; sleep 1.5
check "second launch hands over and exits (rc=$rc)" '[ $rc -eq 0 ]'
check "second image opens in its own window" '[ -n "$(xdotool search --onlyvisible --name "^two.png$")" ]'
check "both in one running copy" '[ "$(pgrep -fc "python3.* $APP")" = "1" ]'
timeout 5 "$PY" $APP $HOME/missing.png; sleep 1
check "missing file: error shown" '[ -n "$(xdotool search --onlyvisible --name "^$" 2>/dev/null | head -1)$(xdotool search --onlyvisible --class xl-annotate | wc -l | grep -v "^2$")" ]'
pkill -f "python3.* $APP"; sleep 0.5
"$PY" $APP > alog2.txt 2>&1 &
sleep 2
check "no file: empty window with the hint" '[ -n "$(xdotool search --onlyvisible --name "^xl-Annotate$")" ]'
pkill -f "python3.* $APP"
grep -v "dbind\|^$" alog.txt alog2.txt
echo "FAILURES: $fails"
