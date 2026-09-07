#!/usr/bin/env python3
"""
Music Library Player v0.7

A standalone Linux digital music library/player.

Highlights:
- Add one or more existing music folders
- Recursive music scanning
- Artist -> Album -> Track browser
- Local / embedded album artwork
- Full-library search view
- Now Playing queue
- Play album, add album/track to queue
- mpv-first playback with pause / resume
- Remembers music folder locations between launches

Configuration:
    ~/.config/music-library-player/library.json
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import os
import shutil
import socket
import subprocess
import threading
import tempfile
import time
import tkinter as tk
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

APP_NAME = "Music Library Player"
APP_VERSION = "0.9"

CONFIG_DIR = Path.home() / ".config" / "music-library-player"
CONFIG_FILE = CONFIG_DIR / "library.json"
USER_DATA_FILE = CONFIG_DIR / "user_data.json"
LIBRARY_CACHE_FILE = CONFIG_DIR / "library_cache.json"
APP_ID = "music-library-player"
INSTALL_DIR = Path.home() / ".local" / "share" / APP_ID
INSTALLED_SCRIPT = INSTALL_DIR / "music_library_player.py"
APP_ICON_FILE = Path(__file__).resolve().with_name("music-library-player.png")
HEADER_ICON_FILE = Path(__file__).resolve().with_name("music-library-player-48.png")
GITHUB_REPO = "mikehellyer/music-library-player"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UPDATE_USER_AGENT = f"Music-Library-Player/{APP_VERSION}"

AUDIO_EXTS = {
    ".mp3", ".flac", ".m4a", ".mp4", ".aac",
    ".ogg", ".oga", ".opus", ".wav", ".wma",
    ".aif", ".aiff", ".ape",
}

COVER_FILENAMES = (
    "cover.jpg", "cover.jpeg", "cover.png",
    "folder.jpg", "folder.jpeg", "folder.png",
    "front.jpg", "front.jpeg", "front.png",
    "album.jpg", "album.jpeg", "album.png",
)

try:
    import mutagen
    from mutagen import File as MutagenFile
    HAVE_MUTAGEN = True
    MUTAGEN_VERSION = getattr(mutagen, "version_string", getattr(mutagen, "version", "unknown"))
    MUTAGEN_PATH = getattr(mutagen, "__file__", "")
except Exception:
    mutagen = None
    MutagenFile = None
    HAVE_MUTAGEN = False
    MUTAGEN_VERSION = "not installed"
    MUTAGEN_PATH = ""

try:
    import PIL
    from PIL import Image, ImageTk
    HAVE_PIL = True
    PIL_VERSION = getattr(PIL, "__version__", "unknown")
except Exception:
    PIL = None
    Image = None
    ImageTk = None
    HAVE_PIL = False
    PIL_VERSION = "not installed"


def fmt_time(value):
    try:
        seconds = max(0, int(float(value)))
    except Exception:
        return ""
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"



def version_tuple(value):
    """Return a simple numeric tuple suitable for release-version comparisons."""
    parts = [int(x) for x in re.findall(r"\d+", str(value))]
    return tuple((parts + [0, 0, 0])[:3])


def github_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UPDATE_USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UPDATE_USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def tag_value(tags, *keys):
    if not tags:
        return ""
    for key in keys:
        try:
            value = tags.get(key)
        except Exception:
            value = None
        if value:
            if isinstance(value, (list, tuple)):
                value = value[0] if value else ""
            text = str(value).strip()
            if text:
                return text
    return ""


def track_num(value):
    try:
        return int(str(value).split("/")[0].strip())
    except Exception:
        return 0


def clean_raw_tag_value(value):
    """Turn common Mutagen raw tag objects into readable text."""
    if value is None:
        return ""

    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        value = value[0]

    # ID3 text frames
    frame_text = getattr(value, "text", None)
    if frame_text is not None:
        if isinstance(frame_text, (list, tuple)):
            return str(frame_text[0]).strip() if frame_text else ""
        return str(frame_text).strip()

    # ASF values and similar wrappers
    raw_value = getattr(value, "value", None)
    if raw_value is not None and not isinstance(raw_value, (bytes, bytearray)):
        return str(raw_value).strip()

    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8", "replace").strip()
        except Exception:
            return ""

    return str(value).strip()


def raw_tag_value(tags, *keys):
    if not tags:
        return ""

    # Direct key lookup first.
    for key in keys:
        try:
            if key in tags:
                text = clean_raw_tag_value(tags[key])
                if text:
                    return text
        except Exception:
            pass

    # Case-insensitive lookup for containers such as Vorbis/ASF.
    try:
        lowered = {str(k).casefold(): k for k in tags.keys()}
        for key in keys:
            actual = lowered.get(str(key).casefold())
            if actual is not None:
                text = clean_raw_tag_value(tags[actual])
                if text:
                    return text
    except Exception:
        pass

    return ""


def infer_from_library_root(path, library_roots):
    """
    Best-effort folder fallback which understands the configured library root.

    Example:
        library root:
            /home/mike/Dropbox/Music

        file:
            /home/mike/Dropbox/Music/UFO/2000 - Covenant/.../UFO - Live USA.flac

    Artist becomes the first folder under the configured root:
        UFO

    Album is normally the immediate parent folder, unless that parent looks like
    a CD/disc folder, in which case the parent above it is used.
    """
    p = Path(path)

    matching_root = None
    relative_parts = None

    # Use the most specific configured root containing the file.
    roots = []
    for raw_root in library_roots or []:
        try:
            root = Path(raw_root).expanduser().resolve()
            roots.append(root)
        except Exception:
            pass

    roots.sort(key=lambda r: len(r.parts), reverse=True)

    for root in roots:
        try:
            rel = p.resolve().relative_to(root)
            matching_root = root
            relative_parts = rel.parts
            break
        except Exception:
            continue

    # Artist: first directory below the configured library root.
    artist = ""
    if relative_parts and len(relative_parts) >= 2:
        artist = relative_parts[0]

    # Album: use the immediate parent, except for disc/CD subfolders.
    parent = p.parent
    album = parent.name

    parent_name = parent.name.casefold().replace("_", " ").replace("-", " ").strip()
    disc_like = (
        parent_name.startswith("disc ")
        or parent_name.startswith("disk ")
        or parent_name.startswith("cd ")
        or parent_name.startswith("disc")
        or parent_name.startswith("disk")
        or parent_name.startswith("cd")
    )

    if disc_like and parent.parent != parent:
        album = parent.parent.name

    # If there was no matching configured root, fall back to the older
    # two-level folder assumption, but only as a last resort.
    if not artist:
        if parent.parent != parent:
            artist = parent.parent.name

    if not artist or artist in {"/", "\\"}:
        artist = "Unknown Artist"
    if not album or album in {"/", "\\"}:
        album = "Unknown Album"

    return artist, album, str(matching_root) if matching_root else ""




def album_key(track):
    return (track.get("artist", "Unknown Artist"), track.get("album", "Unknown Album"))


class MusicLibraryPlayer(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1320x790")
        self.minsize(1050, 650)

        # Use the existing Music Library Player icon when it is present beside
        # the installed program. Updates never replace the user's icon unless
        # an icon file is explicitly included in the release package.
        try:
            if APP_ICON_FILE.exists():
                self._app_icon = tk.PhotoImage(file=str(APP_ICON_FILE))
                self.iconphoto(True, self._app_icon)
        except Exception:
            self._app_icon = None

        self.folders = []
        self.tracks = []
        self.filtered = []
        self.artist_names = []
        self.album_groups = {}
        self.current_album_tracks = []

        # Queue
        self.queue = []
        self.queue_index = None

        # User library data
        self.favourites = set()
        self.playlists = {}
        self.recent_paths = []
        self.play_counts = {}
        self.track_by_path = {}
        self.collection_view_tracks = []

        # Player
        self.player_kind, self.player_path = self.find_player()
        self.proc = None
        self.mpv_socket = None
        self.current_path = None
        self.current_track = None
        self.paused = False
        self.scan_id = 0
        self.expected_stop = False
        self.play_counted_this_play = False
        self.progress_after_id = None
        self.seek_dragging = False

        # Artwork
        self.art_photo = None
        self.art_cache = {}
        self.now_art_photo = None

        # Vars
        self.status = tk.StringVar(value="Ready")
        # A persistent, passive startup-update notice.  This is deliberately
        # separate from the general status text so library scans/playback do not
        # overwrite the fact that a newer release is available.
        self.update_notice = tk.StringVar(value="")
        self.now_playing = tk.StringVar(value="Nothing playing")
        self.search = tk.StringVar()
        self.folder_text = tk.StringVar(value="No music folders added yet.")
        self.count_text = tk.StringVar(value="0 tracks")
        self.queue_text = tk.StringVar(value="Queue: empty")
        self.album_title_text = tk.StringVar(value="Select an album")
        self.album_info_text = tk.StringVar(value="")
        self.engine_text = tk.StringVar(
            value=f"Player: {self.player_kind}" if self.player_kind else "Player: not found"
        )

        self.now_title_text = tk.StringVar(value="Nothing playing")
        self.now_album_text = tk.StringVar(value="")
        self.elapsed_text = tk.StringVar(value="0:00")
        self.remaining_text = tk.StringVar(value="-0:00")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.favourite_button_text = tk.StringVar(value="☆ Favourite")

        self.load_config()
        self.load_user_data()
        cached_tracks = self.load_library_cache()
        self.build_ui()
        self.search.trace_add("write", lambda *_: self.apply_filter())
        self.protocol("WM_DELETE_WINDOW", self.close)

        if cached_tracks:
            self.install_library_tracks(cached_tracks)
            self.status.set(
                f"Loaded {len(cached_tracks):,} cached tracks — checking for changes…"
            )

        if not self.player_kind:
            self.after(300, self.no_player_warning)

        if not HAVE_MUTAGEN and os.sys.executable != "/usr/bin/python3":
            self.after(500, self.python_environment_warning)

        if self.folders:
            # The cached library is already usable at this point. This scan is
            # incremental and only re-reads metadata for changed/new files.
            self.after(700, self.scan_library)

        # Quietly check GitHub after startup.  If a newer release exists, only
        # show a passive bottom-left notice.  The user explicitly clicks Check
        # for Updates before any update dialogue is shown.
        self.after(2200, lambda: self.check_for_updates(silent=True))

    # ----------------------------------------------------------
    # Configuration
    # ----------------------------------------------------------
    def load_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            values = data.get("folders", [])
            if isinstance(values, list):
                self.folders = list(
                    dict.fromkeys(
                        str(x).strip() for x in values if str(x).strip()
                    )
                )
        except Exception:
            self.folders = []

    def save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"folders": self.folders}, indent=2),
            encoding="utf-8",
        )
        tmp.replace(CONFIG_FILE)

    def load_user_data(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not USER_DATA_FILE.exists():
            return

        try:
            data = json.loads(USER_DATA_FILE.read_text(encoding="utf-8"))

            favourites = data.get("favourites", [])
            if isinstance(favourites, list):
                self.favourites = {str(path) for path in favourites if str(path)}

            playlists = data.get("playlists", {})
            if isinstance(playlists, dict):
                cleaned = {}
                for name, paths in playlists.items():
                    if not str(name).strip() or not isinstance(paths, list):
                        continue
                    cleaned[str(name).strip()] = [
                        str(path) for path in paths if str(path)
                    ]
                self.playlists = cleaned

            recent = data.get("recent", [])
            if isinstance(recent, list):
                self.recent_paths = [str(path) for path in recent if str(path)][:100]

            counts = data.get("play_counts", {})
            if isinstance(counts, dict):
                self.play_counts = {
                    str(path): int(value)
                    for path, value in counts.items()
                    if str(path)
                    and isinstance(value, (int, float))
                    and int(value) >= 0
                }
        except Exception:
            self.favourites = set()
            self.playlists = {}
            self.recent_paths = []
            self.play_counts = {}

    def save_user_data(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = USER_DATA_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "favourites": sorted(self.favourites),
                    "playlists": self.playlists,
                    "recent": self.recent_paths[:100],
                    "play_counts": self.play_counts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(USER_DATA_FILE)

    def register_recent_play(self, track):
        path = track.get("path", "")
        if not path:
            return
        self.recent_paths = [item for item in self.recent_paths if item != path]
        self.recent_paths.insert(0, path)
        self.recent_paths = self.recent_paths[:100]
        self.save_user_data()
        if hasattr(self, "collection_list"):
            self.refresh_collection_tracks()

    def register_play_count(self, track):
        if self.play_counted_this_play:
            return
        path = track.get("path", "")
        if not path:
            return
        self.play_counts[path] = int(self.play_counts.get(path, 0)) + 1
        self.play_counted_this_play = True
        self.save_user_data()
        if hasattr(self, "collection_list"):
            self.refresh_collection_tracks()

    def is_favourite(self, track):
        return bool(track and track.get("path") in self.favourites)

    def toggle_favourite(self, track=None):
        track = track or self.current_track
        if not track:
            return

        path = track.get("path", "")
        if not path:
            return

        if path in self.favourites:
            self.favourites.remove(path)
            self.status.set("Removed from favourites")
        else:
            self.favourites.add(path)
            self.status.set("Added to favourites")

        self.save_user_data()
        self.update_favourite_button()
        self.refresh_collection_tracks()

    def update_favourite_button(self):
        if self.current_track and self.current_track.get("path") in self.favourites:
            self.favourite_button_text.set("★ Favourite")
        else:
            self.favourite_button_text.set("☆ Favourite")

    def prompt_add_tracks_to_playlist(self, tracks):
        tracks = [track for track in tracks if track and track.get("path")]
        if not tracks:
            return

        existing = ", ".join(sorted(self.playlists)) or "none yet"
        name = simpledialog.askstring(
            "Add to Playlist",
            "Playlist name:\n\n"
            f"Existing playlists: {existing}\n\n"
            "Enter an existing name or type a new one:",
            parent=self,
        )
        if name is None:
            return

        name = name.strip()
        if not name:
            return

        paths = self.playlists.setdefault(name, [])
        added = 0
        for track in tracks:
            path = track["path"]
            if path not in paths:
                paths.append(path)
                added += 1

        self.save_user_data()
        self.refresh_collection_source_list(select_name=name)
        self.status.set(
            f"Added {added} track{'' if added == 1 else 's'} to {name}"
        )

    # ----------------------------------------------------------
    # Persistent library index
    # ----------------------------------------------------------
    def load_library_cache(self):
        """
        Load the previous scan immediately.

        The cache is safe to ignore if it is missing/corrupt. A background
        incremental scan checks the real folders after the UI appears.
        """
        if not LIBRARY_CACHE_FILE.exists():
            return []

        try:
            data = json.loads(LIBRARY_CACHE_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return []

            tracks = data.get("tracks", [])
            if not isinstance(tracks, list):
                return []

            cleaned = []
            configured_roots = [
                str(Path(folder).expanduser().resolve())
                for folder in self.folders
            ]

            for track in tracks:
                if not isinstance(track, dict):
                    continue
                path = str(track.get("path", "")).strip()
                if not path:
                    continue

                # Only show cached tracks that still belong to one of the
                # currently configured library folders.
                belongs = False
                try:
                    resolved = Path(path).resolve()
                    for root_name in configured_roots:
                        try:
                            resolved.relative_to(Path(root_name))
                            belongs = True
                            break
                        except Exception:
                            continue
                except Exception:
                    pass

                if belongs:
                    cleaned.append(track)

            cleaned.sort(
                key=lambda t: (
                    str(t.get("artist", "")).casefold(),
                    str(t.get("album", "")).casefold(),
                    int(t.get("disc", 0) or 0),
                    int(t.get("track_number", 0) or 0),
                    str(t.get("title", "")).casefold(),
                    str(t.get("path", "")).casefold(),
                )
            )
            return cleaned
        except Exception:
            return []

    def save_library_cache(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = LIBRARY_CACHE_FILE.with_suffix(".tmp")

        payload = {
            "version": 1,
            "folders": self.folders,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tracks": self.tracks,
        }

        tmp.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        tmp.replace(LIBRARY_CACHE_FILE)

    def install_library_tracks(self, tracks):
        """Install a track list into all library views."""
        self.tracks = tracks
        self.track_by_path = {
            track["path"]: track
            for track in tracks
            if track.get("path")
        }
        self.art_cache.clear()
        self.apply_filter()
        self.rebuild_artist_album_index()
        self.update_folder_text()
        self.refresh_collection_source_list()

    # ----------------------------------------------------------
    # Player
    # ----------------------------------------------------------
    @staticmethod
    def find_player():
        for kind, exe in (
            ("mpv", "mpv"),
            ("VLC", "cvlc"),
            ("VLC", "vlc"),
            ("ffplay", "ffplay"),
        ):
            path = shutil.which(exe)
            if path:
                return kind, path
        return None, None

    def cleanup_socket(self):
        if self.mpv_socket:
            try:
                Path(self.mpv_socket).unlink(missing_ok=True)
            except Exception:
                pass
            self.mpv_socket = None

    def terminate_player(self):
        self.expected_stop = True
        if self.proc:
            try:
                if self.proc.poll() is None:
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
            except Exception:
                pass
        self.proc = None
        self.cleanup_socket()

    def mpv_command(self, command):
        if (
            self.player_kind != "mpv"
            or not self.mpv_socket
            or not Path(self.mpv_socket).exists()
        ):
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.7)
                sock.connect(self.mpv_socket)
                sock.sendall((json.dumps({"command": command}) + "\n").encode("utf-8"))
                return True
        except Exception:
            return False

    def mpv_get_properties(self, properties):
        if (
            self.player_kind != "mpv"
            or not self.mpv_socket
            or not Path(self.mpv_socket).exists()
        ):
            return {}

        results = {}
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.7)
                sock.connect(self.mpv_socket)

                for request_id, prop in enumerate(properties, start=1):
                    request = {
                        "command": ["get_property", prop],
                        "request_id": request_id,
                    }
                    sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

                replies = {}
                buffer = b""
                deadline = time.monotonic() + 0.7

                while len(replies) < len(properties) and time.monotonic() < deadline:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk

                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line:
                            continue
                        try:
                            reply = json.loads(line.decode("utf-8", "replace"))
                        except Exception:
                            continue
                        rid = reply.get("request_id")
                        if rid:
                            replies[int(rid)] = reply

                for request_id, prop in enumerate(properties, start=1):
                    reply = replies.get(request_id, {})
                    if reply.get("error") == "success":
                        results[prop] = reply.get("data")
        except Exception:
            pass

        return results

    def cancel_progress_monitor(self):
        if self.progress_after_id is not None:
            try:
                self.after_cancel(self.progress_after_id)
            except Exception:
                pass
            self.progress_after_id = None

    def start_progress_monitor(self):
        self.cancel_progress_monitor()
        self.progress_after_id = self.after(800, self.update_playback_progress)

    def update_playback_progress(self):
        self.progress_after_id = None

        if not self.proc or self.proc.poll() is not None or not self.current_track:
            return

        duration = float(self.current_track.get("duration_seconds", 0) or 0)
        position = 0.0

        if self.player_kind == "mpv":
            values = self.mpv_get_properties(["time-pos", "duration", "pause"])
            if values.get("time-pos") is not None:
                position = float(values.get("time-pos") or 0)
            if values.get("duration") is not None:
                duration = float(values.get("duration") or duration)

        if duration > 0:
            self.progress_scale.configure(to=duration)
            if not self.seek_dragging:
                self.progress_var.set(min(position, duration))
            self.elapsed_text.set(fmt_time(position) or "0:00")
            self.remaining_text.set(f"-{fmt_time(max(0, duration - position)) or '0:00'}")

            if not self.play_counted_this_play:
                threshold = min(30.0, max(10.0, duration * 0.5))
                if position >= threshold:
                    self.register_play_count(self.current_track)
        else:
            self.elapsed_text.set(fmt_time(position) or "0:00")
            self.remaining_text.set("-?:??")

        self.start_progress_monitor()

    def seek_press(self, _event=None):
        self.seek_dragging = True

    def seek_release(self, _event=None):
        self.seek_dragging = False
        if self.player_kind == "mpv" and self.current_track:
            try:
                position = float(self.progress_var.get())
            except Exception:
                return
            self.mpv_command(["seek", position, "absolute"])
            self.elapsed_text.set(fmt_time(position) or "0:00")

    def play_track(self, track, queue_position=None):
        path = track.get("path", "")

        if not self.player_kind:
            self.no_player_warning()
            return

        if not Path(path).exists():
            messagebox.showerror(
                "Missing file",
                f"This track could not be found:\n\n{path}",
                parent=self,
            )
            return

        self.terminate_player()
        self.cancel_progress_monitor()
        self.expected_stop = False
        self.paused = False
        self.play_counted_this_play = False
        self.pause_btn.configure(text="⏸ Pause")
        self.current_path = path
        self.current_track = track
        self.register_recent_play(track)

        if queue_position is not None:
            self.queue_index = queue_position
        else:
            # If the track is already in the queue, keep queue navigation coherent.
            try:
                self.queue_index = next(
                    i for i, item in enumerate(self.queue)
                    if item.get("path") == path
                )
            except StopIteration:
                self.queue_index = None

        artist = track.get("artist", "")
        title = track.get("title", Path(path).stem)
        album = track.get("album", "")

        if artist:
            display = f"{artist} — {title}"
        else:
            display = title

        self.now_playing.set(f"Now playing: {display}")
        self.now_title_text.set(title)
        self.now_album_text.set(
            f"{artist}  •  {album}" if artist and album else (artist or album)
        )
        self.elapsed_text.set("0:00")
        self.remaining_text.set(
            f"-{track.get('duration', '')}" if track.get("duration") else "-?:??"
        )
        self.progress_var.set(0.0)
        if float(track.get("duration_seconds", 0) or 0) > 0:
            self.progress_scale.configure(to=float(track["duration_seconds"]))
        else:
            self.progress_scale.configure(to=1.0)
        self.update_now_playing_art(track)
        self.update_favourite_button()
        self.status.set(f"Playing from {album}" if album else "Playing")

        if self.player_kind == "mpv":
            sock = f"/tmp/music-library-player-{os.getpid()}.sock"
            try:
                Path(sock).unlink(missing_ok=True)
            except Exception:
                pass
            self.mpv_socket = sock
            cmd = [
                self.player_path,
                "--no-video",
                "--really-quiet",
                "--no-terminal",
                "--force-window=no",
                f"--input-ipc-server={sock}",
                path,
            ]
        elif self.player_kind == "VLC":
            cmd = [
                self.player_path,
                "--intf", "dummy",
                "--no-video",
                "--quiet",
                path,
            ]
        else:
            cmd = [
                self.player_path,
                "-nodisp",
                "-autoexit",
                "-loglevel", "error",
                path,
            ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.highlight_current_everywhere()
            self.refresh_queue_tree()
            self.start_progress_monitor()
            self.after(900, self.watch_player)
        except Exception as exc:
            self.proc = None
            messagebox.showerror("Playback error", str(exc), parent=self)

    def watch_player(self):
        process = self.proc
        if not process:
            return

        if process.poll() is None:
            self.after(900, self.watch_player)
            return

        self.proc = None
        self.cancel_progress_monitor()
        self.cleanup_socket()

        if self.expected_stop:
            self.expected_stop = False
            return

        # Natural completion counts as a play even for non-mpv players.
        if self.current_track and not self.play_counted_this_play:
            self.register_play_count(self.current_track)

        # Natural track end: prefer the Now Playing queue.
        if self.queue and self.queue_index is not None:
            next_index = self.queue_index + 1
            if next_index < len(self.queue):
                self.play_track(self.queue[next_index], queue_position=next_index)
                return

        self.current_path = None
        self.current_track = None
        self.queue_index = None
        self.now_playing.set("Nothing playing")
        self.now_title_text.set("Nothing playing")
        self.now_album_text.set("")
        self.elapsed_text.set("0:00")
        self.remaining_text.set("-0:00")
        self.progress_var.set(0.0)
        self.show_now_art_placeholder()
        self.update_favourite_button()
        self.status.set("Playback finished")
        self.refresh_queue_tree()

    def toggle_pause(self):
        if not self.proc or self.proc.poll() is not None:
            return

        if self.player_kind == "mpv" and self.mpv_command(["cycle", "pause"]):
            self.paused = not self.paused
            self.pause_btn.configure(
                text="▶ Resume" if self.paused else "⏸ Pause"
            )
            self.status.set("Paused" if self.paused else "Playing")
            return

        messagebox.showinfo(
            "Pause",
            "Pause/resume is available with mpv.\n\n"
            "Install it with:\n\nsudo apt install mpv",
            parent=self,
        )

    def stop(self):
        self.cancel_progress_monitor()
        self.terminate_player()
        self.current_path = None
        self.current_track = None
        self.queue_index = None
        self.paused = False
        self.pause_btn.configure(text="⏸ Pause")
        self.now_playing.set("Nothing playing")
        self.now_title_text.set("Nothing playing")
        self.now_album_text.set("")
        self.elapsed_text.set("0:00")
        self.remaining_text.set("-0:00")
        self.progress_var.set(0.0)
        self.show_now_art_placeholder()
        self.update_favourite_button()
        self.status.set("Stopped")
        self.refresh_queue_tree()

    def previous(self):
        if self.queue and self.queue_index is not None and self.queue_index > 0:
            self.play_track(
                self.queue[self.queue_index - 1],
                queue_position=self.queue_index - 1,
            )
            return

        # Fall back to current album.
        if self.current_track and self.current_album_tracks:
            paths = [t["path"] for t in self.current_album_tracks]
            try:
                idx = paths.index(self.current_track["path"])
            except ValueError:
                return
            if idx > 0:
                self.play_track(self.current_album_tracks[idx - 1])

    def next(self):
        if self.queue and self.queue_index is not None:
            next_index = self.queue_index + 1
            if next_index < len(self.queue):
                self.play_track(
                    self.queue[next_index],
                    queue_position=next_index,
                )
                return

        # Fall back to current album.
        if self.current_track and self.current_album_tracks:
            paths = [t["path"] for t in self.current_album_tracks]
            try:
                idx = paths.index(self.current_track["path"])
            except ValueError:
                return
            if idx + 1 < len(self.current_album_tracks):
                self.play_track(self.current_album_tracks[idx + 1])

    # ----------------------------------------------------------
    # Queue
    # ----------------------------------------------------------
    def set_queue_and_play(self, tracks, start_index=0):
        if not tracks:
            return
        self.queue = list(tracks)
        start_index = max(0, min(start_index, len(self.queue) - 1))
        self.queue_index = start_index
        self.refresh_queue_tree()
        self.play_track(self.queue[start_index], queue_position=start_index)

    def add_tracks_to_queue(self, tracks):
        if not tracks:
            return
        self.queue.extend(tracks)
        self.refresh_queue_tree()
        self.status.set(
            f"Added {len(tracks)} track{'' if len(tracks) == 1 else 's'} to queue"
        )

    def clear_queue(self):
        self.queue = []
        self.queue_index = None
        self.refresh_queue_tree()
        self.status.set("Queue cleared")

    def remove_queue_selected(self):
        selected = self.queue_tree.selection()
        if not selected:
            return

        indexes = sorted((int(item) for item in selected), reverse=True)
        for idx in indexes:
            if 0 <= idx < len(self.queue):
                del self.queue[idx]

        if self.queue_index is not None:
            if not self.queue:
                self.queue_index = None
            elif self.queue_index >= len(self.queue):
                self.queue_index = len(self.queue) - 1

        self.refresh_queue_tree()

    def play_queue_selected(self):
        selected = self.queue_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        if 0 <= idx < len(self.queue):
            self.play_track(self.queue[idx], queue_position=idx)

    def move_queue_item(self, direction):
        selected = self.queue_tree.selection()
        if not selected:
            return

        idx = int(selected[0])
        new_idx = idx + direction
        if not (0 <= new_idx < len(self.queue)):
            return

        self.queue[idx], self.queue[new_idx] = self.queue[new_idx], self.queue[idx]

        if self.queue_index == idx:
            self.queue_index = new_idx
        elif self.queue_index == new_idx:
            self.queue_index = idx

        self.refresh_queue_tree(select_index=new_idx)

    def refresh_queue_tree(self, select_index=None):
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)

        for idx, track in enumerate(self.queue):
            marker = "▶" if idx == self.queue_index and self.current_path else ""
            self.queue_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    marker,
                    track.get("artist", ""),
                    track.get("title", ""),
                ),
            )

        if select_index is not None and self.queue_tree.exists(str(select_index)):
            self.queue_tree.selection_set(str(select_index))
            self.queue_tree.focus(str(select_index))
            self.queue_tree.see(str(select_index))

        if self.queue:
            self.queue_text.set(f"Queue: {len(self.queue)} tracks")
        else:
            self.queue_text.set("Queue: empty")

    # ----------------------------------------------------------
    # Music folder management
    # ----------------------------------------------------------
    def add_folder(self):
        chosen = filedialog.askdirectory(
            title="Choose your music folder",
            mustexist=True,
            parent=self,
        )
        if not chosen:
            return

        chosen = str(Path(chosen).expanduser().resolve())
        if chosen not in self.folders:
            self.folders.append(chosen)
            self.save_config()

        self.update_folder_text()
        self.scan_library()

    def manage_folders(self):
        win = tk.Toplevel(self)
        win.title("Music Library Folders")
        win.geometry("760x370")
        win.transient(self)
        win.grab_set()

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Folders included in the library:",
        ).pack(anchor="w", pady=(0, 8))

        box = tk.Listbox(frame)
        box.pack(fill="both", expand=True)

        def refresh():
            box.delete(0, "end")
            for path in self.folders:
                box.insert("end", path)

        def add():
            chosen = filedialog.askdirectory(
                title="Choose your music folder",
                mustexist=True,
                parent=win,
            )
            if not chosen:
                return
            chosen = str(Path(chosen).expanduser().resolve())
            if chosen not in self.folders:
                self.folders.append(chosen)
                self.save_config()
                refresh()
                self.update_folder_text()

        def remove():
            selected = box.curselection()
            if not selected:
                return
            idx = selected[0]
            path = self.folders[idx]
            if messagebox.askyesno(
                "Remove folder",
                f"Stop including this folder?\n\n{path}\n\n"
                "No music files will be deleted.",
                parent=win,
            ):
                del self.folders[idx]
                self.save_config()
                refresh()
                self.update_folder_text()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))

        ttk.Button(buttons, text="Add Folder…", command=add).pack(side="left")
        ttk.Button(
            buttons,
            text="Remove Selected",
            command=remove,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            buttons,
            text="Close and Rescan",
            command=lambda: (win.destroy(), self.scan_library()),
        ).pack(side="right")

        refresh()

    # ----------------------------------------------------------
    # Scanning and metadata
    # ----------------------------------------------------------
    def scan_library(self, full_rescan=False):
        self.scan_id += 1
        generation = self.scan_id
        folders = list(self.folders)

        self.scan_btn.configure(state="disabled")
        if hasattr(self, "full_scan_btn"):
            self.full_scan_btn.configure(state="disabled")

        self.status.set(
            "Performing full library rescan…"
            if full_rescan
            else "Checking library for changes…"
        )

        # Snapshot the previous index so the worker does not touch Tk state.
        cached_by_path = {
            track.get("path"): dict(track)
            for track in self.tracks
            if track.get("path")
        }

        def worker():
            files = []
            seen = set()

            # os.walk is noticeably quicker than Path.rglob for large trees.
            for root_name in folders:
                root = Path(root_name)
                if not root.is_dir():
                    continue

                try:
                    for dirpath, _dirnames, filenames in os.walk(root):
                        if generation != self.scan_id:
                            return

                        for filename in filenames:
                            suffix = Path(filename).suffix.lower()
                            if suffix not in AUDIO_EXTS:
                                continue

                            path = str(Path(dirpath, filename).resolve())
                            if path not in seen:
                                seen.add(path)
                                files.append(path)
                except Exception:
                    pass

            tracks = []
            total = len(files)
            reused = 0
            refreshed = 0

            for number, path in enumerate(files, 1):
                if generation != self.scan_id:
                    return

                stat_size = None
                stat_mtime_ns = None
                try:
                    stat = os.stat(path)
                    stat_size = int(stat.st_size)
                    stat_mtime_ns = int(stat.st_mtime_ns)
                except Exception:
                    pass

                old = cached_by_path.get(path)
                unchanged = (
                    not full_rescan
                    and old is not None
                    and old.get("_size") == stat_size
                    and old.get("_mtime_ns") == stat_mtime_ns
                )

                if unchanged:
                    track = old
                    reused += 1
                else:
                    track = self.metadata(path)
                    track["_size"] = stat_size
                    track["_mtime_ns"] = stat_mtime_ns
                    refreshed += 1

                tracks.append(track)

                if number % 100 == 0 or number == total:
                    self.after(
                        0,
                        lambda number=number, total=total, reused=reused, refreshed=refreshed:
                        self.status.set(
                            f"Checking library… {number:,}/{total:,}  "
                            f"cached {reused:,}  updated {refreshed:,}"
                        ),
                    )

            tracks.sort(
                key=lambda t: (
                    t["artist"].casefold(),
                    t["album"].casefold(),
                    t["disc"],
                    t["track_number"],
                    t["title"].casefold(),
                    t["path"].casefold(),
                )
            )

            self.after(
                0,
                lambda: self.scan_complete(
                    generation,
                    tracks,
                    reused=reused,
                    refreshed=refreshed,
                    full_rescan=full_rescan,
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def metadata(self, path):
        p = Path(path)

        inferred_artist, inferred_album, inferred_root = infer_from_library_root(
            path,
            self.folders,
        )

        result = {
            "path": path,
            "filename": p.name,
            "title": p.stem,
            "artist": inferred_artist,
            "album": inferred_album,
            "album_artist": "",
            "track_number": 0,
            "disc": 0,
            "duration": "",
            "duration_seconds": 0.0,
            "artist_source": "folder fallback",
            "album_source": "folder fallback",
            "title_source": "filename",
            "library_root": inferred_root,
            "tag_keys": [],
        }

        if not HAVE_MUTAGEN:
            return result

        # ------------------------------------------------------
        # Pass 1: Mutagen easy tags
        # ------------------------------------------------------
        try:
            easy_audio = MutagenFile(path, easy=True)
        except Exception:
            easy_audio = None

        if easy_audio is not None:
            try:
                tags = getattr(easy_audio, "tags", None)

                easy_title = tag_value(tags, "title")
                easy_artist = tag_value(
                    tags,
                    "artist",
                    "albumartist",
                    "album artist",
                )
                easy_album_artist = tag_value(
                    tags,
                    "albumartist",
                    "album artist",
                )
                easy_album = tag_value(tags, "album")
                easy_track = tag_value(tags, "tracknumber", "track")
                easy_disc = tag_value(tags, "discnumber", "disc")

                if easy_title:
                    result["title"] = easy_title
                    result["title_source"] = "Mutagen easy tag"

                if easy_artist:
                    result["artist"] = easy_artist
                    result["artist_source"] = "Mutagen easy tag"

                if easy_album_artist:
                    result["album_artist"] = easy_album_artist

                if easy_album:
                    result["album"] = easy_album
                    result["album_source"] = "Mutagen easy tag"

                if easy_track:
                    result["track_number"] = track_num(easy_track)

                if easy_disc:
                    result["disc"] = track_num(easy_disc)

                info = getattr(easy_audio, "info", None)
                if info is not None:
                    length = getattr(info, "length", None)
                    if length:
                        result["duration_seconds"] = float(length)
                        result["duration"] = fmt_time(length)
            except Exception:
                pass

        # ------------------------------------------------------
        # Pass 2: raw tags
        # ------------------------------------------------------
        try:
            raw_audio = MutagenFile(path, easy=False)
        except Exception:
            raw_audio = None

        if raw_audio is not None:
            try:
                tags = getattr(raw_audio, "tags", None)

                try:
                    if tags:
                        result["tag_keys"] = [str(k) for k in list(tags.keys())[:30]]
                except Exception:
                    result["tag_keys"] = []

                raw_title = raw_tag_value(
                    tags,
                    "TIT2",
                    "TITLE",
                    "Title",
                    "\xa9nam",
                )
                raw_artist = raw_tag_value(
                    tags,
                    "TPE1",
                    "TPE2",
                    "ARTIST",
                    "Artist",
                    "WM/AlbumArtist",
                    "WM/Album Artist",
                    "\xa9ART",
                    "aART",
                )
                raw_album_artist = raw_tag_value(
                    tags,
                    "TPE2",
                    "ALBUMARTIST",
                    "ALBUM ARTIST",
                    "WM/AlbumArtist",
                    "WM/Album Artist",
                    "aART",
                )
                raw_album = raw_tag_value(
                    tags,
                    "TALB",
                    "ALBUM",
                    "Album",
                    "WM/AlbumTitle",
                    "\xa9alb",
                )
                raw_track = raw_tag_value(
                    tags,
                    "TRCK",
                    "TRACKNUMBER",
                    "TRACK",
                    "WM/TrackNumber",
                    "trkn",
                )
                raw_disc = raw_tag_value(
                    tags,
                    "TPOS",
                    "DISCNUMBER",
                    "DISC",
                    "disk",
                )

                # Raw tags only replace fallback values or filename values.
                if raw_title and result["title_source"] == "filename":
                    result["title"] = raw_title
                    result["title_source"] = "Mutagen raw tag"

                if raw_artist and result["artist_source"] == "folder fallback":
                    result["artist"] = raw_artist
                    result["artist_source"] = "Mutagen raw tag"

                if raw_album_artist and not result["album_artist"]:
                    result["album_artist"] = raw_album_artist

                if raw_album and result["album_source"] == "folder fallback":
                    result["album"] = raw_album
                    result["album_source"] = "Mutagen raw tag"

                if raw_track and not result["track_number"]:
                    result["track_number"] = track_num(raw_track)

                if raw_disc and not result["disc"]:
                    result["disc"] = track_num(raw_disc)

                info = getattr(raw_audio, "info", None)
                if info is not None and result["duration_seconds"] <= 0:
                    length = getattr(info, "length", None)
                    if length:
                        result["duration_seconds"] = float(length)
                        result["duration"] = fmt_time(length)

            except Exception:
                pass

        # Final safety
        if not str(result["artist"]).strip():
            result["artist"] = inferred_artist
            result["artist_source"] = "folder fallback"

        if not str(result["album"]).strip():
            result["album"] = inferred_album
            result["album_source"] = "folder fallback"

        if not str(result["title"]).strip():
            result["title"] = p.stem
            result["title_source"] = "filename"

        return result

    def scan_complete(
        self,
        generation,
        tracks,
        reused=0,
        refreshed=0,
        full_rescan=False,
    ):
        if generation != self.scan_id:
            return

        self.install_library_tracks(tracks)
        self.scan_btn.configure(state="normal")
        if hasattr(self, "full_scan_btn"):
            self.full_scan_btn.configure(state="normal")

        self.save_library_cache()

        if tracks:
            if full_rescan:
                self.status.set(
                    f"Full rescan complete — {len(tracks):,} tracks"
                )
            elif refreshed == 0:
                self.status.set(
                    f"Library ready — {len(tracks):,} tracks, no changes"
                )
            else:
                self.status.set(
                    f"Library ready — {len(tracks):,} tracks  •  "
                    f"{refreshed:,} new/changed  •  {reused:,} from cache"
                )
        elif self.folders:
            self.status.set("No supported music files found")
        else:
            self.status.set("Add a music folder to get started")

    # ----------------------------------------------------------
    # Artist / album index
    # ----------------------------------------------------------
    def rebuild_artist_album_index(self):
        groups = defaultdict(list)

        for track in self.tracks:
            groups[album_key(track)].append(track)

        for key, tracks in groups.items():
            tracks.sort(
                key=lambda t: (
                    t.get("disc", 0),
                    t.get("track_number", 0),
                    t.get("title", "").casefold(),
                )
            )

        self.album_groups = dict(groups)
        self.artist_names = sorted(
            {artist for artist, _album in self.album_groups},
            key=str.casefold,
        )

        self.artist_list.delete(0, "end")
        for artist in self.artist_names:
            self.artist_list.insert("end", artist)

        self.album_list.delete(0, "end")
        self.album_track_tree.delete(*self.album_track_tree.get_children())
        self.current_album_tracks = []
        self.album_title_text.set("Select an album")
        self.album_info_text.set("")
        self.show_art_placeholder("Album artwork")

        if self.artist_names:
            self.artist_list.selection_set(0)
            self.artist_list.activate(0)
            self.on_artist_selected()

    def on_artist_selected(self, _event=None):
        selected = self.artist_list.curselection()
        if not selected:
            return

        artist = self.artist_names[selected[0]]
        albums = sorted(
            [
                album
                for (group_artist, album) in self.album_groups
                if group_artist == artist
            ],
            key=str.casefold,
        )

        self.current_artist_albums = albums
        self.album_list.delete(0, "end")

        for album in albums:
            self.album_list.insert("end", album)

        self.album_track_tree.delete(*self.album_track_tree.get_children())
        self.current_album_tracks = []
        self.album_title_text.set(artist)
        self.album_info_text.set("")
        self.show_art_placeholder("Select an album")

        if albums:
            self.album_list.selection_set(0)
            self.album_list.activate(0)
            self.on_album_selected()

    def on_album_selected(self, _event=None):
        artist_sel = self.artist_list.curselection()
        album_sel = self.album_list.curselection()

        if not artist_sel or not album_sel:
            return

        artist = self.artist_names[artist_sel[0]]
        album = self.current_artist_albums[album_sel[0]]
        tracks = list(self.album_groups.get((artist, album), []))
        self.current_album_tracks = tracks

        self.album_title_text.set(album)

        total_seconds = sum(
            float(track.get("duration_seconds", 0) or 0) for track in tracks
        )
        album_info = f"{artist}  •  {len(tracks)} track{'' if len(tracks) == 1 else 's'}"
        if total_seconds > 0:
            album_info += f"  •  {fmt_time(total_seconds)}"
        self.album_info_text.set(album_info)

        for item in self.album_track_tree.get_children():
            self.album_track_tree.delete(item)

        for idx, track in enumerate(tracks):
            self.album_track_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    track.get("track_number") or "",
                    track.get("title", ""),
                    track.get("duration", ""),
                ),
            )

        self.load_album_art(tracks)
        self.highlight_current_everywhere()

    def album_play(self):
        if self.current_album_tracks:
            self.set_queue_and_play(self.current_album_tracks, 0)

    def album_add_to_queue(self):
        self.add_tracks_to_queue(self.current_album_tracks)

    def selected_album_track(self):
        selected = self.album_track_tree.selection()
        if not selected:
            return None
        idx = int(selected[0])
        if 0 <= idx < len(self.current_album_tracks):
            return self.current_album_tracks[idx]
        return None

    def album_play_selected_track(self):
        selected = self.album_track_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        if 0 <= idx < len(self.current_album_tracks):
            # Playing from the album creates an album queue starting at that track.
            self.set_queue_and_play(self.current_album_tracks, idx)

    def album_add_selected_track(self):
        selected = self.album_track_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        if 0 <= idx < len(self.current_album_tracks):
            self.add_tracks_to_queue([self.current_album_tracks[idx]])

    def show_now_art_placeholder(self, text="No artwork"):
        if not hasattr(self, "now_art_label"):
            return
        self.now_art_photo = None
        self.now_art_label.configure(image="", text=text)

    def update_now_playing_art(self, track):
        if not hasattr(self, "now_art_label"):
            return
        if not track or not HAVE_PIL:
            self.show_now_art_placeholder()
            return

        try:
            image_path = self.find_local_cover([track])
            if image_path:
                image = Image.open(image_path)
            else:
                image_bytes = self.embedded_art_bytes(track["path"])
                if not image_bytes:
                    self.show_now_art_placeholder()
                    return
                image = Image.open(io.BytesIO(image_bytes))

            image.thumbnail((100, 100))
            photo = ImageTk.PhotoImage(image.copy())
            self.now_art_photo = photo
            self.now_art_label.configure(image=photo, text="")
        except Exception:
            self.show_now_art_placeholder()

    # ----------------------------------------------------------
    # Album artwork
    # ----------------------------------------------------------
    def show_art_placeholder(self, text="No artwork"):
        self.art_photo = None
        self.art_label.configure(image="", text=text)

    def load_album_art(self, tracks):
        if not tracks:
            self.show_art_placeholder()
            return

        key = album_key(tracks[0])
        if key in self.art_cache:
            cached = self.art_cache[key]
            if cached is None:
                self.show_art_placeholder()
            else:
                self.art_photo = cached
                self.art_label.configure(image=self.art_photo, text="")
            return

        if not HAVE_PIL:
            self.art_cache[key] = None
            self.show_art_placeholder(
                "Album artwork\n\nInstall python3-pil"
            )
            return

        image_bytes = None
        image_path = self.find_local_cover(tracks)

        try:
            if image_path:
                image = Image.open(image_path)
            else:
                image_bytes = self.embedded_art_bytes(tracks[0]["path"])
                if not image_bytes:
                    self.art_cache[key] = None
                    self.show_art_placeholder()
                    return
                image = Image.open(io.BytesIO(image_bytes))

            image.thumbnail((270, 270))
            photo = ImageTk.PhotoImage(image.copy())
            self.art_cache[key] = photo
            self.art_photo = photo
            self.art_label.configure(image=photo, text="")
        except Exception:
            self.art_cache[key] = None
            self.show_art_placeholder()

    @staticmethod
    def find_local_cover(tracks):
        directories = []
        for track in tracks[:5]:
            directory = Path(track["path"]).parent
            if directory not in directories:
                directories.append(directory)

        for directory in directories:
            for filename in COVER_FILENAMES:
                candidate = directory / filename
                if candidate.exists() and candidate.is_file():
                    return str(candidate)

            # Case-insensitive fallback for common artwork names.
            try:
                image_files = {
                    p.name.casefold(): p
                    for p in directory.iterdir()
                    if p.is_file()
                    and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
                }
                for filename in COVER_FILENAMES:
                    match = image_files.get(filename.casefold())
                    if match:
                        return str(match)
            except Exception:
                pass

        return None

    @staticmethod
    def embedded_art_bytes(path):
        if not HAVE_MUTAGEN:
            return None

        try:
            audio = MutagenFile(path, easy=False)
            if audio is None:
                return None

            # FLAC native picture blocks.
            pictures = getattr(audio, "pictures", None)
            if pictures:
                for picture in pictures:
                    data = getattr(picture, "data", None)
                    if data:
                        return bytes(data)

            tags = getattr(audio, "tags", None)
            if not tags:
                return None

            # MP3 / ID3 APIC and older PIC frames.
            try:
                for key in tags.keys():
                    key_text = str(key)
                    if key_text.startswith("APIC") or key_text.startswith("PIC"):
                        frame = tags[key]
                        data = getattr(frame, "data", None)
                        if data:
                            return bytes(data)
            except Exception:
                pass

            # MP4 / M4A cover atom.
            try:
                covers = tags.get("covr")
                if covers:
                    return bytes(covers[0])
            except Exception:
                pass

            # Ogg/Vorbis/Opus METADATA_BLOCK_PICTURE.
            try:
                import base64
                import struct

                values = None
                for candidate in ("metadata_block_picture", "METADATA_BLOCK_PICTURE"):
                    values = tags.get(candidate)
                    if values:
                        break

                if values:
                    encoded = values[0] if isinstance(values, (list, tuple)) else values
                    block = base64.b64decode(encoded)
                    # FLAC picture block:
                    # type(4), mime_len(4), mime, desc_len(4), desc,
                    # width(4), height(4), depth(4), colors(4), data_len(4), data
                    offset = 4
                    mime_len = struct.unpack(">I", block[offset:offset+4])[0]
                    offset += 4 + mime_len
                    desc_len = struct.unpack(">I", block[offset:offset+4])[0]
                    offset += 4 + desc_len
                    offset += 16
                    data_len = struct.unpack(">I", block[offset:offset+4])[0]
                    offset += 4
                    if data_len > 0:
                        return block[offset:offset+data_len]
            except Exception:
                pass

            # WMA / ASF WM/Picture.
            try:
                pictures = tags.get("WM/Picture")
                if pictures:
                    raw = pictures[0]
                    value = getattr(raw, "value", raw)
                    if isinstance(value, (bytes, bytearray)):
                        data = bytes(value)

                        # ASF WM/Picture layout:
                        # type byte, data size DWORD, UTF-16LE mime, UTF-16LE desc, data
                        if len(data) > 10:
                            pos = 5

                            def skip_utf16z(buf, start):
                                i = start
                                while i + 1 < len(buf):
                                    if buf[i:i+2] == b"\x00\x00":
                                        return i + 2
                                    i += 2
                                return len(buf)

                            pos = skip_utf16z(data, pos)
                            pos = skip_utf16z(data, pos)
                            if pos < len(data):
                                return data[pos:]
            except Exception:
                pass

        except Exception:
            pass

        return None

    # ----------------------------------------------------------
    # Full library / search
    # ----------------------------------------------------------
    def apply_filter(self):
        query = self.search.get().strip().casefold()

        if not query:
            self.filtered = list(self.tracks)
        else:
            self.filtered = [
                track
                for track in self.tracks
                if query in track["artist"].casefold()
                or query in track["album"].casefold()
                or query in track["title"].casefold()
                or query in track["filename"].casefold()
            ]

        self.refresh_tree()

    def selected_all_track(self):
        selected = self.tree.selection()
        if not selected:
            return None
        idx = int(selected[0])
        if 0 <= idx < len(self.filtered):
            return self.filtered[idx]
        return None

    def play_all_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        if 0 <= idx < len(self.filtered):
            self.set_queue_and_play(self.filtered, idx)

    def add_all_selected_to_queue(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        if 0 <= idx < len(self.filtered):
            self.add_tracks_to_queue([self.filtered[idx]])

    # ----------------------------------------------------------
    # Favourites / playlists / history
    # ----------------------------------------------------------
    def refresh_collection_source_list(self, select_name=None):
        if not hasattr(self, "collection_list"):
            return

        current = select_name
        if current is None:
            selection = self.collection_list.curselection()
            if selection:
                current = self.collection_list.get(selection[0])

        values = [
            "★ Favourites",
            "🕘 Recently Played",
            "🏆 Most Played",
        ] + sorted(self.playlists, key=str.casefold)

        self.collection_list.delete(0, "end")
        for value in values:
            self.collection_list.insert("end", value)

        index = 0
        if current in values:
            index = values.index(current)

        if values:
            self.collection_list.selection_set(index)
            self.collection_list.activate(index)

        self.refresh_collection_tracks()

    def current_collection_name(self):
        if not hasattr(self, "collection_list"):
            return ""
        selection = self.collection_list.curselection()
        if not selection:
            return ""
        return self.collection_list.get(selection[0])

    def paths_to_tracks(self, paths):
        return [
            self.track_by_path[path]
            for path in paths
            if path in self.track_by_path
        ]

    def refresh_collection_tracks(self):
        if not hasattr(self, "collection_tree"):
            return

        name = self.current_collection_name()

        if name == "★ Favourites":
            tracks = self.paths_to_tracks(
                sorted(
                    self.favourites,
                    key=lambda path: (
                        self.track_by_path.get(path, {}).get("artist", "").casefold(),
                        self.track_by_path.get(path, {}).get("album", "").casefold(),
                        self.track_by_path.get(path, {}).get("title", "").casefold(),
                    ),
                )
            )
        elif name == "🕘 Recently Played":
            tracks = self.paths_to_tracks(self.recent_paths)
        elif name == "🏆 Most Played":
            paths = sorted(
                self.play_counts,
                key=lambda path: (
                    -int(self.play_counts.get(path, 0)),
                    self.track_by_path.get(path, {}).get("artist", "").casefold(),
                    self.track_by_path.get(path, {}).get("title", "").casefold(),
                ),
            )
            tracks = self.paths_to_tracks(paths)
        else:
            tracks = self.paths_to_tracks(self.playlists.get(name, []))

        self.collection_view_tracks = tracks

        for item in self.collection_tree.get_children():
            self.collection_tree.delete(item)

        for idx, track in enumerate(tracks):
            self.collection_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    track.get("artist", ""),
                    track.get("album", ""),
                    track.get("title", ""),
                    int(self.play_counts.get(track.get("path", ""), 0)),
                ),
            )

    def selected_collection_track(self):
        selected = self.collection_tree.selection()
        if not selected:
            return None
        idx = int(selected[0])
        if 0 <= idx < len(self.collection_view_tracks):
            return self.collection_view_tracks[idx]
        return None

    def play_collection_selected_track(self):
        track = self.selected_collection_track()
        if not track:
            return
        idx = self.collection_view_tracks.index(track)
        self.set_queue_and_play(self.collection_view_tracks, idx)

    def play_current_collection(self):
        if self.collection_view_tracks:
            self.set_queue_and_play(self.collection_view_tracks, 0)

    def new_playlist(self):
        name = simpledialog.askstring(
            "New Playlist",
            "Playlist name:",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        if name in {"★ Favourites", "🕘 Recently Played", "🏆 Most Played"}:
            messagebox.showerror(
                "Reserved name",
                "Please choose a different playlist name.",
                parent=self,
            )
            return
        self.playlists.setdefault(name, [])
        self.save_user_data()
        self.refresh_collection_source_list(select_name=name)

    def delete_selected_playlist(self):
        name = self.current_collection_name()
        if not name or name in {
            "★ Favourites",
            "🕘 Recently Played",
            "🏆 Most Played",
        }:
            return

        if not messagebox.askyesno(
            "Delete Playlist",
            f"Delete playlist '{name}'?\n\nNo music files will be deleted.",
            parent=self,
        ):
            return

        self.playlists.pop(name, None)
        self.save_user_data()
        self.refresh_collection_source_list()

    def remove_selected_from_collection(self):
        track = self.selected_collection_track()
        if not track:
            return

        path = track.get("path", "")
        name = self.current_collection_name()

        if name == "★ Favourites":
            self.favourites.discard(path)
        elif name == "🕘 Recently Played":
            self.recent_paths = [item for item in self.recent_paths if item != path]
        elif name == "🏆 Most Played":
            return
        elif name in self.playlists:
            self.playlists[name] = [
                item for item in self.playlists[name] if item != path
            ]
        else:
            return

        self.save_user_data()
        self.update_favourite_button()
        self.refresh_collection_tracks()

    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------
    def build_ui(self):
        style = ttk.Style(self)
        try:
            style.configure("Title.TLabel", font=("", 18, "bold"))
            style.configure("Now.TLabel", font=("", 12, "bold"))
            style.configure("UpdateNotice.TLabel", font=("", 9, "bold"))
            style.configure("Album.TLabel", font=("", 15, "bold"))
        except Exception:
            pass

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))

        # Show the same Music Library Player icon inside the application
        # header as we use for the launcher/window/panel.
        self.header_icon = None
        try:
            if HEADER_ICON_FILE.exists():
                self.header_icon = tk.PhotoImage(file=str(HEADER_ICON_FILE))
                ttk.Label(header, image=self.header_icon).pack(
                    side="left",
                    padx=(0, 9),
                )
        except Exception:
            self.header_icon = None

        ttk.Label(
            header,
            text=APP_NAME,
            style="Title.TLabel",
        ).pack(side="left")

        ttk.Label(
            header,
            text=f"v{APP_VERSION}",
        ).pack(side="left", padx=(8, 0))

        ttk.Label(
            header,
            textvariable=self.engine_text,
        ).pack(side="right")

        # Now Playing
        player = ttk.LabelFrame(outer, text="Now Playing", padding=7)
        player.pack(fill="x", pady=(0, 10))

        now_art_box = ttk.Frame(player, width=108, height=108)
        now_art_box.pack(side="left", padx=(0, 10))
        now_art_box.pack_propagate(False)

        self.now_art_label = ttk.Label(
            now_art_box,
            text="No artwork",
            anchor="center",
            justify="center",
        )
        self.now_art_label.pack(fill="both", expand=True)

        player_info = ttk.Frame(player)
        player_info.pack(side="left", fill="both", expand=True)

        ttk.Label(
            player_info,
            textvariable=self.now_title_text,
            style="Now.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            player_info,
            textvariable=self.now_album_text,
            foreground="#666666",
        ).pack(anchor="w", pady=(2, 5))

        progress_line = ttk.Frame(player_info)
        progress_line.pack(fill="x")

        ttk.Label(
            progress_line,
            textvariable=self.elapsed_text,
            width=8,
        ).pack(side="left")

        self.progress_scale = ttk.Scale(
            progress_line,
            from_=0,
            to=1,
            variable=self.progress_var,
        )
        self.progress_scale.pack(side="left", fill="x", expand=True, padx=6)
        self.progress_scale.bind("<ButtonPress-1>", self.seek_press)
        self.progress_scale.bind("<ButtonRelease-1>", self.seek_release)

        ttk.Label(
            progress_line,
            textvariable=self.remaining_text,
            width=9,
            anchor="e",
        ).pack(side="left")

        controls = ttk.Frame(player_info)
        controls.pack(fill="x", pady=(5, 0))

        ttk.Button(
            controls,
            text="⏮ Previous",
            command=self.previous,
        ).pack(side="left")

        self.pause_btn = ttk.Button(
            controls,
            text="⏸ Pause",
            command=self.toggle_pause,
        )
        self.pause_btn.pack(side="left", padx=(6, 0))

        ttk.Button(
            controls,
            text="⏭ Next",
            command=self.next,
        ).pack(side="left", padx=(6, 0))

        ttk.Button(
            controls,
            text="■ Stop",
            command=self.stop,
        ).pack(side="left", padx=(6, 0))

        ttk.Button(
            controls,
            textvariable=self.favourite_button_text,
            command=self.toggle_favourite,
        ).pack(side="left", padx=(14, 0))

        ttk.Button(
            controls,
            text="Add to Playlist…",
            command=lambda: self.prompt_add_tracks_to_playlist(
                [self.current_track]
            ),
        ).pack(side="left", padx=(6, 0))

        # Folder actions
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))

        ttk.Button(
            actions,
            text="Add Music Folder…",
            command=self.add_folder,
        ).pack(side="left")

        ttk.Button(
            actions,
            text="Manage Folders…",
            command=self.manage_folders,
        ).pack(side="left", padx=(6, 0))

        self.scan_btn = ttk.Button(
            actions,
            text="Check for Changes",
            command=self.scan_library,
        )
        self.scan_btn.pack(side="left", padx=(6, 0))

        self.full_scan_btn = ttk.Button(
            actions,
            text="Full Rescan",
            command=lambda: self.scan_library(full_rescan=True),
        )
        self.full_scan_btn.pack(side="left", padx=(6, 0))

        ttk.Button(
            actions,
            text="Metadata Diagnostics",
            command=self.show_metadata_diagnostics,
        ).pack(side="left", padx=(6, 0))

        self.update_btn = ttk.Button(
            actions,
            text="Check for Updates",
            command=lambda: self.check_for_updates(silent=False),
        )
        self.update_btn.pack(side="left", padx=(6, 0))

        ttk.Label(
            actions,
            textvariable=self.folder_text,
            foreground="#666666",
        ).pack(side="left", padx=(12, 0))

        # Main split: browser + queue
        main_panes = ttk.Panedwindow(outer, orient="horizontal")
        main_panes.pack(fill="both", expand=True)

        browser_frame = ttk.Frame(main_panes)
        queue_frame = ttk.LabelFrame(main_panes, text="Now Playing Queue", padding=8)

        main_panes.add(browser_frame, weight=4)
        main_panes.add(queue_frame, weight=1)

        # Notebook
        self.notebook = ttk.Notebook(browser_frame)
        self.notebook.pack(fill="both", expand=True)

        self.browse_tab = ttk.Frame(self.notebook, padding=8)
        self.all_tab = ttk.Frame(self.notebook, padding=8)
        self.collections_tab = ttk.Frame(self.notebook, padding=8)

        self.notebook.add(self.browse_tab, text="Artists & Albums")
        self.notebook.add(self.all_tab, text="All Tracks / Search")
        self.notebook.add(self.collections_tab, text="Playlists & History")

        self.build_artist_album_tab()
        self.build_all_tracks_tab()
        self.build_collections_tab()
        self.build_queue(queue_frame)

        # Status
        statusbar = ttk.Frame(outer)
        statusbar.pack(fill="x", pady=(8, 0))

        # Startup update checks are passive: when a newer release exists this
        # notice remains at the bottom-left until the user chooses Check for
        # Updates.  General player/library status appears beside it.
        ttk.Label(
            statusbar,
            textvariable=self.update_notice,
            style="UpdateNotice.TLabel",
        ).pack(side="left")

        ttk.Label(
            statusbar,
            textvariable=self.status,
        ).pack(side="left", padx=(10, 0))

        notes = []
        notes.append(
            f"Mutagen {MUTAGEN_VERSION}"
            if HAVE_MUTAGEN
            else "install python3-mutagen for tags"
        )
        notes.append(
            f"Pillow {PIL_VERSION}"
            if HAVE_PIL
            else "install python3-pil for artwork"
        )

        ttk.Label(
            statusbar,
            text=" • ".join(notes),
            foreground="#666666",
        ).pack(side="right")

        self.update_folder_text()

    def build_artist_album_tab(self):
        panes = ttk.Panedwindow(self.browse_tab, orient="horizontal")
        panes.pack(fill="both", expand=True)

        artist_frame = ttk.LabelFrame(panes, text="Artists", padding=6)
        album_frame = ttk.LabelFrame(panes, text="Albums", padding=6)
        detail_frame = ttk.Frame(panes)

        panes.add(artist_frame, weight=1)
        panes.add(album_frame, weight=1)
        panes.add(detail_frame, weight=4)

        # Artists
        artist_scroll = ttk.Scrollbar(artist_frame, orient="vertical")
        self.artist_list = tk.Listbox(
            artist_frame,
            exportselection=False,
            yscrollcommand=artist_scroll.set,
        )
        artist_scroll.configure(command=self.artist_list.yview)

        self.artist_list.pack(side="left", fill="both", expand=True)
        artist_scroll.pack(side="right", fill="y")
        self.artist_list.bind("<<ListboxSelect>>", self.on_artist_selected)

        # Albums
        album_scroll = ttk.Scrollbar(album_frame, orient="vertical")
        self.album_list = tk.Listbox(
            album_frame,
            exportselection=False,
            yscrollcommand=album_scroll.set,
        )
        album_scroll.configure(command=self.album_list.yview)

        self.album_list.pack(side="left", fill="both", expand=True)
        album_scroll.pack(side="right", fill="y")
        self.album_list.bind("<<ListboxSelect>>", self.on_album_selected)

        # Album detail
        top = ttk.Frame(detail_frame)
        top.pack(fill="x", pady=(0, 8))

        art_box = ttk.LabelFrame(top, text="Artwork", padding=8)
        art_box.pack(side="left", anchor="n")

        self.art_label = ttk.Label(
            art_box,
            text="Album artwork",
            anchor="center",
            justify="center",
            width=34,
        )
        self.art_label.pack()

        album_header = ttk.Frame(top, padding=(12, 8))
        album_header.pack(side="left", fill="both", expand=True)

        ttk.Label(
            album_header,
            textvariable=self.album_title_text,
            style="Album.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            album_header,
            textvariable=self.album_info_text,
            foreground="#666666",
        ).pack(anchor="w", pady=(4, 12))

        ttk.Button(
            album_header,
            text="▶ Play Album",
            command=self.album_play,
        ).pack(anchor="w")

        ttk.Button(
            album_header,
            text="Add Album to Queue",
            command=self.album_add_to_queue,
        ).pack(anchor="w", pady=(6, 0))

        ttk.Button(
            album_header,
            text="Add Album to Playlist…",
            command=lambda: self.prompt_add_tracks_to_playlist(
                self.current_album_tracks
            ),
        ).pack(anchor="w", pady=(6, 0))

        # Album tracks
        track_frame = ttk.LabelFrame(
            detail_frame,
            text="Album Tracks",
            padding=6,
        )
        track_frame.pack(fill="both", expand=True)

        tree_frame = ttk.Frame(track_frame)
        tree_frame.pack(fill="both", expand=True)

        self.album_track_tree = ttk.Treeview(
            tree_frame,
            columns=("num", "title", "length"),
            show="headings",
            selectmode="browse",
        )

        self.album_track_tree.heading("num", text="#")
        self.album_track_tree.heading("title", text="Track")
        self.album_track_tree.heading("length", text="Length")

        self.album_track_tree.column("num", width=48, stretch=False)
        self.album_track_tree.column("title", width=480, minwidth=220)
        self.album_track_tree.column("length", width=80, stretch=False)

        scroll = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.album_track_tree.yview,
        )
        self.album_track_tree.configure(yscrollcommand=scroll.set)

        self.album_track_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.album_track_tree.bind(
            "<Double-1>",
            lambda _e: self.album_play_selected_track(),
        )
        self.album_track_tree.bind(
            "<Return>",
            lambda _e: self.album_play_selected_track(),
        )

        buttons = ttk.Frame(track_frame)
        buttons.pack(fill="x", pady=(7, 0))

        ttk.Button(
            buttons,
            text="▶ Play Selected",
            command=self.album_play_selected_track,
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Add Selected to Queue",
            command=self.album_add_selected_track,
        ).pack(side="left", padx=(6, 0))

        ttk.Button(
            buttons,
            text="☆ Favourite",
            command=lambda: self.toggle_favourite(self.selected_album_track()),
        ).pack(side="left", padx=(12, 0))

        ttk.Button(
            buttons,
            text="Add to Playlist…",
            command=lambda: self.prompt_add_tracks_to_playlist(
                [self.selected_album_track()]
            ),
        ).pack(side="left", padx=(6, 0))

    def build_all_tracks_tab(self):
        searchbar = ttk.Frame(self.all_tab)
        searchbar.pack(fill="x", pady=(0, 8))

        ttk.Label(searchbar, text="Search:").pack(side="left")

        ttk.Entry(
            searchbar,
            textvariable=self.search,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        ttk.Button(
            searchbar,
            text="Clear",
            command=lambda: self.search.set(""),
        ).pack(side="left", padx=(6, 0))

        library = ttk.LabelFrame(
            self.all_tab,
            text="Complete Music Library",
            padding=8,
        )
        library.pack(fill="both", expand=True)

        treeframe = ttk.Frame(library)
        treeframe.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            treeframe,
            columns=("artist", "album", "num", "title", "length"),
            show="headings",
            selectmode="browse",
        )

        for col, title in (
            ("artist", "Artist"),
            ("album", "Album"),
            ("num", "#"),
            ("title", "Track"),
            ("length", "Length"),
        ):
            self.tree.heading(col, text=title)

        self.tree.column("artist", width=190, minwidth=110)
        self.tree.column("album", width=230, minwidth=120)
        self.tree.column("num", width=46, stretch=False)
        self.tree.column("title", width=330, minwidth=170)
        self.tree.column("length", width=75, stretch=False)

        scroll = ttk.Scrollbar(
            treeframe,
            orient="vertical",
            command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tree.bind(
            "<Double-1>",
            lambda _e: self.play_all_selected(),
        )
        self.tree.bind(
            "<Return>",
            lambda _e: self.play_all_selected(),
        )

        bottom = ttk.Frame(library)
        bottom.pack(fill="x", pady=(8, 0))

        ttk.Button(
            bottom,
            text="▶ Play Selected",
            command=self.play_all_selected,
        ).pack(side="left")

        ttk.Button(
            bottom,
            text="Add Selected to Queue",
            command=self.add_all_selected_to_queue,
        ).pack(side="left", padx=(6, 0))

        ttk.Button(
            bottom,
            text="☆ Favourite",
            command=lambda: self.toggle_favourite(self.selected_all_track()),
        ).pack(side="left", padx=(12, 0))

        ttk.Button(
            bottom,
            text="Add to Playlist…",
            command=lambda: self.prompt_add_tracks_to_playlist(
                [self.selected_all_track()]
            ),
        ).pack(side="left", padx=(6, 0))

        ttk.Label(
            bottom,
            textvariable=self.count_text,
            foreground="#666666",
        ).pack(side="right")

    def build_collections_tab(self):
        panes = ttk.Panedwindow(self.collections_tab, orient="horizontal")
        panes.pack(fill="both", expand=True)

        sources = ttk.LabelFrame(panes, text="Collections", padding=8)
        tracks = ttk.LabelFrame(panes, text="Tracks", padding=8)
        panes.add(sources, weight=1)
        panes.add(tracks, weight=4)

        self.collection_list = tk.Listbox(
            sources,
            exportselection=False,
        )
        self.collection_list.pack(fill="both", expand=True)
        self.collection_list.bind(
            "<<ListboxSelect>>",
            lambda _e: self.refresh_collection_tracks(),
        )

        source_buttons = ttk.Frame(sources)
        source_buttons.pack(fill="x", pady=(8, 0))

        ttk.Button(
            source_buttons,
            text="New Playlist…",
            command=self.new_playlist,
        ).pack(fill="x")

        ttk.Button(
            source_buttons,
            text="Delete Playlist",
            command=self.delete_selected_playlist,
        ).pack(fill="x", pady=(5, 0))

        tree_frame = ttk.Frame(tracks)
        tree_frame.pack(fill="both", expand=True)

        self.collection_tree = ttk.Treeview(
            tree_frame,
            columns=("artist", "album", "title", "plays"),
            show="headings",
            selectmode="browse",
        )
        self.collection_tree.heading("artist", text="Artist")
        self.collection_tree.heading("album", text="Album")
        self.collection_tree.heading("title", text="Track")
        self.collection_tree.heading("plays", text="Plays")
        self.collection_tree.column("artist", width=170, minwidth=100)
        self.collection_tree.column("album", width=210, minwidth=110)
        self.collection_tree.column("title", width=330, minwidth=160)
        self.collection_tree.column("plays", width=60, stretch=False)

        scroll = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.collection_tree.yview,
        )
        self.collection_tree.configure(yscrollcommand=scroll.set)
        self.collection_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.collection_tree.bind(
            "<Double-1>",
            lambda _e: self.play_collection_selected_track(),
        )
        self.collection_tree.bind(
            "<Return>",
            lambda _e: self.play_collection_selected_track(),
        )

        bottom = ttk.Frame(tracks)
        bottom.pack(fill="x", pady=(8, 0))

        ttk.Button(
            bottom,
            text="▶ Play Collection",
            command=self.play_current_collection,
        ).pack(side="left")

        ttk.Button(
            bottom,
            text="Add Collection to Queue",
            command=lambda: self.add_tracks_to_queue(self.collection_view_tracks),
        ).pack(side="left", padx=(6, 0))

        ttk.Button(
            bottom,
            text="Remove Selected",
            command=self.remove_selected_from_collection,
        ).pack(side="left", padx=(14, 0))

        ttk.Button(
            bottom,
            text="☆ Favourite",
            command=lambda: self.toggle_favourite(
                self.selected_collection_track()
            ),
        ).pack(side="left", padx=(6, 0))

        self.refresh_collection_source_list()

    def build_queue(self, parent):
        ttk.Label(
            parent,
            textvariable=self.queue_text,
            foreground="#666666",
        ).pack(anchor="w", pady=(0, 6))

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True)

        self.queue_tree = ttk.Treeview(
            tree_frame,
            columns=("playing", "artist", "title"),
            show="headings",
            selectmode="browse",
        )

        self.queue_tree.heading("playing", text="")
        self.queue_tree.heading("artist", text="Artist")
        self.queue_tree.heading("title", text="Track")

        self.queue_tree.column("playing", width=32, stretch=False)
        self.queue_tree.column("artist", width=120, minwidth=80)
        self.queue_tree.column("title", width=180, minwidth=100)

        scroll = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.queue_tree.yview,
        )
        self.queue_tree.configure(yscrollcommand=scroll.set)

        self.queue_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.queue_tree.bind(
            "<Double-1>",
            lambda _e: self.play_queue_selected(),
        )
        self.queue_tree.bind(
            "<Return>",
            lambda _e: self.play_queue_selected(),
        )

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(8, 0))

        ttk.Button(
            buttons,
            text="Play",
            command=self.play_queue_selected,
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Remove",
            command=self.remove_queue_selected,
        ).pack(side="left", padx=(5, 0))

        ttk.Button(
            buttons,
            text="Clear",
            command=self.clear_queue,
        ).pack(side="left", padx=(5, 0))

        order = ttk.Frame(parent)
        order.pack(fill="x", pady=(6, 0))

        ttk.Button(
            order,
            text="Move Up",
            command=lambda: self.move_queue_item(-1),
        ).pack(side="left")

        ttk.Button(
            order,
            text="Move Down",
            command=lambda: self.move_queue_item(1),
        ).pack(side="left", padx=(5, 0))

    # ----------------------------------------------------------
    # General UI refresh helpers
    # ----------------------------------------------------------
    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, track in enumerate(self.filtered):
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    track["artist"],
                    track["album"],
                    track["track_number"] or "",
                    track["title"],
                    track["duration"],
                ),
            )

        self.count_text.set(
            f"{len(self.filtered):,} of {len(self.tracks):,} tracks"
        )
        self.highlight_current_everywhere()

    def highlight_current_everywhere(self):
        if not self.current_path:
            return

        # All tracks view
        for idx, track in enumerate(self.filtered):
            if track["path"] == self.current_path:
                iid = str(idx)
                if self.tree.exists(iid):
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    self.tree.see(iid)
                break

        # Album tracks view
        for idx, track in enumerate(self.current_album_tracks):
            if track["path"] == self.current_path:
                iid = str(idx)
                if self.album_track_tree.exists(iid):
                    self.album_track_tree.selection_set(iid)
                    self.album_track_tree.focus(iid)
                    self.album_track_tree.see(iid)
                break

    # ----------------------------------------------------------
    # GitHub updates
    # ----------------------------------------------------------
    def check_for_updates(self, silent=False):
        if hasattr(self, "update_btn"):
            self.update_btn.configure(state="disabled")
        if not silent:
            self.status.set("Checking GitHub for updates…")

        def worker():
            try:
                release = github_json(LATEST_RELEASE_API)
                tag = str(release.get("tag_name", "")).strip()
                latest = tag.lstrip("vV")
                if not latest:
                    raise RuntimeError("The latest GitHub release has no version tag.")

                assets = {
                    str(asset.get("name", "")): str(asset.get("browser_download_url", ""))
                    for asset in release.get("assets", [])
                    if asset.get("name") and asset.get("browser_download_url")
                }

                package_name = next(
                    (
                        name for name in assets
                        if name.lower().endswith(".zip")
                        and "music_library_player" in name.lower()
                        and "installer" in name.lower()
                    ),
                    None,
                )
                checksum_name = next(
                    (
                        name for name in assets
                        if name.lower() in {"sha256sums.txt", "sha256sum.txt"}
                    ),
                    None,
                )

                result = {
                    "latest": latest,
                    "release_url": str(release.get("html_url", "")),
                    "notes": str(release.get("body", "")).strip(),
                    "package_name": package_name,
                    "package_url": assets.get(package_name, "") if package_name else "",
                    "checksum_name": checksum_name,
                    "checksum_url": assets.get(checksum_name, "") if checksum_name else "",
                }
                self.after(0, lambda: self._handle_update_check(result, silent))
            except Exception as exc:
                self.after(0, lambda: self._handle_update_error(exc, silent))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_update_error(self, exc, silent):
        if hasattr(self, "update_btn"):
            self.update_btn.configure(state="normal")
        if silent:
            # A background check must never disturb normal scan/playback status.
            return
        self.status.set("Update check failed")
        messagebox.showerror(
            "Update check failed",
            "Music Library Player could not check GitHub for updates.\n\n"
            f"{exc}",
            parent=self,
        )

    def _handle_update_check(self, result, silent):
        if hasattr(self, "update_btn"):
            self.update_btn.configure(state="normal")

        latest = result["latest"]
        if version_tuple(latest) <= version_tuple(APP_VERSION):
            self.update_notice.set("")
            if silent:
                return
            self.status.set(f"Music Library Player v{APP_VERSION} is up to date")
            messagebox.showinfo(
                "No update available",
                f"You are running the latest version: v{APP_VERSION}.",
                parent=self,
            )
            return

        # Background checks only announce the release in the bottom-left.
        # The update choice is deliberately deferred until the user presses the
        # Check for Updates button, matching Internet Radio Player behaviour.
        self.update_notice.set(
            f"Update v{latest} available — click Check for Updates"
        )
        if silent:
            return

        self.status.set(f"Music Library Player v{latest} is available")

        if not result["package_url"] or not result["checksum_url"]:
            messagebox.showinfo(
                "Update available",
                f"Music Library Player v{latest} is available on GitHub.\n\n"
                "This release does not contain the automatic-update package, so "
                "please download it from the Releases page.",
                parent=self,
            )
            return

        notes = result["notes"]
        if len(notes) > 900:
            notes = notes[:900].rstrip() + "…"
        message = (
            f"Music Library Player v{latest} is available.\n\n"
            f"You are currently running v{APP_VERSION}.\n\n"
        )
        if notes:
            message += f"{notes}\n\n"
        message += (
            "Download, verify and install this update now?\n\n"
            "Your music folders, playlists, favourites, history and library "
            "cache in ~/.config/music-library-player will be preserved."
        )

        if messagebox.askyesno("Update available", message, parent=self):
            self._install_update(result)

    def _install_update(self, result):
        if hasattr(self, "update_btn"):
            self.update_btn.configure(state="disabled")
        self.status.set(f"Downloading Music Library Player v{result['latest']}…")

        def worker():
            workdir = Path(tempfile.mkdtemp(prefix="music-library-player-update-"))
            try:
                package = workdir / result["package_name"]
                checksums = workdir / result["checksum_name"]
                download_file(result["package_url"], package)
                download_file(result["checksum_url"], checksums)

                expected = ""
                for line in checksums.read_text(encoding="utf-8", errors="replace").splitlines():
                    fields = line.strip().split()
                    if len(fields) >= 2 and fields[-1].lstrip("*") == package.name:
                        expected = fields[0].lower()
                        break
                if not expected:
                    raise RuntimeError(
                        f"No SHA-256 checksum was found for {package.name}."
                    )

                actual = hashlib.sha256(package.read_bytes()).hexdigest().lower()
                if actual != expected:
                    raise RuntimeError(
                        "The downloaded update failed SHA-256 verification and "
                        "has not been installed."
                    )

                extract_dir = workdir / "package"
                extract_dir.mkdir()
                with zipfile.ZipFile(package) as archive:
                    archive.extractall(extract_dir)

                installer = next(extract_dir.rglob("install.sh"), None)
                if installer is None:
                    raise RuntimeError("install.sh was not found in the update package.")

                completed = subprocess.run(
                    ["bash", str(installer), "--update"],
                    cwd=str(installer.parent),
                    text=True,
                    capture_output=True,
                    timeout=90,
                )
                if completed.returncode != 0:
                    details = (completed.stderr or completed.stdout or "").strip()
                    raise RuntimeError(
                        "The installer returned an error."
                        + (f"\n\n{details[-1200:]}" if details else "")
                    )

                self.after(
                    0,
                    lambda: self._finish_update(result["latest"]),
                )
            except Exception as exc:
                self.after(0, lambda: self._update_install_error(exc))
            finally:
                shutil.rmtree(workdir, ignore_errors=True)

        threading.Thread(target=worker, daemon=True).start()

    def _update_install_error(self, exc):
        if hasattr(self, "update_btn"):
            self.update_btn.configure(state="normal")
        self.status.set("Update failed")
        messagebox.showerror(
            "Update failed",
            "The update was not installed.\n\n"
            f"{exc}",
            parent=self,
        )

    def _finish_update(self, latest):
        self.status.set(f"Updated to v{latest}")
        messagebox.showinfo(
            "Update installed",
            f"Music Library Player v{latest} has been installed successfully.\n\n"
            "The player will now restart.",
            parent=self,
        )

        self.scan_id += 1
        self.cancel_progress_monitor()
        self.save_user_data()
        if self.tracks:
            try:
                self.save_library_cache()
            except Exception:
                pass
        self.terminate_player()

        try:
            subprocess.Popen(
                ["/usr/bin/python3", str(INSTALLED_SCRIPT)],
                start_new_session=True,
            )
        except Exception as exc:
            messagebox.showwarning(
                "Restart required",
                "The update was installed, but Music Library Player could not "
                "restart automatically.\n\n"
                f"{exc}\n\nPlease start it again from the Applications menu.",
                parent=self,
            )
        self.destroy()

    def update_folder_text(self):
        if not self.folders:
            self.folder_text.set("No music folders added yet.")
        elif len(self.folders) == 1:
            self.folder_text.set(f"1 music folder: {self.folders[0]}")
        else:
            self.folder_text.set(f"{len(self.folders)} music folders configured")

    def show_metadata_diagnostics(self):
        mutagen_text = (
            f"Mutagen: {MUTAGEN_VERSION}\n{MUTAGEN_PATH}"
            if HAVE_MUTAGEN
            else "Mutagen: NOT INSTALLED"
        )
        pillow_text = (
            f"Pillow: {PIL_VERSION}"
            if HAVE_PIL
            else "Pillow: NOT INSTALLED"
        )

        sample = ""
        if self.tracks:
            first = self.tracks[0]
            keys = first.get("tag_keys", [])
            keys_text = ", ".join(keys[:12]) if keys else "(none visible)"

            sample = (
                "\n\nFirst scanned track:\n"
                f"Artist: {first.get('artist', '')}\n"
                f"  source: {first.get('artist_source', '')}\n"
                f"Album: {first.get('album', '')}\n"
                f"  source: {first.get('album_source', '')}\n"
                f"Title: {first.get('title', '')}\n"
                f"  source: {first.get('title_source', '')}\n"
                f"Library root: {first.get('library_root', '') or '(no matching root)'}\n"
                f"Tag keys: {keys_text}\n"
                f"File: {first.get('path', '')}"
            )

        cache_text = (
            f"\n\nLibrary cache: {LIBRARY_CACHE_FILE}\n"
            f"Cached index present: {'yes' if LIBRARY_CACHE_FILE.exists() else 'no'}"
        )

        messagebox.showinfo(
            "Metadata Diagnostics",
            f"Python: {os.sys.version.split()[0]}\n\n"
            f"{mutagen_text}\n\n"
            f"{pillow_text}{cache_text}{sample}",
            parent=self,
        )

    def python_environment_warning(self):
        messagebox.showwarning(
            "Python environment",
            "Music Library Player is running with:\n\n"
            f"    {os.sys.executable}\n\n"
            "but Mutagen is not available in that Python environment.\n\n"
            "On Pop!_OS / Ubuntu, run the player with:\n\n"
            "    /usr/bin/python3 music_library_player.py\n\n"
            "The supplied application launcher does this automatically.",
            parent=self,
        )

    def no_player_warning(self):
        messagebox.showwarning(
            "No media player found",
            f"{APP_NAME} needs a media player.\n\n"
            "Recommended on Pop!_OS / Ubuntu:\n\n"
            "    sudo apt install mpv",
            parent=self,
        )

    def close(self):
        self.scan_id += 1
        self.cancel_progress_monitor()
        self.save_user_data()
        if self.tracks:
            try:
                self.save_library_cache()
            except Exception:
                pass
        self.terminate_player()
        self.destroy()


if __name__ == "__main__":
    MusicLibraryPlayer().mainloop()
