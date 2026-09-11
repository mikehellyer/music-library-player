# Changelog

## v0.12

- Added supported **macOS installation** alongside Linux.
- Added a genuine **Simple Music Library Player.app** bundle with native `.icns` icon.
- Added double-clickable `Install Simple Music Library Player.command` installer.
- macOS installs the managed app to `~/Applications` so future self-updates do not require administrator privileges.
- Added Homebrew Apple Silicon (`/opt/homebrew`), Intel (`/usr/local`) and MacPorts path support.
- Added macOS playback detection for Homebrew `mpv` and `/Applications/VLC.app`.
- Added a private Python support environment for Mutagen and Pillow.
- Fixed Homebrew Tkinter visibility by creating the private environment with `--system-site-packages`.
- Installer automatically repairs the earlier v0.12 test environment if it was created without Tkinter visibility.
- Added macOS-aware updater restart which reopens the installed `.app` after a successful update.
- Retains the existing `music-library-player` technical ID, GitHub repository and `~/.config/music-library-player` data path.
- Linux installation and updater behaviour remain supported.

## v0.11

- Renamed the user-facing application to **Simple Music Library Player**.
- Kept the internal app ID, config path, install path and GitHub repository unchanged for seamless upgrades.
- Applications-menu launcher now displays the new name while retaining `music-library-player.desktop`.
- Existing desktop shortcuts are migrated to the new visible name without creating a shortcut for users who did not already have one.
- Updater explicitly accepts both old and new installer asset naming conventions.
- Retains passive startup update notifications, compact Now Playing panel and maximized startup.

## v0.10

- Startup update checks are fully passive: no popup and no visual/state change to the **Check for Updates** button.
- A newer release is announced in the bottom-left; the user explicitly clicks **Check for Updates** before any update choice appears.
- The main window starts maximized by default.
- Retains the compact **Now Playing** area introduced during v0.9 testing.

## v0.9

- Changed startup update detection to a passive bottom-left notification.
- Reduced the vertical size of the **Now Playing** area with smaller artwork and tighter spacing.
- Added a safe simulated-update mode to the local test runner.

## v0.8

- Added the existing Music Library Player vinyl/blue-note icon to the application header.
- Added the repeatable `run-test.sh` local pre-release testing workflow.
- Local tests use a private `.test-home` so installed application data is protected.

## v0.7

- First GitHub/update-enabled release.
- Added GitHub Releases integration and **Check for Updates**.
- Added SHA-256 verified one-click updates and automatic restart.
- Added a user-local installer for Pop!_OS / Ubuntu.
