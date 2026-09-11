# Simple Music Library Player - v0.12 Testing

## Linux local test

Use the normal isolated test runner:

```bash
chmod +x run-test.sh
./run-test.sh
```

It uses a private `.test-home` containing a copy of the current configuration,
so the installed application and live `~/.config/music-library-player` are not
modified.

After v0.12 is published, updater notification can be exercised with:

```bash
./run-test.sh --simulate-update
```

The temporary copy identifies itself as v0.11 so the real v0.12 release appears
newer. Expected behaviour: no automatic popup; bottom-left update notice only;
manual **Check for Updates** click displays the update choice.

## macOS install test

1. Extract `Simple_Music_Library_Player_v0.12_Installer.zip`.
2. Double-click `Install Simple Music Library Player.command`.
3. Confirm installation to `~/Applications/Simple Music Library Player.app`.
4. Confirm the app launches from Finder.
5. Confirm library browsing, artwork and playback work.
6. Confirm existing data under `~/.config/music-library-player` remains present.

The v0.12 macOS installer has been tested on a real Mac. The revised installer
fixes Tkinter visibility in Homebrew-based private virtual environments by using
`--system-site-packages` and repairs the earlier test environment automatically.

## Update test on macOS

For a future v0.13 release, leave v0.12 installed, allow the passive notice to
appear, then click **Check for Updates** manually. The updater should download
the universal installer, verify SHA-256, reinstall the app under `~/Applications`
and reopen it.
