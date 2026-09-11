# Simple Music Library Player

A straightforward desktop player for browsing and playing a local digital music
collection on **Linux and macOS**.

The user-facing name is **Simple Music Library Player**. For update and data
compatibility, its technical identity deliberately remains `music-library-player`.

## Features

- Artist → Album → Track browsing
- Full-library search
- Album artwork
- Now Playing queue
- Favourites and playlists
- Recently played tracks and play counts
- Persistent library cache and incremental rescanning
- mpv-first playback, with VLC/ffplay fallback where available
- Existing vinyl/blue-note application icon
- Passive GitHub update notification with user-initiated installation
- Starts maximized so the full library interface is visible
- Built-in SHA-256 verified updates

## Linux installation

Developed and tested primarily on Pop!_OS / Ubuntu.

Recommended packages:

```bash
sudo apt install python3-tk python3-mutagen python3-pil python3-pil.imagetk mpv
```

Then run:

```bash
chmod +x install.sh
./install.sh
```

Linux application files are installed under:

```text
~/.local/share/music-library-player
```

The Applications-menu launcher remains:

```text
~/.local/share/applications/music-library-player.desktop
```

but is displayed as **Simple Music Library Player**.

## macOS installation

v0.12 adds supported macOS installation with a genuine `.app` bundle.

Extract the installer package and double-click:

```text
Install Simple Music Library Player.command
```

The app is installed to:

```text
~/Applications/Simple Music Library Player.app
```

Recommended Homebrew dependencies:

```bash
brew install python python-tk mpv
```

The installer creates a private Python support environment under:

```text
~/Library/Application Support/music-library-player/venv
```

It uses system site packages so Homebrew's split Tkinter module remains
available inside that environment. Existing broken v0.12 test environments are
repaired automatically.

The app is currently unsigned/not notarized, so macOS may require Control-click
→ **Open** on first launch.

See `README-macOS.txt` for more detail.

## Existing settings are preserved

The Linux/macOS packaging and the visible-name change do **not** move or reset
user data. It continues to use:

```text
~/.config/music-library-player/
```

That preserves library folders, playlists, favourites, recently played history,
play counts and the library cache across updates.

## Updates

The updater uses:

https://github.com/mikehellyer/music-library-player

The updater accepts both the original installer naming convention
(`Music_Library_Player_..._Installer.zip`) and the current branding
(`Simple_Music_Library_Player_..._Installer.zip`).

The release installer is universal: its `install.sh` detects Linux or macOS.
On macOS the updater reinstalls `~/Applications/Simple Music Library Player.app`
and reopens it; on Linux it updates the existing user-local installation.

A background check is passive: if a newer release exists, a notice appears at
the bottom-left. The update/install prompt appears only after the user presses
**Check for Updates**.

## Project authorship

Simple Music Library Player was **designed, specified and tested by Mike Hellyer**.
The application code was **developed with the assistance of OpenAI's ChatGPT**,
based on Mike's feature ideas, requirements, feedback and testing.

**Designed by Mike Hellyer · Developed with OpenAI ChatGPT**
