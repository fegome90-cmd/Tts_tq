"""Application layer DTOs (Data Transfer Objects).

These are immutable data structures for request/response.
"""

from dataclasses import dataclass
from typing import Literal

Language = Literal["Spanish", "English", "Auto"]


@dataclass(frozen=True)
class GenerateSpeechRequest:
    """Request DTO for speech generation.

    Attributes:
        text: Text to convert to speech.
        language: Language for synthesis (default: Auto).
        voice_profile_name: Optional voice profile to use for cloning.
        speaker: Optional speaker name threaded end-to-end into TTSRequest.
            Reaches Qwen (multi-speaker models) and Inworld (per-voice
            selection via voiceId). Fixes the latent dead-code ``--speaker``
            bug where the CLI accepted the flag but the DTO dropped it.
    """

    text: str
    language: Language = "Auto"
    voice_profile_name: str | None = None
    speaker: str | None = None


@dataclass(frozen=True)
class GenerateSpeechResponse:
    """Response DTO for speech generation.

    Attributes:
        audio_path: Path to the generated audio file.
        duration_seconds: Duration of the generated audio.
    """

    audio_path: str
    duration_seconds: float


__all__ = ["GenerateSpeechRequest", "GenerateSpeechResponse", "Language"]
