#!/usr/bin/env python3
"""Manual smoke test for the Deepgram streaming transcription integration.

Workflow:
  1. Press Enter to start recording.
  2. Speak.
  3. Press Enter to stop.
  4. See the transcript printed to stdout.

Press q + Enter to quit.
Requires MAX_AI_DEEPGRAM_API_KEY to be set in .env or the environment.
"""

from __future__ import annotations

import asyncio
import sys
import termios
import tty


def _getch() -> str:
    """Read one character without echo."""
    file_descriptor = sys.stdin.fileno()
    old_settings = termios.tcgetattr(file_descriptor)
    try:
        tty.setcbreak(file_descriptor)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)


def _wait_for_enter_or_quit() -> str:
    """Block until Enter or 'q'. Returns 'enter' or 'q'."""
    while True:
        character = _getch()
        if character in ("\n", "\r"):
            return "enter"
        if character.lower() == "q":
            return "q"


async def run() -> None:
    from max_ai.config import settings
    from max_ai.voice.loop import _transcribe_with_deepgram

    if not settings.deepgram_api_key:
        print("ERROR: MAX_AI_DEEPGRAM_API_KEY is not set.")
        sys.exit(1)

    print("\nDeeepgram Transcription Test")
    print("============================")
    print("Controls: Enter = start/stop  |  q = quit\n")

    clip = 0
    while True:
        clip += 1
        print(f"[Clip {clip:02d}] Press Enter to start (q to quit) ...", end=" ", flush=True)

        key = _wait_for_enter_or_quit()
        if key == "q":
            print("\nBye.")
            break

        print("  Preparing microphone …", end="\r", flush=True)

        def on_recording_started() -> None:
            print("  Recording …  (press Enter to stop)", end=" ", flush=True)

        try:
            _wav_bytes, transcript = await _transcribe_with_deepgram(
                settings.deepgram_api_key,
                settings.voice_input_device,
                on_recording_started,
            )
        except Exception as exception:
            print(f"\n  Error: {exception}\n")
            continue

        print()
        if transcript:
            print(f"\n  Transcript: {transcript}\n")
        else:
            print("\n  (no transcript returned)\n")


if __name__ == "__main__":
    asyncio.run(run())
