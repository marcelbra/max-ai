"""Tests for Settings."""

from max_ai.config import Settings


def test_defaults() -> None:
    s = Settings()
    assert s.model == "claude-sonnet-4-6"
    assert s.max_tokens == 4096
    assert s.enable_web_search is True
    assert s.web_search_max_uses == 5
    assert s.debug is False


def test_spotify_redirect_uri_default() -> None:
    s = Settings()
    assert s.spotify_redirect_uri == "http://127.0.0.1:8888/callback"


def test_env_prefix_override(monkeypatch) -> None:
    monkeypatch.setenv("MAX_AI_MODEL", "claude-opus-4-6")
    monkeypatch.setenv("MAX_AI_MAX_TOKENS", "8192")
    s = Settings()
    assert s.model == "claude-opus-4-6"
    assert s.max_tokens == 8192


def test_elevenlabs_defaults() -> None:
    s = Settings()
    assert s.elevenlabs_voice_id == "JBFqnCBsd6RMkjVDRZzb"
    assert s.elevenlabs_tts_model == "eleven_turbo_v2_5"
    assert s.elevenlabs_stt_language == "en"
