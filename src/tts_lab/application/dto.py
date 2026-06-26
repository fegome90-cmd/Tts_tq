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
        instruct: Optional voice-style instructions threaded end-to-end into
            TTSRequest. Reaches Qwen (activates instruction-tuning at
            qwen_client.py:97). Fixes the latent dead-code ``--instruct`` bug
            where the CLI accepted the flag but the DTO dropped it. Passing
            ``-i <text>`` is a DELIBERATE behavior change (enables Qwen
            instruction mode); the default ``None`` preserves the pre-change
            path.
    """

    text: str
    language: Language = "Auto"
    voice_profile_name: str | None = None
    speaker: str | None = None
    instruct: str | None = None


__all__ = ["GenerateSpeechRequest", "Language"]
