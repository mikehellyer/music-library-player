#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Music Library Player"
APP_ID="music-library-player"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/$APP_ID"
APPLICATIONS_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"
DESKTOP_DIR="$HOME/Desktop"

UPDATE_MODE="false"
if [ "${1:-}" = "--update" ]; then
    UPDATE_MODE="true"
fi

echo
echo "Installing $APP_NAME..."
echo

if [ ! -f "$SCRIPT_DIR/music_library_player.py" ]; then
    echo "ERROR: music_library_player.py was not found beside install.sh"
    exit 1
fi

if [ ! -x /usr/bin/python3 ]; then
    echo "ERROR: /usr/bin/python3 was not found."
    exit 1
fi

if ! /usr/bin/python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "WARNING: Python Tkinter is not installed."
    echo "On Ubuntu/Pop!_OS:"
    echo "  sudo apt install python3-tk"
    echo
fi

if ! /usr/bin/python3 -c "import mutagen" >/dev/null 2>&1; then
    echo "WARNING: Python Mutagen is not installed."
    echo "On Ubuntu/Pop!_OS:"
    echo "  sudo apt install python3-mutagen"
    echo
fi

if ! /usr/bin/python3 -c "from PIL import Image" >/dev/null 2>&1; then
    echo "WARNING: Python Pillow is not installed."
    echo "On Ubuntu/Pop!_OS:"
    echo "  sudo apt install python3-pil python3-pil.imagetk"
    echo
fi

if ! command -v mpv >/dev/null 2>&1; then
    echo "WARNING: mpv is not installed."
    echo "mpv is the recommended playback engine."
    echo "On Ubuntu/Pop!_OS:"
    echo "  sudo apt install mpv"
    echo
fi

mkdir -p "$INSTALL_DIR"
mkdir -p "$APPLICATIONS_DIR"

cp "$SCRIPT_DIR/music_library_player.py" \
   "$INSTALL_DIR/music_library_player.py"
chmod +x "$INSTALL_DIR/music_library_player.py"

# Runtime/window icon files. If an update package ever omits an icon, the
# previously installed Music Library Player icon is intentionally left alone.
for icon_file in \
    music-library-player.png \
    music-library-player-256.png \
    music-library-player-128.png \
    music-library-player-64.png \
    music-library-player-48.png \
    music-library-player-32.png \
    music-library-player-16.png
do
    if [ -f "$SCRIPT_DIR/$icon_file" ]; then
        cp "$SCRIPT_DIR/$icon_file" "$INSTALL_DIR/$icon_file"
    fi
done

for size in 512 256 128 64 48 32 16; do
    mkdir -p "$ICON_BASE/${size}x${size}/apps"
done

# The master icon is used for 512x512. Desktop environments scale it as needed.
if [ -f "$SCRIPT_DIR/music-library-player.png" ]; then
    cp "$SCRIPT_DIR/music-library-player.png" \
       "$ICON_BASE/512x512/apps/$APP_ID.png"
fi

for size in 256 128 64 48 32 16; do
    src="$SCRIPT_DIR/music-library-player-${size}.png"
    dst="$ICON_BASE/${size}x${size}/apps/$APP_ID.png"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
    fi
done

DESKTOP_FILE="$APPLICATIONS_DIR/$APP_ID.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Music Library Player
Comment=Play and organise your local music collection
Exec=/usr/bin/python3 "$INSTALL_DIR/music_library_player.py"
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupNotify=true
StartupWMClass=MusicLibraryPlayer
EOF

chmod +x "$DESKTOP_FILE"

# Only create/update the desktop shortcut during a normal interactive install.
# Automatic updates should not unexpectedly add desktop files.
if [ "$UPDATE_MODE" != "true" ] && [ -d "$DESKTOP_DIR" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP_DIR/Music Library Player.desktop"
    chmod +x "$DESKTOP_DIR/Music Library Player.desktop"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_BASE" >/dev/null 2>&1 || true
fi

echo
echo "$APP_NAME installed successfully."
echo
echo "Program:"
echo "  $INSTALL_DIR"
echo
echo "Applications launcher:"
echo "  $DESKTOP_FILE"
echo
echo "Your personal library settings are preserved in:"
echo "  ~/.config/music-library-player"
echo
