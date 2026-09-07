# Music Library Player - Pre-release Testing

## 1. Safe local v0.10 test

```bash
chmod +x run-test.sh
./run-test.sh
```

The script uses a private `.test-home` and copies the current Music Library
Player config/cache into it. The installed application and the real
`~/.config/music-library-player` are not modified.

Confirm:
- the header shows **v0.10**;
- the application starts maximized while retaining the normal title bar/window controls;
- the existing application icon remains before the program name;
- the **Now Playing** panel is compact;
- artwork, title, album, progress/seek and playback controls remain usable;
- existing configured folders and cached tracks load normally.

## 2. Passive startup update notification

After v0.10 is published, this helper can safely simulate an older v0.9 client:

```bash
./run-test.sh --simulate-update
```

The temporary copy reports itself as v0.9 and talks to the real GitHub release.

Confirm:
- startup displays **no update popup**;
- **Check for Updates** is not disabled, depressed, or otherwise touched by the silent check;
- the bottom-left displays `Update v0.10 available — click Check for Updates`;
- normal player/library status changes do not remove that update notice;
- clicking **Check for Updates** then displays the normal update choice.

If **Yes** is chosen, the update is installed only inside `.test-home`, not over
the normal installed application.

## 3. Playback and library regression

Confirm:
- play/pause/resume/seek/previous/next/stop work;
- queue progression works;
- Artists & Albums browse correctly;
- All Tracks/Search works;
- Check for Changes and Full Rescan work;
- favourites/playlists/history/play counts remain available in the sandbox.

## 4. Before publishing

Build the release package, test `install.sh --update` in an isolated HOME,
verify SHA-256, and only then publish the GitHub release.
