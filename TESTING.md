# Simple Music Library Player - v0.11 Pre-release Testing

Use `run-test.sh` to test the new branding without replacing the installed
release or changing the live configuration in `~/.config/music-library-player`.

```bash
chmod +x run-test.sh
./run-test.sh
```

The test build uses a private `.test-home` containing a copy of the current
Music Library Player configuration/cache.

## Check the v0.11 rename

- Window title says **Simple Music Library Player**.
- Header says **Simple Music Library Player** and still uses the existing icon.
- Version shows **v0.11**.
- The window starts maximized.
- Library, playlists, favourites, recent history and cache still load normally.
- The internal config path remains `~/.config/music-library-player` inside the sandbox.

## Update-notice simulation

Because the published GitHub release is currently v0.10, run:

```bash
./run-test.sh --simulate-update
```

The temporary copy reports itself as v0.9, allowing the real v0.10 release to
exercise the passive startup notification. There should be no automatic popup
and the **Check for Updates** button must not visibly change state until you
press it yourself.

## Technical identity intentionally unchanged

These remain unchanged in v0.11:

- GitHub repository: `mikehellyer/music-library-player`
- App ID: `music-library-player`
- Install directory: `~/.local/share/music-library-player`
- Config directory: `~/.config/music-library-player`
- Launcher filename: `music-library-player.desktop`
