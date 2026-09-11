#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REAL_HOME="$HOME"
TEST_HOME="$SCRIPT_DIR/.test-home"
APP_CONFIG=".config/music-library-player"
TEST_SCRIPT="$SCRIPT_DIR/music_library_player.py"
SIMULATED_SCRIPT="$SCRIPT_DIR/.music_library_player_simulated_update.py"

if [ ! -x /usr/bin/python3 ]; then
    echo "ERROR: /usr/bin/python3 was not found."
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/music_library_player.py" ]; then
    echo "ERROR: music_library_player.py was not found beside run-test.sh"
    exit 1
fi

# Rebuild an isolated test home on every run. This lets the test build use a
# copy of the real library settings/cache without modifying the installed
# player's live configuration.
rm -rf "$TEST_HOME"
mkdir -p "$TEST_HOME/.config"

if [ -d "$REAL_HOME/$APP_CONFIG" ]; then
    cp -a "$REAL_HOME/$APP_CONFIG" "$TEST_HOME/.config/"
    echo "Copied your current Simple Music Library Player settings into the test sandbox."
else
    echo "No existing Simple Music Library Player settings found; starting with a clean test sandbox."
fi

if [ "${1:-}" = "--simulate-update" ]; then
    # GitHub's real latest release is used, but this temporary copy identifies
    # itself as v0.10. This lets this build test the passive startup notice
    # and manual update offer without changing the actual source version.
    /usr/bin/python3 - "$SCRIPT_DIR/music_library_player.py" "$SIMULATED_SCRIPT" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text(encoding="utf-8")
start = 'APP_VERSION = "0.12"'
if start not in src:
    raise SystemExit("Could not create simulated update build: expected v0.12 source.")
src = src.replace(start, 'APP_VERSION = "0.11"', 1)
Path(sys.argv[2]).write_text(src, encoding="utf-8")
PY
    TEST_SCRIPT="$SIMULATED_SCRIPT"
    trap 'rm -f "$SIMULATED_SCRIPT"' EXIT
    echo
    echo "Starting UPDATE-NOTICE SIMULATION..."
    echo "The temporary test copy reports itself as v0.11 so the published GitHub v0.12 appears newer."
    echo "Expected startup behaviour: NO popup; bottom-left says an update is available."
    echo "Then click Check for Updates to confirm the normal update choice appears."
else
    echo
    echo "Starting Simple Music Library Player v0.12 LOCAL TEST build..."
fi

echo "Program: $TEST_SCRIPT"
echo "Test home: $TEST_HOME"
echo
echo "Your installed application and ~/.config/music-library-player are NOT modified."
echo

HOME="$TEST_HOME" \
XDG_CONFIG_HOME="$TEST_HOME/.config" \
/usr/bin/python3 "$TEST_SCRIPT"
