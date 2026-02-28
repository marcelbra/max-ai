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
                name="spotify_now_playing",
                description="Get information about the currently playing track.",
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
    elif name == "spotify_now_playing":
        return _now_playing(sp)
    elif name == "spotify_queue":
        return _queue(sp, inp.get("query", ""))
    elif name == "spotify_search":
        return _search(sp, inp.get("query", ""), inp.get("type", "track"), inp.get("limit", 5))
    return f"Unknown Spotify tool: {name}"


def _get_device_id(sp: spotipy.Spotify) -> str | None:
    """Return an active device ID, falling back to the first available device."""
    devices = sp.devices().get("devices", [])
    if not devices:
        return None
    active = next((d for d in devices if d["is_active"]), None)
    return str((active or devices[0])["id"])


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
    return f"{is_playing}: {title} — {artists} ({album}) [{progress}/{duration}]"


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
