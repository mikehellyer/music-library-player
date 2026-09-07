# Changelog

## v0.8

Small visual release and first release prepared using the repeatable local-test
workflow.

### Added
- The existing Music Library Player vinyl/blue-note icon is now displayed in the
  application header immediately before the program name.
- Added `run-test.sh` for isolated local pre-release testing.
- Local test runs use a private `.test-home` so the installed application's
  configuration is not modified.

### Preserved
- GitHub update checking and one-click updater.
- Artist → Album → Track browser.
- Full-library search.
- Now Playing queue.
- Favourites and playlists.
- Recently played tracks and play counts.
- Incremental music-library scan/cache.
- Album-art display.
- mpv/VLC/ffplay playback support.

### Data safety
Updates only replace application files. The user's settings and music-library
data remain under `~/.config/music-library-player/`.

## v0.7

First GitHub/update-enabled release.

### Added
- GitHub Releases integration.
- **Check for Updates** button.
- Quiet update check shortly after startup.
- One-click update download and installation.
- SHA-256 verification of release packages.
- Automatic restart after a successful update.
- User-local installer for Pop!_OS / Ubuntu.
- Music Library Player application icon integration.
- GitHub-ready README, testing notes and release notes.

### Preserved
- Artist → Album → Track browser.
- Full-library search.
- Now Playing queue.
- Favourites and playlists.
- Recently played tracks and play counts.
- Incremental music-library scan/cache.
- Album-art display.
- mpv/VLC/ffplay playback support.
