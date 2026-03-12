"""Tests for infrastructure layer - FileAudioRepository.

TDD RED Phase: These tests define expected behavior BEFORE implementation.
"""

from pathlib import Path

import pytest


class TestFileAudioRepository:
    """Tests for FileAudioRepository."""

    def test_repository_exists(self):
        """FileAudioRepository should exist."""
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        assert FileAudioRepository is not None

    def test_repository_creates_output_dir(self, temp_output_dir, sample_audio_data):
        """Repository should create output directory if not exists."""
        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        new_dir = temp_output_dir / "new_output"
        repo = FileAudioRepository(output_dir=str(new_dir))

        audio = AudioResult(
            audio_data=sample_audio_data,
            sample_rate=24000,
            duration_seconds=1.0,
        )
        repo.save(audio, "test.wav")

        assert new_dir.exists()

    def test_save_returns_path(self, temp_output_dir, sample_audio_data):
        """Save should return the full path to saved file."""
        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        repo = FileAudioRepository(output_dir=str(temp_output_dir))
        audio = AudioResult(
            audio_data=sample_audio_data,
            sample_rate=24000,
            duration_seconds=1.0,
        )

        path = repo.save(audio, "test.wav")

        assert Path(path).exists()
        assert path.endswith("test.wav")

    def test_sanitize_filename_prevents_path_traversal(self, temp_output_dir, sample_audio_data):
        """Security: Prevent path traversal attacks."""
        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        repo = FileAudioRepository(output_dir=str(temp_output_dir))
        audio = AudioResult(
            audio_data=sample_audio_data,
            sample_rate=24000,
            duration_seconds=1.0,
        )

        # Malicious filename attempting traversal
        path = repo.save(audio, "../../../etc/passwd")

        # Should be saved in output dir, not /etc/
        assert str(temp_output_dir) in path
        assert "etc" not in path

    def test_sanitize_filename_adds_wav_extension(self, temp_output_dir, sample_audio_data):
        """Should add .wav extension if not present."""
        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        repo = FileAudioRepository(output_dir=str(temp_output_dir))
        audio = AudioResult(
            audio_data=sample_audio_data,
            sample_rate=24000,
            duration_seconds=1.0,
        )

        path = repo.save(audio, "test")

        assert path.endswith(".wav")

    def test_save_with_hash_generates_filename(self, temp_output_dir, sample_audio_data):
        """save_with_hash should generate filename from content hash."""
        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        repo = FileAudioRepository(output_dir=str(temp_output_dir))
        audio = AudioResult(
            audio_data=sample_audio_data,
            sample_rate=24000,
            duration_seconds=1.0,
        )

        path = repo.save_with_hash(audio, "Hello world", "English")

        assert "speech_" in path
        assert path.endswith(".wav")
        assert Path(path).exists()

    def test_save_with_hash_is_deterministic(self, temp_output_dir, sample_audio_data):
        """Same text/language should produce same hash."""
        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        repo = FileAudioRepository(output_dir=str(temp_output_dir))
        audio = AudioResult(
            audio_data=sample_audio_data,
            sample_rate=24000,
            duration_seconds=1.0,
        )

        path1 = repo.save_with_hash(audio, "Test", "Spanish")
        path2 = repo.save_with_hash(audio, "Test", "Spanish")

        assert path1 == path2

    def test_load_returns_audio_result(self, temp_output_dir, sample_audio_data):
        """Load should return AudioResult with correct data."""
        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        repo = FileAudioRepository(output_dir=str(temp_output_dir))
        audio = AudioResult(
            audio_data=sample_audio_data,
            sample_rate=24000,
            duration_seconds=1.0,
        )

        path = repo.save(audio, "test.wav")
        loaded = repo.load(path)

        assert isinstance(loaded, AudioResult)
        assert loaded.sample_rate == 24000
        assert loaded.duration_seconds > 0

    def test_validate_path_rejects_traversal(self, temp_output_dir):
        """_validate_path should reject paths outside output directory."""
        from tts_lab.infrastructure.file_storage import FileAudioRepository

        repo = FileAudioRepository(output_dir=str(temp_output_dir))

        with pytest.raises(ValueError, match="Path traversal"):
            repo._validate_path("/etc/passwd")

        with pytest.raises(ValueError, match="Path traversal"):
            repo._validate_path(str(temp_output_dir / ".." / "etc" / "passwd"))


class TestTTSConfig:
    """Tests for TTSConfig."""

    def test_config_exists(self):
        """TTSConfig should exist."""
        from tts_lab.infrastructure.config import TTSConfig

        assert TTSConfig is not None

    def test_config_defaults(self):
        """TTSConfig should have sensible defaults for Apple Silicon."""
        from tts_lab.infrastructure.config import TTSConfig

        config = TTSConfig(model_path="test_model")

        assert config.device == "mps"
        assert config.output_dir == "output"
        assert config.voices_dir == "voice_profiles"

    def test_config_from_env(self, monkeypatch):
        """TTSConfig should load from environment variables."""
        from tts_lab.infrastructure.config import TTSConfig

        monkeypatch.setenv("TTS_MODEL_PATH", "custom_model")
        monkeypatch.setenv("TTS_DEVICE", "cuda")
        monkeypatch.setenv("TTS_OUTPUT_DIR", "custom_output")

        config = TTSConfig.from_env()

        assert config.model_path == "custom_model"
        assert config.device == "cuda"
        assert config.output_dir == "custom_output"
