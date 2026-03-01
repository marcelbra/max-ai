from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MAX_AI_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    database_url: str = f"sqlite+aiosqlite:///{Path.home()}/.max-ai/max_ai.db"

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"

    # Web search (built-in Anthropic server tool — $10/1k searches)
    enable_web_search: bool = True
    web_search_max_uses: int = 5

    # LangWatch
    langwatch_api_key: str = ""

    # ElevenLabs (voice mode)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # George (default)
    elevenlabs_tts_model: str = "eleven_turbo_v2_5"
    elevenlabs_stt_model: str = "scribe_v1"
    elevenlabs_stt_language: str = "en"  # ISO 639-1 code; passed to ElevenLabs STT

    # Run: python -c "import sounddevice; print(sounddevice.query_devices())" to list devices.
    # Optional sounddevice output device index for TTS playback.
    tts_output_device: int | None = None

    # Optional sounddevice input device index for voice recording.
    # TIP: Set voice_input_device to your built-in mic (e.g. MacBook Pro Microphone) so that
    # Bluetooth headphones stay on A2DP (high-quality) instead of switching to HFP when the
    # microphone stream opens.
    voice_input_device: int | None = None

    # Wake word mode (Porcupine + Deepgram)
    picovoice_access_key: str = ""
    porcupine_keyword_path: str = ""  # empty = use built-in keyword
    deepgram_api_key: str = ""
    vad_silence_threshold_ms: int = 1800
    vad_min_words: int = 3

    # Debug
    debug: bool = False


settings = Settings()
