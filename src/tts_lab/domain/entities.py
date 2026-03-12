"""Pure domain entities for TTS Lab.

These entities are immutable and have no external dependencies.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TTSRequest:
    """Pure domain entity for TTS requests.

    Attributes:
        text: The text to convert to speech.
        language: Language for synthesis (Spanish, English, or Auto-detect).
        speaker: Optional speaker name for multi-speaker models.
        instruct: Optional voice style instructions (e.g., "speak happily").
    """

    text: str
    language: Literal["Spanish", "English", "Auto"] = "Auto"
    speaker: str | None = None
    instruct: str | None = None


@dataclass(frozen=True)
class AudioResult:
    """Pure domain entity for TTS output.

    Attributes:
        audio_data: Raw audio bytes (WAV format).
        sample_rate: Audio sample rate in Hz.
        duration_seconds: Duration of the audio in seconds.
    """

    audio_data: bytes
    sample_rate: int
    duration_seconds: float


@dataclass(frozen=True)
class VoiceProfile:
    """Pure domain entity for voice cloning reference.

    Attributes:
        name: Unique name for this voice profile.
        reference_audio_path: Path to reference audio file for cloning.
        reference_text: Transcription of the reference audio.
    """

    name: str
    reference_audio_path: str
    reference_text: str


__all__ = ["AudioResult", "TTSRequest", "VoiceProfile"]
