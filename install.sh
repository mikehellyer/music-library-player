#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Simple Music Library Player"
APP_ID="music-library-player"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
UPDATE_MODE="false"
if [ "${1:-}" = "--update" ]; then
    UPDATE_MODE="true"
fi

install_macos() {
    local app_source="$SCRIPT_DIR/Simple Music Library Player.app"
    local apps_dir="$HOME/Applications"
    local app_dest="$apps_dir/Simple Music Library Player.app"
    local support_dir="$HOME/Library/Application Support/$APP_ID"
    local venv_dir="$support_dir/venv"
    local base_python=""

    echo
    echo "Installing $APP_NAME for macOS..."
    echo

    if [ ! -d "$app_source" ]; then
        echo "ERROR: Simple Music Library Player.app was not found beside install.sh"
        exit 1
    fi

    # Finder-launched apps have a small PATH, so probe the standard Homebrew,
    # python.org and system locations for a Python build that includes Tkinter.
    # Search common Python locations. The .command installer runs in Terminal,
    # so include the user's current python3 as well as Homebrew, python.org and
    # MacPorts locations.
    local path_python=""
    path_python="$(command -v python3 2>/dev/null || true)"
    for candidate in \
        "$path_python" \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
        /opt/local/bin/python3 \
        /usr/bin/python3
    do
        [ -n "$candidate" ] || continue
        if [ -x "$candidate" ] && "$candidate" -c 'import tkinter' >/dev/null 2>&1; then
            base_python="$candidate"
            break
        fi
    done

    if [ -z "$base_python" ]; then
        echo "ERROR: Python 3 with Tkinter was not found."
        echo
        echo "If you use Homebrew, install it with:"
        echo "  brew install python python-tk"
        echo
        echo "Then run this installer again."
        exit 1
    fi

    mkdir -p "$support_dir" "$apps_dir"

    # Use a private virtual environment for the Python packages needed by the
    # player. Homebrew supplies Tkinter as a split Python package. Its Python
    # startup code exposes split modules such as Tkinter to a virtual
    # environment only when that environment includes system site packages.
    # Recreate any older/broken environment automatically.
    local rebuild_venv="false"
    if [ ! -x "$venv_dir/bin/python3" ]; then
        rebuild_venv="true"
    elif ! grep -Eq '^include-system-site-packages = true$' "$venv_dir/pyvenv.cfg" 2>/dev/null; then
        rebuild_venv="true"
    elif ! "$venv_dir/bin/python3" -c 'import tkinter' >/dev/null 2>&1; then
        rebuild_venv="true"
    fi

    if [ "$rebuild_venv" = "true" ]; then
        echo "Repairing Python support environment..."
        rm -rf "$venv_dir"
        "$base_python" -m venv --system-site-packages "$venv_dir"
    fi

    echo "Preparing Python support (Mutagen + Pillow)..."
    "$venv_dir/bin/python3" -m pip install \
        --disable-pip-version-check --quiet --upgrade mutagen pillow

    if ! "$venv_dir/bin/python3" -c 'import tkinter, mutagen; from PIL import Image, ImageTk' >/dev/null 2>&1; then
        echo "ERROR: The private Python environment could not load Tkinter, Mutagen and Pillow."
        exit 1
    fi

    rm -rf "$app_dest"
    /usr/bin/ditto "$app_source" "$app_dest"
    chmod +x "$app_dest/Contents/MacOS/SimpleMusicLibraryPlayer"

    # mpv is preferred, but VLC is also supported if already installed.
    export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    if ! command -v mpv >/dev/null 2>&1 && [ ! -x "/Applications/VLC.app/Contents/MacOS/VLC" ]; then
        echo
        echo "NOTE: No supported media player was found."
        echo "For best results install mpv with Homebrew:"
        echo "  brew install mpv"
        echo
    fi

    echo
    echo "$APP_NAME installed successfully."
    echo
    echo "Application:"
    echo "  $app_dest"
    echo
    echo "Python support:"
    echo "  $venv_dir"
    echo
    echo "Your library settings remain in:"
    echo "  ~/.config/music-library-player"
    echo

    if [ "$UPDATE_MODE" != "true" ]; then
        /usr/bin/open "$app_dest" || true
    fi
}

install_linux() {
    local install_dir="$HOME/.local/share/$APP_ID"
    local applications_dir="$HOME/.local/share/applications"
    local icon_base="$HOME/.local/share/icons/hicolor"
    local desktop_dir="$HOME/Desktop"

    echo
    echo "Installing $APP_NAME for Linux..."
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
        echo "On Ubuntu/Pop!_OS: sudo apt install python3-tk"
    fi
    if ! /usr/bin/python3 -c "import mutagen" >/dev/null 2>&1; then
        echo "WARNING: Python Mutagen is not installed."
        echo "On Ubuntu/Pop!_OS: sudo apt install python3-mutagen"
    fi
    if ! /usr/bin/python3 -c "from PIL import Image" >/dev/null 2>&1; then
        echo "WARNING: Python Pillow is not installed."
        echo "On Ubuntu/Pop!_OS: sudo apt install python3-pil python3-pil.imagetk"
    fi
    if ! command -v mpv >/dev/null 2>&1; then
        echo "WARNING: mpv is not installed."
        echo "On Ubuntu/Pop!_OS: sudo apt install mpv"
    fi

    mkdir -p "$install_dir" "$applications_dir"
    cp "$SCRIPT_DIR/music_library_player.py" "$install_dir/music_library_player.py"
    chmod +x "$install_dir/music_library_player.py"

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
            cp "$SCRIPT_DIR/$icon_file" "$install_dir/$icon_file"
        fi
    done

    for size in 512 256 128 64 48 32 16; do
        mkdir -p "$icon_base/${size}x${size}/apps"
    done
    if [ -f "$SCRIPT_DIR/music-library-player.png" ]; then
        cp "$SCRIPT_DIR/music-library-player.png" "$icon_base/512x512/apps/$APP_ID.png"
    fi
    for size in 256 128 64 48 32 16; do
        local src="$SCRIPT_DIR/music-library-player-${size}.png"
        local dst="$icon_base/${size}x${size}/apps/$APP_ID.png"
        if [ -f "$src" ]; then cp "$src" "$dst"; fi
    done

    local desktop_file="$applications_dir/$APP_ID.desktop"
    cat > "$desktop_file" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=Simple Music Library Player
Comment=Play and organise your local music collection
Exec=/usr/bin/python3 "$install_dir/music_library_player.py"
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupNotify=true
StartupWMClass=MusicLibraryPlayer
DESKTOP
    chmod +x "$desktop_file"

    local old_shortcut="$desktop_dir/Music Library Player.desktop"
    local new_shortcut="$desktop_dir/Simple Music Library Player.desktop"
    if [ -d "$desktop_dir" ]; then
        if [ "$UPDATE_MODE" != "true" ]; then
            rm -f "$old_shortcut"
            cp "$desktop_file" "$new_shortcut"
            chmod +x "$new_shortcut"
        elif [ -f "$old_shortcut" ] || [ -f "$new_shortcut" ]; then
            rm -f "$old_shortcut"
            cp "$desktop_file" "$new_shortcut"
            chmod +x "$new_shortcut"
        fi
    fi

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$icon_base" >/dev/null 2>&1 || true
    fi

    echo
    echo "$APP_NAME installed successfully."
    echo "Program: $install_dir"
    echo "Applications launcher: $desktop_file"
    echo "Settings preserved in: ~/.config/music-library-player"
    echo
}

case "$(uname -s)" in
    Darwin) install_macos ;;
    Linux)  install_linux ;;
    *)
        echo "ERROR: Unsupported operating system: $(uname -s)"
        exit 1
        ;;
esac
