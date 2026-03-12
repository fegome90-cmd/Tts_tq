"""Domain layer - Pure entities, protocols, and services."""

from tts_lab.domain.entities import AudioResult, TTSRequest, VoiceProfile
from tts_lab.domain.exceptions import (
    AudioFormatError,
    ModelLoadError,
    TTSError,
    VoiceProfileError,
)
from tts_lab.domain.protocols import AudioRepository, TTSClient

__all__ = [
    "AudioFormatError",
    "AudioRepository",
    "AudioResult",
    "ModelLoadError",
    "TTSClient",
    "TTSError",
    "TTSRequest",
    "VoiceProfile",
    "VoiceProfileError",
]
