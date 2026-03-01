"""Alarm tool — plays an audible alert via ElevenLabs TTS."""

from typing import Any

from max_ai.agent.tools.base import BaseTool, ToolDefinition
from max_ai.config import settings
from max_ai.voice.tts import speak


class AlarmTool(BaseTool):
    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="sound_alarm",
                description=(
                    "Play an audible alarm to the user via ElevenLabs text-to-speech. "
                    "Call this when a timer fires or when you need to alert the user "
                    "with an urgent notification."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The alarm message to speak aloud.",
                        },
                    },
                    "required": ["message"],
                },
            )
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        message: str = tool_input["message"]
        await speak(
            text=message,
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_tts_model,
        )
        return f"Alarm sounded: '{message}'"
