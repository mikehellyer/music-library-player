# Music Library Player - Pre-release Testing

## 1. Safe local v0.9 test

```bash
chmod +x run-test.sh
./run-test.sh
```

The script uses a private `.test-home` and copies the current Music Library
Player config/cache into it. The installed application and the real
`~/.config/music-library-player` are not modified.

Confirm:
- the header shows **v0.9**;
- the existing application icon remains before the program name;
- the **Now Playing** panel is noticeably more compact;
- artwork still displays correctly;
- title, album, progress/seek and all playback buttons remain usable;
- existing configured folders and cached tracks load normally.

## 2. Passive startup update notification

When the local test build is already the same or newer than the public GitHub release,
use the simulation mode:

```bash
./run-test.sh --simulate-update
```

This creates a temporary copy of the v0.9 source which identifies itself as
v0.7 only for this test. It talks to the real GitHub repository, so the current
public release appears newer.

Confirm:
- startup does **not** display an update popup;
- the bottom-left displays `Update vX.X available — click Check for Updates`;
- normal library/player status can change without removing that update notice;
- clicking **Check for Updates** then displays the normal update choice.

You can choose **No** at the update prompt. If you choose **Yes**, the update is
installed only inside `.test-home`, not over the normal installed application.

## 3. Playback and library regression

Confirm:
- play/pause/resume/seek/previous/next/stop work;
- queue progression works;
- Artists & Albums browse correctly;
- All Tracks/Search works;
- Check for Changes and Full Rescan work;
- favourites/playlists/history/play counts remain available in the sandbox.

## 4. Before publishing

After local approval, build the release package, test `install.sh --update` in an
isolated HOME, verify SHA-256, and only then publish the next GitHub release.
