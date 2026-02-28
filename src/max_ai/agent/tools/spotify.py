"""Spotify playback control tools via spotipy."""

from pathlib import Path
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from max_ai.agent.tools.base import BaseTool, ToolDefinition
from max_ai.config import settings

TOKEN_PATH = Path.home() / ".max-ai" / "spotify_token.json"

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-library-read",
    "user-library-modify",
    "user-read-recently-played",
]


def _get_spotify() -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=settings.spotify_redirect_uri,
        scope=" ".join(SCOPES),
        cache_path=str(TOKEN_PATH),
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth)


class SpotifyTools(BaseTool):
    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="spotify_play",
                description="Play a track, album, playlist, or artist by name. "
                "Searches Spotify and starts playback on the active device.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query, e.g. 'Bohemian Rhapsody Queen'",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["track", "album", "playlist", "artist"],
                            "description": "Type of content to search for. Default: track",
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="spotify_pause",
                description="Pause Spotify playback.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="spotify_resume",
                description="Resume Spotify playback.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="spotify_skip",
                description="Skip to the next track.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="spotify_previous",
                description="Go back to the previous track.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="spotify_volume",
                description="Set the Spotify volume.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Volume level from 0 to 100",
                        }
                    },
                    "required": ["level"],
                },
            ),
            ToolDefinition(
                name="spotify_shuffle",
                description="Enable or disable shuffle mode.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "description": "True to enable shuffle, False to disable",
                        }
                    },
                    "required": ["enabled"],
                },
            ),
            ToolDefinition(
                name="spotify_repeat",
                description=(
                    "Set repeat mode: 'track' repeats the current track, "
                    "'context' repeats the album/playlist, 'off' disables repeat."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["track", "context", "off"],
                            "description": "Repeat mode",
                        }
                    },
                    "required": ["mode"],
                },
            ),
            ToolDefinition(
                name="spotify_seek",
                description="Seek to a position in the current track.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "position_seconds": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Position in seconds to seek to",
                        }
                    },
                    "required": ["position_seconds"],
                },
            ),
            ToolDefinition(
                name="spotify_now_playing",
                description="Get information about the currently playing track.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="spotify_get_queue",
                description="View the current playback queue (up to 10 upcoming tracks).",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="spotify_queue",
                description="Add a track to the playback queue by name.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Track name to search for and queue",
                        }
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="spotify_search",
                description="Search Spotify for tracks, albums, artists, or playlists.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "type": {
                            "type": "string",
                            "enum": ["track", "album", "artist", "playlist"],
                            "description": "Content type to search. Default: track",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Number of results. Default: 5",
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="spotify_devices",
                description="List all available Spotify devices.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="spotify_transfer",
                description="Transfer playback to a different device by name.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "device_name": {
                            "type": "string",
                            "description": "Device name to transfer to (partial match supported)",
                        }
                    },
                    "required": ["device_name"],
                },
            ),
            ToolDefinition(
                name="spotify_list_playlists",
                description="List the current user's playlists.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Number of playlists to return. Default: 20",
                        }
                    },
                },
            ),
            ToolDefinition(
                name="spotify_playlist_tracks",
                description="List the tracks in one of the user's playlists.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "playlist": {
                            "type": "string",
                            "description": "Playlist name (partial match against user's playlists)",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Number of tracks to return. Default: 20",
                        },
                    },
                    "required": ["playlist"],
                },
            ),
            ToolDefinition(
                name="spotify_create_playlist",
                description="Create a new Spotify playlist.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Playlist name",
                        },
                        "description": {
                            "type": "string",
                            "description": "Playlist description",
                        },
                        "public": {
                            "type": "boolean",
                            "description": "Whether the playlist is public. Default: false",
                        },
                    },
                    "required": ["name"],
                },
            ),
            ToolDefinition(
                name="spotify_add_to_playlist",
                description="Add a track to one of the user's playlists.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "playlist": {
                            "type": "string",
                            "description": "Playlist name (partial match against user's playlists)",
                        },
                        "query": {
                            "type": "string",
                            "description": "Track name to search for and add",
                        },
                    },
                    "required": ["playlist", "query"],
                },
            ),
            ToolDefinition(
                name="spotify_remove_from_playlist",
                description="Remove a track from one of the user's playlists.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "playlist": {
                            "type": "string",
                            "description": "Playlist name (partial match against user's playlists)",
                        },
                        "query": {
                            "type": "string",
                            "description": "Track name to search for and remove",
                        },
                    },
                    "required": ["playlist", "query"],
                },
            ),
            ToolDefinition(
                name="spotify_like_track",
                description="Save/like a track. Likes the current track if no query given.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Track to like. Omit to like the current track.",
                        }
                    },
                },
            ),
            ToolDefinition(
                name="spotify_saved_tracks",
                description="Browse the user's liked/saved tracks.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Number of tracks to return. Default: 20",
                        }
                    },
                },
            ),
            ToolDefinition(
                name="spotify_recent",
                description="Get the user's recently played tracks.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Number of tracks to return. Default: 10",
                        }
                    },
                },
            ),
            ToolDefinition(
                name="spotify_recommendations",
                description="Get track recommendations based on a seed track, artist, or genre.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "seed": {
                            "type": "string",
                            "description": "Seed value: a track name, artist name, or genre string",
                        },
                        "seed_type": {
                            "type": "string",
                            "enum": ["track", "artist", "genre"],
                            "description": "What the seed refers to. Default: track",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "description": "Number of recommendations. Default: 10",
                        },
                    },
                    "required": ["seed"],
                },
            ),
            ToolDefinition(
                name="spotify_artist_top_tracks",
                description="Get the top tracks for an artist.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "artist": {
                            "type": "string",
                            "description": "Artist name",
                        }
                    },
                    "required": ["artist"],
                },
            ),
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        try:
            sp = _get_spotify()
            return await _dispatch(sp, tool_name, tool_input)
        except Exception as e:
            return f"Spotify error: {e}"


async def _dispatch(sp: spotipy.Spotify, name: str, inp: dict[str, Any]) -> str:
    if name == "spotify_play":
        return _play(sp, inp.get("query", ""), inp.get("type", "track"))
    elif name == "spotify_pause":
        sp.pause_playback()
        return "Paused."
    elif name == "spotify_resume":
        sp.start_playback()
        return "Resumed."
    elif name == "spotify_skip":
        sp.next_track()
        return "Skipped to next track."
    elif name == "spotify_previous":
        sp.previous_track()
        return "Went back to previous track."
    elif name == "spotify_volume":
        level = int(inp["level"])
        sp.volume(level)
        return f"Volume set to {level}%."
    elif name == "spotify_shuffle":
        enabled = bool(inp["enabled"])
        sp.shuffle(enabled)
        return f"Shuffle {'enabled' if enabled else 'disabled'}."
    elif name == "spotify_repeat":
        mode = inp["mode"]
        sp.repeat(mode)
        return f"Repeat set to '{mode}'."
    elif name == "spotify_seek":
        position_ms = int(inp["position_seconds"]) * 1000
        sp.seek_track(position_ms)
        return f"Seeked to {inp['position_seconds']}s."
    elif name == "spotify_now_playing":
        return _now_playing(sp)
    elif name == "spotify_get_queue":
        return _get_queue(sp)
    elif name == "spotify_queue":
        return _queue(sp, inp.get("query", ""))
    elif name == "spotify_search":
        return _search(sp, inp.get("query", ""), inp.get("type", "track"), inp.get("limit", 5))
    elif name == "spotify_devices":
        return _devices(sp)
    elif name == "spotify_transfer":
        return _transfer(sp, inp.get("device_name", ""))
    elif name == "spotify_list_playlists":
        return _list_playlists(sp, inp.get("limit", 20))
    elif name == "spotify_playlist_tracks":
        return _playlist_tracks(sp, inp.get("playlist", ""), inp.get("limit", 20))
    elif name == "spotify_create_playlist":
        return _create_playlist(
            sp, inp.get("name", ""), inp.get("description", ""), inp.get("public", False)
        )
    elif name == "spotify_add_to_playlist":
        return _add_to_playlist(sp, inp.get("playlist", ""), inp.get("query", ""))
    elif name == "spotify_remove_from_playlist":
        return _remove_from_playlist(sp, inp.get("playlist", ""), inp.get("query", ""))
    elif name == "spotify_like_track":
        return _like_track(sp, inp.get("query"))
    elif name == "spotify_saved_tracks":
        return _saved_tracks(sp, inp.get("limit", 20))
    elif name == "spotify_recent":
        return _recent(sp, inp.get("limit", 10))
    elif name == "spotify_recommendations":
        return _recommendations(
            sp, inp.get("seed", ""), inp.get("seed_type", "track"), inp.get("limit", 10)
        )
    elif name == "spotify_artist_top_tracks":
        return _artist_top_tracks(sp, inp.get("artist", ""))
    return f"Unknown Spotify tool: {name}"


def _get_device_id(sp: spotipy.Spotify) -> str | None:
    """Return an active device ID, falling back to the first available device."""
    devices = sp.devices().get("devices", [])
    if not devices:
        return None
    active = next((d for d in devices if d["is_active"]), None)
    return str((active or devices[0])["id"])


def _find_user_playlist(sp: spotipy.Spotify, name: str) -> dict[str, Any] | None:
    """Find a user playlist by partial name match."""
    results = sp.current_user_playlists(limit=50)
    items: list[dict[str, Any]] = results.get("items", [])
    name_lower = name.lower()
    # Exact match first, then partial
    exact = next((p for p in items if p["name"].lower() == name_lower), None)
    if exact:
        return exact
    return next((p for p in items if name_lower in p["name"].lower()), None)


def _play(sp: spotipy.Spotify, query: str, content_type: str) -> str:
    results = sp.search(q=query, type=content_type, limit=1)
    items_key = f"{content_type}s"
    items = results.get(items_key, {}).get("items", [])
    if not items:
        return f"No {content_type} found for '{query}'."

    item = items[0]
    uri = item["uri"]
    name = item.get("name", uri)

    device_id = _get_device_id(sp)
    if device_id is None:
        return "No Spotify devices found. Open Spotify on any device and try again."

    if content_type == "track":
        sp.start_playback(device_id=device_id, uris=[uri])
    else:
        sp.start_playback(device_id=device_id, context_uri=uri)

    return f"Playing {content_type}: {name}"


def _now_playing(sp: spotipy.Spotify) -> str:
    current = sp.current_playback()
    if not current or not current.get("item"):
        return "Nothing is currently playing."
    item = current["item"]
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    title = item.get("name", "Unknown")
    album = item.get("album", {}).get("name", "")
    is_playing = "Playing" if current.get("is_playing") else "Paused"
    progress_ms = current.get("progress_ms", 0)
    duration_ms = item.get("duration_ms", 1)
    progress = f"{progress_ms // 60000}:{(progress_ms % 60000) // 1000:02d}"
    duration = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
    shuffle = "on" if current.get("shuffle_state") else "off"
    repeat = current.get("repeat_state", "off")
    return (
        f"{is_playing}: {title} — {artists} ({album}) [{progress}/{duration}] "
        f"| shuffle: {shuffle} | repeat: {repeat}"
    )


def _get_queue(sp: spotipy.Spotify) -> str:
    result = sp.queue()
    queue_items = result.get("queue", [])[:10]
    if not queue_items:
        return "Queue is empty."
    lines = ["Upcoming tracks:"]
    for i, track in enumerate(queue_items, 1):
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        lines.append(f"  {i}. {track['name']} — {artists}")
    return "\n".join(lines)


def _queue(sp: spotipy.Spotify, query: str) -> str:
    results = sp.search(q=query, type="track", limit=1)
    items = results.get("tracks", {}).get("items", [])
    if not items:
        return f"No track found for '{query}'."
    track = items[0]
    sp.add_to_queue(track["uri"])
    return f"Queued: {track['name']} — {', '.join(a['name'] for a in track['artists'])}"


def _search(sp: spotipy.Spotify, query: str, content_type: str, limit: int) -> str:
    results = sp.search(q=query, type=content_type, limit=limit)
    items_key = f"{content_type}s"
    items = results.get(items_key, {}).get("items", [])
    if not items:
        return f"No results for '{query}'."

    lines = [f"Search results for '{query}' ({content_type}):"]
    for i, item in enumerate(items, 1):
        name = item.get("name", "?")
        if content_type == "track":
            artists = ", ".join(a["name"] for a in item.get("artists", []))
            lines.append(f"  {i}. {name} — {artists}")
        elif content_type == "artist":
            lines.append(f"  {i}. {name}")
        elif content_type == "album":
            artists = ", ".join(a["name"] for a in item.get("artists", []))
            lines.append(f"  {i}. {name} — {artists}")
        elif content_type == "playlist":
            owner = item.get("owner", {}).get("display_name", "?")
            lines.append(f"  {i}. {name} by {owner}")

    return "\n".join(lines)


def _devices(sp: spotipy.Spotify) -> str:
    devices = sp.devices().get("devices", [])
    if not devices:
        return "No devices found. Open Spotify on a device and try again."
    lines = ["Available devices:"]
    for d in devices:
        active = " (active)" if d.get("is_active") else ""
        volume = d.get("volume_percent", "?")
        lines.append(f"  - {d['name']} [{d['type']}] vol:{volume}%{active}")
    return "\n".join(lines)


def _transfer(sp: spotipy.Spotify, device_name: str) -> str:
    devices = sp.devices().get("devices", [])
    name_lower = device_name.lower()
    match = next((d for d in devices if name_lower in d["name"].lower()), None)
    if not match:
        available = ", ".join(d["name"] for d in devices) or "none"
        return f"Device '{device_name}' not found. Available: {available}"
    sp.transfer_playback(match["id"])
    return f"Playback transferred to {match['name']}."


def _list_playlists(sp: spotipy.Spotify, limit: int) -> str:
    results = sp.current_user_playlists(limit=limit)
    items = results.get("items", [])
    if not items:
        return "No playlists found."
    lines = ["Your playlists:"]
    for i, p in enumerate(items, 1):
        total = p.get("tracks", {}).get("total", "?")
        lines.append(f"  {i}. {p['name']} ({total} tracks)")
    return "\n".join(lines)


def _playlist_tracks(sp: spotipy.Spotify, name: str, limit: int) -> str:
    playlist = _find_user_playlist(sp, name)
    if not playlist:
        return f"Playlist '{name}' not found in your library."
    results = sp.playlist_tracks(playlist["id"], limit=limit)
    items = results.get("items", [])
    if not items:
        return f"Playlist '{playlist['name']}' is empty."
    lines = [f"Tracks in '{playlist['name']}':"]
    for i, item in enumerate(items, 1):
        track = item.get("track")
        if not track:
            continue
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        lines.append(f"  {i}. {track['name']} — {artists}")
    return "\n".join(lines)


def _create_playlist(sp: spotipy.Spotify, name: str, description: str, public: bool) -> str:
    user_id = sp.me()["id"]
    playlist = sp.user_playlist_create(user_id, name, public=public, description=description)
    return f"Created playlist '{playlist['name']}' (id: {playlist['id']})."


def _add_to_playlist(sp: spotipy.Spotify, playlist_name: str, query: str) -> str:
    playlist = _find_user_playlist(sp, playlist_name)
    if not playlist:
        return f"Playlist '{playlist_name}' not found in your library."
    results = sp.search(q=query, type="track", limit=1)
    tracks = results.get("tracks", {}).get("items", [])
    if not tracks:
        return f"No track found for '{query}'."
    track = tracks[0]
    sp.playlist_add_items(playlist["id"], [track["uri"]])
    artists = ", ".join(a["name"] for a in track["artists"])
    return f"Added '{track['name']} — {artists}' to '{playlist['name']}'."


def _remove_from_playlist(sp: spotipy.Spotify, playlist_name: str, query: str) -> str:
    playlist = _find_user_playlist(sp, playlist_name)
    if not playlist:
        return f"Playlist '{playlist_name}' not found in your library."
    results = sp.search(q=query, type="track", limit=1)
    tracks = results.get("tracks", {}).get("items", [])
    if not tracks:
        return f"No track found for '{query}'."
    track = tracks[0]
    sp.playlist_remove_all_occurrences_of_items(playlist["id"], [track["uri"]])
    artists = ", ".join(a["name"] for a in track["artists"])
    return f"Removed '{track['name']} — {artists}' from '{playlist['name']}'."


def _like_track(sp: spotipy.Spotify, query: str | None) -> str:
    if query:
        results = sp.search(q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"No track found for '{query}'."
        track = tracks[0]
    else:
        current = sp.current_playback()
        if not current or not current.get("item"):
            return "Nothing is currently playing."
        track = current["item"]
    sp.current_user_saved_tracks_add([track["uri"]])
    artists = ", ".join(a["name"] for a in track.get("artists", []))
    return f"Liked '{track['name']} — {artists}'."


def _saved_tracks(sp: spotipy.Spotify, limit: int) -> str:
    results = sp.current_user_saved_tracks(limit=limit)
    items = results.get("items", [])
    if not items:
        return "No saved tracks found."
    lines = ["Your liked tracks:"]
    for i, item in enumerate(items, 1):
        track = item["track"]
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        lines.append(f"  {i}. {track['name']} — {artists}")
    return "\n".join(lines)


def _recent(sp: spotipy.Spotify, limit: int) -> str:
    results = sp.current_user_recently_played(limit=limit)
    items = results.get("items", [])
    if not items:
        return "No recently played tracks."
    lines = ["Recently played:"]
    for i, item in enumerate(items, 1):
        track = item["track"]
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        lines.append(f"  {i}. {track['name']} — {artists}")
    return "\n".join(lines)


def _recommendations(sp: spotipy.Spotify, seed: str, seed_type: str, limit: int) -> str:
    seed_tracks: list[str] = []
    seed_artists: list[str] = []
    seed_genres: list[str] = []

    if seed_type == "genre":
        seed_genres = [seed]
    elif seed_type == "artist":
        results = sp.search(q=seed, type="artist", limit=1)
        artists = results.get("artists", {}).get("items", [])
        if not artists:
            return f"Artist '{seed}' not found."
        seed_artists = [artists[0]["id"]]
    else:
        results = sp.search(q=seed, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"Track '{seed}' not found."
        seed_tracks = [tracks[0]["id"]]

    recs = sp.recommendations(
        seed_tracks=seed_tracks,
        seed_artists=seed_artists,
        seed_genres=seed_genres,
        limit=limit,
    )
    tracks = recs.get("tracks", [])
    if not tracks:
        return "No recommendations found."
    lines = [f"Recommendations based on {seed_type} '{seed}':"]
    for i, track in enumerate(tracks, 1):
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        lines.append(f"  {i}. {track['name']} — {artists}")
    return "\n".join(lines)


def _artist_top_tracks(sp: spotipy.Spotify, artist_name: str) -> str:
    results = sp.search(q=artist_name, type="artist", limit=1)
    artists = results.get("artists", {}).get("items", [])
    if not artists:
        return f"Artist '{artist_name}' not found."
    artist = artists[0]
    top = sp.artist_top_tracks(artist["id"])
    tracks = top.get("tracks", [])
    if not tracks:
        return f"No top tracks found for '{artist['name']}'."
    lines = [f"Top tracks for {artist['name']}:"]
    for i, track in enumerate(tracks, 1):
        lines.append(f"  {i}. {track['name']}")
    return "\n".join(lines)
