#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REAL_HOME="$HOME"
TEST_HOME="$SCRIPT_DIR/.test-home"
APP_CONFIG=".config/music-library-player"

if [ ! -x /usr/bin/python3 ]; then
    echo "ERROR: /usr/bin/python3 was not found."
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/music_library_player.py" ]; then
    echo "ERROR: music_library_player.py was not found beside run-test.sh"
    exit 1
fi

# Rebuild an isolated test home on every run.  This lets the test build use a
# copy of the real library settings/cache without modifying the installed
# player's live configuration.
rm -rf "$TEST_HOME"
mkdir -p "$TEST_HOME/.config"

if [ -d "$REAL_HOME/$APP_CONFIG" ]; then
    cp -a "$REAL_HOME/$APP_CONFIG" "$TEST_HOME/.config/"
    echo "Copied your current Music Library Player settings into the test sandbox."
else
    echo "No existing Music Library Player settings found; starting with a clean test sandbox."
fi

echo
echo "Starting Music Library Player LOCAL TEST build..."
echo "Program: $SCRIPT_DIR/music_library_player.py"
echo "Test home: $TEST_HOME"
echo
echo "Your installed application and ~/.config/music-library-player are NOT modified."
echo

HOME="$TEST_HOME" \
XDG_CONFIG_HOME="$TEST_HOME/.config" \
/usr/bin/python3 "$SCRIPT_DIR/music_library_player.py"
