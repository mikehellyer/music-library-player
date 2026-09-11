SIMPLE MUSIC LIBRARY PLAYER v0.12 - macOS INSTALLATION
======================================================

EASIEST INSTALL
---------------
1. Download/extract the installer ZIP.
2. Double-click:

       Install Simple Music Library Player.command

3. The installer places the managed app here:

       ~/Applications/Simple Music Library Player.app

4. The app opens automatically after a successful normal installation.

WHY ~/Applications?
-------------------
Using your personal Applications folder means the built-in GitHub updater can
replace the app later without requesting an administrator password.

REQUIREMENTS
------------
The Mac needs Python 3 with Tkinter. The installer creates a private virtual
environment under:

       ~/Library/Application Support/music-library-player/venv

and installs Mutagen and Pillow into that environment.

Homebrew users can install the recommended dependencies with:

       brew install python python-tk mpv

VLC in /Applications is also detected as a playback fallback.

TKINTER / VIRTUAL ENVIRONMENT FIX
---------------------------------
The v0.12 installer creates its Python environment with system site packages
enabled. This is required for Homebrew's split Tkinter package. If an older
v0.12 test environment is present, the installer detects and repairs it
automatically; no manual deletion is required.

FIRST-LAUNCH SECURITY NOTE
--------------------------
The app is currently unsigned/not notarized. Depending on macOS security
settings, the first launch may require Control-clicking the app, choosing Open,
and confirming Open.

DATA / SETTINGS
---------------
The technical application identity remains music-library-player. Existing user
data stays under:

       ~/.config/music-library-player

The GitHub repository remains:

       https://github.com/mikehellyer/music-library-player

The same install.sh supports both macOS and Linux and detects the operating
system automatically.
