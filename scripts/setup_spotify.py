#!/usr/bin/env python
"""One-time Spotify OAuth setup. Run with: make setup-spotify"""

import sys
from pathlib import Path

# Ensure src is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from max_ai.agent.tools.spotify import SCOPES, TOKEN_PATH

from max_ai.config import settings


def main() -> None:
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        print(
            "Error: Spotify credentials not set.\n"
            "Add MAX_AI_SPOTIFY_CLIENT_ID and MAX_AI_SPOTIFY_CLIENT_SECRET to your .env file."
        )
        sys.exit(1)

    print("Setting up Spotify OAuth...")
    print(f"Token will be saved to: {TOKEN_PATH}")
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        from spotipy.oauth2 import SpotifyOAuth

        auth = SpotifyOAuth(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            redirect_uri=settings.spotify_redirect_uri,
            scope=" ".join(SCOPES),
            cache_path=str(TOKEN_PATH),
            open_browser=True,
        )

        # This triggers the OAuth flow
        token = auth.get_access_token(as_dict=False)
        if token:
            print(f"\nSuccess! Token saved to {TOKEN_PATH}")
            print("You can now use Spotify tools in max-ai.")
        else:
            print("Failed to obtain token.")
            sys.exit(1)

    except ImportError:
        print("Error: spotipy not installed. Run: uv sync")
        sys.exit(1)


if __name__ == "__main__":
    main()
