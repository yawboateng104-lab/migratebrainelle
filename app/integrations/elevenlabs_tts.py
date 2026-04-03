# app/integrations/elevenlabs_tts.py
from pathlib import Path

import requests

from app.config import settings


class ElevenLabsError(Exception):
    """Raised when an ElevenLabs API call fails or returns invalid audio."""


def _get_headers() -> dict[str, str]:
    if not settings.ELEVENLABS_API_KEY:
        raise ElevenLabsError("Missing ElevenLabs API key")

    return {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }


def synthesize_speech_bytes(
    text: str,
    voice_id: str | None = None,
    model_id: str | None = None,
) -> bytes:
    """
    Generate narration audio from text and return raw bytes.
    """
    resolved_voice_id = voice_id or settings.ELEVENLABS_VOICE_ID
    if not resolved_voice_id:
        raise ElevenLabsError("Missing ElevenLabs voice_id")

    url = (
        f"{settings.ELEVENLABS_BASE_URL}/v1/text-to-speech/"
        f"{resolved_voice_id}?output_format=mp3_44100_128"
    )

    payload = {
        "text": text,
        "model_id": model_id or settings.ELEVENLABS_MODEL_ID,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
        },
    }

    response = requests.post(
        url,
        json=payload,
        headers=_get_headers(),
        timeout=180,
    )

    if response.status_code >= 400:
        raise ElevenLabsError(
            f"ElevenLabs TTS request failed: {response.status_code} {response.text}"
        )

    if not response.content:
        raise ElevenLabsError("ElevenLabs returned empty audio content")

    return response.content


def synthesize_speech_to_file(
    text: str,
    output_path: str | Path,
    voice_id: str | None = None,
    model_id: str | None = None,
) -> str:
    """
    Generate narration and write it to a file.
    """
    audio_bytes = synthesize_speech_bytes(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_bytes)

    return str(output_path)
