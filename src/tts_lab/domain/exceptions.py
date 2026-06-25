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


class UnsupportedOperationError(TTSError):
    """A provider cannot honor the requested operation.

    Raised when a TTS provider is asked to perform an operation it does not
    support (e.g. voice cloning on a preset-voice-only provider).

    Attributes:
        operation: The unsupported operation name (e.g. "clone_voice").
        provider: The provider that refused (e.g. "inworld").
    """

    operation: str
    provider: str

    def __init__(self, message: str, *, operation: str, provider: str) -> None:
        """Initialize with message and keyword-only operation/provider.

        Args:
            message: Human-readable error message.
            operation: The unsupported operation name.
            provider: The provider that refused the operation.
        """
        super().__init__(message)
        self.operation = operation
        self.provider = provider


__all__ = [
    "AudioFormatError",
    "ModelLoadError",
    "TTSError",
    "UnsupportedOperationError",
    "VoiceProfileError",
]
