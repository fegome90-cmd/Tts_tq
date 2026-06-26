"""Pure domain entities for TTS Lab.

These entities are immutable and have no external dependencies.
"""

from dataclasses import dataclass
from typing import Literal

from tts_lab.domain.exceptions import TTSError


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


@dataclass(frozen=True)
class GenerationSuccess:
    """DOMAIN result for a successful speech-generation run.

    Carries only post-save scalars: bytes are dead weight once `save_with_hash`
    has written them to disk. Duplicating AudioResult's scalars deliberately
    avoids coupling the result envelope to the client transport type and makes
    byte-leak structurally impossible.

    Attributes:
        audio_path: Path where the generated audio was persisted.
        warnings: Non-fatal warnings emitted during generation (e.g. future
            truncation signals).
        duration_seconds: Duration of the generated audio.
        sample_rate: Sample rate of the generated audio.
    """

    audio_path: str
    warnings: tuple[str, ...]
    duration_seconds: float
    sample_rate: int


@dataclass(frozen=True)
class GenerationFailure:
    """DOMAIN result for a failed speech-generation run.

    Wraps the typed domain error so callers consume failure as data, not as
    raised exceptions. `error` is ALWAYS a `TTSError` subclass so the
    typed-error promise holds for both the generate-branch (TTSError pass
    through) and the save-branch (OSError wrapped into AudioStorageError).

    Attributes:
        error: The typed TTS error that caused the failure.
    """

    error: TTSError


# 2-variant discriminated union: invalid states (e.g. nullable audio_path on
# success, audio fields on failure) are structurally unrepresentable.
type GenerationResult = GenerationSuccess | GenerationFailure


__all__ = [
    "AudioResult",
    "GenerationFailure",
    "GenerationResult",
    "GenerationSuccess",
    "TTSRequest",
    "VoiceProfile",
]
