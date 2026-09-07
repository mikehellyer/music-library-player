# Music Library Player - Pre-release Testing

Use this checklist before publishing a GitHub release.

## 1. Run from the release folder

```bash
/usr/bin/python3 music_library_player.py
```

Confirm:
- the main window opens;
- the Music Library Player icon is shown;
- the version in the header matches the release;
- existing configured folders load;
- cached tracks appear before/while an incremental rescan runs.

## 2. Playback

Confirm:
- a track starts;
- pause/resume works;
- seek works;
- previous/next work;
- stop works;
- queue progression works.

## 3. Library

Confirm:
- Artists & Albums browse correctly;
- All Tracks/Search works;
- album artwork loads where available;
- **Check for Changes** works;
- **Full Rescan** works.

## 4. User data

Confirm:
- favourites survive a restart;
- playlists survive a restart;
- recently played/play counts survive a restart;
- `~/.config/music-library-player/library_cache.json` survives an install/update.

## 5. Installer

From the release folder:

```bash
chmod +x install.sh
./install.sh
```

Then launch **Music Library Player** from the Applications menu.

Confirm:
- the launcher works;
- the correct icon appears;
- the player uses `/usr/bin/python3`;
- existing user settings are unchanged.

## 6. Update checker

Before publishing a future release:
- install the previous public version;
- create the new GitHub Release and attach its ZIP and `SHA256SUMS.txt`;
- launch the old version;
- click **Check for Updates**;
- accept the update;
- confirm the checksum passes;
- confirm installation completes;
- confirm the app restarts on the new version;
- confirm user settings/library cache are still present.
