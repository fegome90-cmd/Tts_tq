"""Infrastructure - File storage for audio files.

Handles all file I/O with security sanitization.
"""

import hashlib
import io
import logging
from pathlib import Path

from tts_lab.domain.entities import AudioResult
from tts_lab.domain.protocols import AudioRepository

logger = logging.getLogger(__name__)


class FileAudioRepository(AudioRepository):
    """Infrastructure - handles file I/O with path sanitization.

    This is an impure component - it has side effects (file operations).
    """

    def __init__(self, output_dir: str = "output"):
        """Initialize repository with output directory.

        Args:
            output_dir: Directory for saving audio files.
        """
        self._output_dir = Path(output_dir).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, audio: AudioResult, filename: str) -> str:
        """Save audio with sanitized filename.

        Args:
            audio: Audio data to save.
            filename: Desired filename (will be sanitized).

        Returns:
            Full path to saved file.
        """
        safe_filename = self._sanitize_filename(filename)
        path = self._output_dir / safe_filename
        self._write_audio(audio, path)
        logger.debug(f"Saved audio to {path}")
        return str(path)

    def save_with_hash(self, audio: AudioResult, text: str, language: str) -> str:
        """Generate filename from content hash.

        This is an infrastructure concern - the domain should not know
        about filename generation.

        Args:
            audio: Audio data to save.
            text: Text used to generate audio (for hash).
            language: Language used (for hash).

        Returns:
            Full path to saved file.
        """
        hash_input = f"{text}_{language}".encode()
        content_hash = hashlib.sha256(hash_input).hexdigest()[:12]
        filename = f"speech_{content_hash}.wav"
        return self.save(audio, filename)

    def load(self, path: str) -> AudioResult:
        """Load audio from path.

        Args:
            path: Path to audio file.

        Returns:
            AudioResult with loaded audio data.

        Raises:
            ValueError: If path is outside output directory.
        """
        validated_path = self._validate_path(path)
        result = self._read_audio(validated_path)
        logger.debug(f"Loaded audio from {validated_path}")
        return result

    def _sanitize_filename(self, filename: str) -> str:
        """Prevent path traversal - security critical.

        Args:
            filename: Input filename (potentially malicious).

        Returns:
            Safe filename without path separators.
        """
        # Remove any path separators
        safe = Path(filename).name
        # Ensure .wav extension
        if not safe.endswith(".wav"):
            safe = f"{safe}.wav"
        return safe

    def _validate_path(self, path: str) -> Path:
        """Validate path is within output directory.

        Args:
            path: Path to validate.

        Returns:
            Resolved path if valid.

        Raises:
            ValueError: If path is outside output directory.
        """
        resolved = Path(path).resolve()
        if not str(resolved).startswith(str(self._output_dir)):
            raise ValueError(f"Path traversal detected: {path}")
        return resolved

    def _write_audio(self, audio: AudioResult, path: Path) -> None:
        """Write audio bytes to file.

        Args:
            audio: Audio data to write.
            path: Destination path.
        """
        with open(path, "wb") as f:
            f.write(audio.audio_data)

    def _read_audio(self, path: Path) -> AudioResult:
        """Read audio file and return AudioResult.

        Args:
            path: Path to audio file.

        Returns:
            AudioResult with audio data.
        """
        import soundfile as sf

        data, sr = sf.read(str(path))
        buffer = io.BytesIO()
        sf.write(buffer, data, sr, format="WAV")
        duration = len(data) / sr

        return AudioResult(
            audio_data=buffer.getvalue(),
            sample_rate=sr,
            duration_seconds=duration,
        )


__all__ = ["FileAudioRepository"]
