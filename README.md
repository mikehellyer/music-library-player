# Simple Music Library Player

A straightforward Linux desktop player for browsing and playing a local digital
music collection.

**Simple Music Library Player** is the new user-facing name introduced in v0.11.
For update compatibility, its technical identity deliberately remains
`music-library-player`.

## Features

- Artist → Album → Track browsing
- Full-library search
- Album artwork
- Now Playing queue
- Favourites and playlists
- Recently played tracks and play counts
- Persistent library cache and incremental rescanning
- mpv-first playback, with VLC/ffplay fallback
- Existing vinyl/blue-note application icon
- Passive GitHub update notification with user-initiated installation
- Starts maximized so the full library interface is visible

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

The application is installed under:

```text
~/.local/share/music-library-player
```

The Applications-menu launcher remains:

```text
~/.local/share/applications/music-library-player.desktop
```

but is displayed as **Simple Music Library Player**.

## Existing settings are preserved

The rename does **not** move or reset your user data. It continues to use:

```text
~/.config/music-library-player/
```

That preserves library folders, playlists, favourites, recently played history,
play counts and the library cache across the rename and future updates.

## Updates

The updater continues to use the existing GitHub repository:

https://github.com/mikehellyer/music-library-player

The updater accepts both the original installer naming convention
(`Music_Library_Player_..._Installer.zip`) and the new branding
(`Simple_Music_Library_Player_..._Installer.zip`).

A background check is passive: if a newer release exists, a notice appears at
the bottom-left. The update/install prompt is shown only after the user presses
**Check for Updates**.

## Project authorship

Simple Music Library Player was **designed, specified and tested by Mike Hellyer**.
The application code was **developed with the assistance of OpenAI's ChatGPT**,
based on Mike's feature ideas, requirements, feedback and testing.

**Designed by Mike Hellyer · Developed with OpenAI ChatGPT**
