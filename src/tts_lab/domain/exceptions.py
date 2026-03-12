"""Domain exceptions for TTS Lab.

These are pure domain exceptions with no external dependencies.
"""


class TTSError(Exception):
    """Base exception for TTS operations."""

    pass


class VoiceProfileError(TTSError):
    """Voice profile validation or loading failed."""

    pass


class ModelLoadError(TTSError):
    """Model loading failed (OOM, not found, etc.)."""

    pass


class AudioFormatError(TTSError):
    """Audio format not supported or corrupted."""

    pass


__all__ = ["AudioFormatError", "ModelLoadError", "TTSError", "VoiceProfileError"]
