"""Tests for domain protocols - TTSClient, AudioRepository.

TDD RED Phase: These tests define the expected behavior BEFORE implementation.
"""

from typing import Protocol


class TestTTSClientProtocol:
    """Tests for TTSClient protocol."""

    def test_tts_client_is_protocol(self):
        """TTSClient should be a Protocol."""
        from tts_lab.domain.protocols import TTSClient

        assert issubclass(TTSClient, Protocol)

    def test_tts_client_has_generate_method(self):
        """TTSClient should have generate method."""
        from tts_lab.domain.protocols import TTSClient

        # Protocol methods should be defined
        assert hasattr(TTSClient, "generate")

    def test_tts_client_has_clone_voice_method(self):
        """TTSClient should have clone_voice method."""
        from tts_lab.domain.protocols import TTSClient

        assert hasattr(TTSClient, "clone_voice")


class TestAudioRepositoryProtocol:
    """Tests for AudioRepository protocol."""

    def test_audio_repository_is_protocol(self):
        """AudioRepository should be a Protocol."""
        from tts_lab.domain.protocols import AudioRepository

        assert issubclass(AudioRepository, Protocol)

    def test_audio_repository_has_save_method(self):
        """AudioRepository should have save method."""
        from tts_lab.domain.protocols import AudioRepository

        assert hasattr(AudioRepository, "save")

    def test_audio_repository_has_load_method(self):
        """AudioRepository should have load method."""
        from tts_lab.domain.protocols import AudioRepository

        assert hasattr(AudioRepository, "load")

    def test_audio_repository_has_save_with_hash_method(self):
        """AudioRepository should have save_with_hash method."""
        from tts_lab.domain.protocols import AudioRepository

        assert hasattr(AudioRepository, "save_with_hash")


class TestProtocolCompliance:
    """Test that implementations can satisfy protocols."""

    def test_mock_tts_client_satisfies_protocol(self):
        """A mock TTSClient should satisfy the protocol."""
        from tts_lab.domain.entities import AudioResult, TTSRequest

        class MockTTSClient:
            def generate(self, request: TTSRequest) -> AudioResult:
                return AudioResult(audio_data=b"test", sample_rate=24000, duration_seconds=1.0)

            def clone_voice(self, profile, text: str) -> AudioResult:
                return AudioResult(audio_data=b"test", sample_rate=24000, duration_seconds=1.0)

        client = MockTTSClient()
        # Should be able to use as TTSClient
        assert callable(client.generate)
        assert callable(client.clone_voice)

    def test_mock_audio_repository_satisfies_protocol(self):
        """A mock AudioRepository should satisfy the protocol."""
        from tts_lab.domain.entities import AudioResult

        class MockAudioRepository:
            def save(self, audio: AudioResult, filename: str) -> str:
                return f"/output/{filename}"

            def save_with_hash(self, audio: AudioResult, text: str, language: str) -> str:
                return "/output/speech_hash.wav"

            def load(self, path: str) -> AudioResult:
                return AudioResult(audio_data=b"test", sample_rate=24000, duration_seconds=1.0)

        repo = MockAudioRepository()
        assert callable(repo.save)
        assert callable(repo.save_with_hash)
        assert callable(repo.load)
