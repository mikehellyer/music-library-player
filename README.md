# Music Library Player

A standalone Linux music player and local-library manager for people who want to
play and organise the music files they already own.

**Current release: v0.7**

## Highlights

- Add one or more existing music folders.
- Scan folders recursively without moving or changing your music files.
- Browse Artist → Album → Track.
- Display local or embedded album artwork.
- Search the full library.
- Build and edit a Now Playing queue.
- Favourites, playlists, recently played tracks and play counts.
- Incremental library rescans with a persistent cache.
- `mpv`-first playback with pause, resume, seek, previous and next controls.
- Built-in GitHub update checker.
- Quiet update check after startup.
- One-click download, SHA-256 verification, installation and restart.

## Linux requirements

Music Library Player is developed and tested primarily for Pop!_OS / Ubuntu.

Recommended packages:

```bash
sudo apt update
sudo apt install python3-tk python3-mutagen python3-pil python3-pil.imagetk mpv
```

The player can also detect VLC/cvlc or ffplay as alternative playback engines.

## Install

Download the current release ZIP from GitHub Releases, extract it, then run:

```bash
chmod +x install.sh
./install.sh
```

The application is installed for the current user at:

```text
~/.local/share/music-library-player
```

The Applications-menu launcher is installed at:

```text
~/.local/share/applications/music-library-player.desktop
```

## Your library data is kept separate

Personal data is stored under:

```text
~/.config/music-library-player/
```

This includes the configured music folders, favourites, playlists, play history,
play counts and the library cache. Program updates do **not** overwrite this
directory.

Your music files themselves are never copied into the application directory.

## Updates

Music Library Player checks the project's GitHub Releases page shortly after
startup. You can also choose **Check for Updates** in the main window.

When a newer release is available the player can:

1. Download the installer ZIP.
2. Download `SHA256SUMS.txt`.
3. Verify the ZIP using SHA-256.
4. Run the bundled user-local installer.
5. Restart Music Library Player.

Update packages are published from:

https://github.com/mikehellyer/music-library-player/releases

## Source

Main source file:

```text
music_library_player.py
```

GitHub repository:

https://github.com/mikehellyer/music-library-player

## Project authorship

Music Library Player was designed, specified and tested by **Mike Hellyer**.

The application code was developed with the assistance of **OpenAI's ChatGPT**,
based on Mike's feature ideas, requirements, feedback and testing.

**Designed by Mike Hellyer · Developed with OpenAI ChatGPT**

## Licence

GNU General Public License v3.0. See `LICENSE`.
