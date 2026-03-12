"""Pure domain protocols for TTS Lab.

These protocols define interfaces without implementations.
They have no external dependencies.
"""

from typing import Protocol

from tts_lab.domain.entities import AudioResult, TTSRequest, VoiceProfile


class TTSClient(Protocol):
    """Protocol for TTS client - pure interface for text-to-speech generation."""

    def generate(self, request: TTSRequest) -> AudioResult:
        """Generate speech from text.

        Args:
            request: TTS request with text, language, and optional speaker.

        Returns:
            AudioResult with generated audio data.
        """
        ...

    def clone_voice(self, profile: VoiceProfile, text: str) -> AudioResult:
        """Clone voice from reference audio and generate speech.

        Args:
            profile: Voice profile with reference audio and text.
            text: Text to speak with cloned voice.

        Returns:
            AudioResult with generated audio data.
        """
        ...


class AudioRepository(Protocol):
    """Protocol for audio storage - pure interface for file operations."""

    def save(self, audio: AudioResult, filename: str) -> str:
        """Save audio to file.

        Args:
            audio: Audio data to save.
            filename: Name for the file (will be sanitized).

        Returns:
            Full path to saved file.
        """
        ...

    def save_with_hash(self, audio: AudioResult, text: str, language: str) -> str:
        """Save audio with content-based hash filename.

        Args:
            audio: Audio data to save.
            text: Text used to generate audio (for hash).
            language: Language used (for hash).

        Returns:
            Full path to saved file.
        """
        ...

    def load(self, path: str) -> AudioResult:
        """Load audio from file.

        Args:
            path: Path to audio file.

        Returns:
            AudioResult with loaded audio data.
        """
        ...


__all__ = ["AudioRepository", "TTSClient"]
