#!/bin/bash
# Try the menu entries and Nemo's "Annotate Image…" before there's a .deb.
#
# Installs into your home folder only (~/.local/share), pointing at the
# commands in this folder. Nothing system-wide; no sudo needed.
#
#   ./install-local.sh              add the menu entries and the Nemo item
#   ./install-local.sh --uninstall  remove them again
set -e

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$SHARE/applications"
ACTIONS="$SHARE/nemo/actions"
ICONS="$SHARE/icons/hicolor/scalable/actions"
APP_ICON_SIZES="scalable 32x32 24x24 16x16"
APP_IDS="io.github.xlcheese.XlScreenshot io.github.xlcheese.XlAnnotate"

DESKTOP_FILES="io.github.xlcheese.XlScreenshot.desktop io.github.xlcheese.XlAnnotate.desktop"
ACTION_FILE="xl-annotate.nemo_action"

refresh() {
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
}

if [ "$1" = "--uninstall" ]; then
    for f in $DESKTOP_FILES; do rm -f "$APPS/$f"; done
    rm -f "$ACTIONS/$ACTION_FILE"
    for f in "$HERE"/usr/share/icons/hicolor/scalable/actions/*.svg; do
        rm -f "$ICONS/$(basename "$f")"
    done
    for size in $APP_ICON_SIZES; do
        for id in $APP_IDS; do rm -f "$SHARE/icons/hicolor/$size/apps/$id.svg"; done
    done
    refresh
    echo "Removed the xl-Screenshot and xl-Annotate menu entries and the Nemo item."
    exit 0
fi

# Write the menu entries and translations from data/ and po/ (needs gettext)
if ! command -v msgfmt >/dev/null; then
    echo "Needs gettext to build the menu entries: sudo apt install gettext make" >&2
    exit 1
fi
make -C "$HERE" --no-print-directory >/dev/null

mkdir -p "$APPS" "$ACTIONS" "$ICONS"

# Point the commands at this folder (quoted, in case the path has spaces)
point_here() {
    sed -e "s|^Exec=xl-screenshot|Exec=\"$HERE/usr/bin/xl-screenshot\"|" \
        -e "s|^Exec=xl-annotate|Exec=\"$HERE/usr/bin/xl-annotate\"|" "$1" > "$2"
}

for f in $DESKTOP_FILES; do
    point_here "$HERE/usr/share/applications/$f" "$APPS/$f"
done
point_here "$HERE/usr/share/nemo/actions/$ACTION_FILE" "$ACTIONS/$ACTION_FILE"
cp "$HERE"/usr/share/icons/hicolor/scalable/actions/*.svg "$ICONS/"
for size in $APP_ICON_SIZES; do
    mkdir -p "$SHARE/icons/hicolor/$size/apps"
    cp "$HERE"/usr/share/icons/hicolor/$size/apps/*.svg "$SHARE/icons/hicolor/$size/apps/"
done
# Touch the theme folder so the menu and panel notice the new app icons
touch "$SHARE/icons/hicolor"
refresh

echo "Added:"
echo "  • xl-Screenshot in the menu under Accessories"
echo "  • xl-Annotate in the menu under Graphics (and in Nemo's Open With)"
echo "  • \"Annotate Image…\" when you right-click an image in Nemo"
echo
echo "If Nemo is open, close all its windows (or run: nemo -q) so it picks up the new item."
echo "To remove them: $0 --uninstall"
