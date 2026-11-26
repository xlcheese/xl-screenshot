#!/bin/bash
# xl-Screenshot and xl-Annotate as real Wayland apps, under a headless Weston,
# with the stand-in Cinnamon screenshot service (xlcheese/xl-screenshot#10).
# Skipped (passing) when Weston isn't installed.
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
if ! command -v weston >/dev/null; then
    echo "(skipped: weston isn't installed)"; echo "FAILURES: none"; exit 0
fi
export XDG_RUNTIME_DIR=$(mktemp -d); chmod 700 "$XDG_RUNTIME_DIR"
weston --backend=headless-backend.so --socket=xl-wayland-test --width=1280 --height=800 \
       --idle-time=0 >/dev/null 2>&1 &
WESTON=$!
sleep 2
export WAYLAND_DISPLAY=xl-wayland-test GDK_BACKEND=wayland XDG_SESSION_TYPE=wayland
unset DISPLAY
"$PY" "$HERE/fake_cinnamon_screenshot.py" "$XDG_RUNTIME_DIR/calls.txt" ok &
FAKE=$!
sleep 1
# (GTK warns that the headless Weston has no keyboard or mouse: not ours, left out)
timeout 90 "$PY" "$HERE/wayland_check.py" 2>&1 | grep -v "Gdk-CRITICAL\|^$\|dbind"
kill $FAKE $WESTON 2>/dev/null
