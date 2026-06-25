"""Tests for infrastructure configuration - TTSConfig + InworldConfig.

TDD RED Phase: These tests define expected behavior BEFORE implementation.
"""

import pytest


class TestTTSConfig:
    """Tests for TTSConfig provider selection."""

    def test_tts_config_provider_defaults_qwen(self):
        """TTSConfig.provider should default to 'qwen'."""
        from tts_lab.infrastructure.config import TTSConfig

        config = TTSConfig(model_path="some/model")
        assert config.provider == "qwen"

    def test_tts_config_from_env_reads_tts_provider(self, monkeypatch):
        """TTSConfig.from_env should read TTS_PROVIDER env var."""
        from tts_lab.infrastructure.config import TTSConfig

        monkeypatch.setenv("TTS_PROVIDER", "inworld")
        config = TTSConfig.from_env()
        assert config.provider == "inworld"

    def test_tts_config_from_env_defaults_qwen_when_unset(self, monkeypatch):
        """TTSConfig.from_env should default to qwen when TTS_PROVIDER unset."""
        from tts_lab.infrastructure.config import TTSConfig

        monkeypatch.delenv("TTS_PROVIDER", raising=False)
        config = TTSConfig.from_env()
        assert config.provider == "qwen"

    def test_tts_config_is_frozen(self):
        """TTSConfig should be immutable."""
        from dataclasses import FrozenInstanceError

        from tts_lab.infrastructure.config import TTSConfig

        config = TTSConfig(model_path="m")
        with pytest.raises(FrozenInstanceError):
            config.provider = "inworld"  # type: ignore[misc]


class TestInworldConfig:
    """Tests for InworldConfig."""

    def test_inworld_config_from_env_reads_key_base_url_voice_encoding(
        self, monkeypatch
    ):
        """InworldConfig.from_env should read all env vars with defaults."""
        from tts_lab.infrastructure.config import InworldConfig

        monkeypatch.setenv("INWORLD_API_KEY", "dGhpcy1pcy1hLWZha2Uta2V5")
        monkeypatch.setenv("INWORLD_BASE_URL", "https://custom.example.com")
        monkeypatch.setenv("INWORLD_DEFAULT_VOICE_ID", "Dennis")
        monkeypatch.setenv("INWORLD_AUDIO_ENCODING", "MP3")

        config = InworldConfig.from_env()

        assert config.api_key == "dGhpcy1pcy1hLWZha2Uta2V5"
        assert config.base_url == "https://custom.example.com"
        assert config.default_voice_id == "Dennis"
        assert config.audio_encoding == "MP3"

    def test_inworld_config_from_env_defaults(self, monkeypatch):
        """InworldConfig.from_env should apply documented defaults."""
        from tts_lab.infrastructure.config import InworldConfig

        monkeypatch.delenv("INWORLD_API_KEY", raising=False)
        monkeypatch.delenv("INWORLD_BASE_URL", raising=False)
        monkeypatch.delenv("INWORLD_DEFAULT_VOICE_ID", raising=False)
        monkeypatch.delenv("INWORLD_AUDIO_ENCODING", raising=False)

        config = InworldConfig.from_env()

        # api_key may be empty here; factory owns the eager check.
        assert config.api_key == ""
        assert config.base_url == "https://api.inworld.ai"
        assert config.default_voice_id == "Sarah"
        assert config.audio_encoding == "LINEAR16"

    def test_inworld_config_is_frozen(self, monkeypatch):
        """InworldConfig should be immutable."""
        from dataclasses import FrozenInstanceError

        from tts_lab.infrastructure.config import InworldConfig

        monkeypatch.setenv("INWORLD_API_KEY", "key")
        config = InworldConfig.from_env()

        with pytest.raises(FrozenInstanceError):
            config.api_key = "other"  # type: ignore[misc]

    def test_inworld_config_http_timeout_defaults_to_30s(self):
        """InworldConfig.http_timeout_seconds defaults to 30.0 (finite)."""
        from tts_lab.infrastructure.config import InworldConfig

        config = InworldConfig(api_key="x")
        assert config.http_timeout_seconds == pytest.approx(30.0)

    def test_inworld_config_from_env_reads_http_timeout(self, monkeypatch):
        """InworldConfig.from_env reads INWORLD_HTTP_TIMEOUT."""
        from tts_lab.infrastructure.config import InworldConfig

        monkeypatch.setenv("INWORLD_HTTP_TIMEOUT", "5.5")
        config = InworldConfig.from_env()
        assert config.http_timeout_seconds == pytest.approx(5.5)

    def test_inworld_config_from_env_http_timeout_default(self, monkeypatch):
        """InworldConfig.from_env defaults timeout to 30s when env unset."""
        from tts_lab.infrastructure.config import InworldConfig

        monkeypatch.delenv("INWORLD_HTTP_TIMEOUT", raising=False)
        config = InworldConfig.from_env()
        assert config.http_timeout_seconds == pytest.approx(30.0)
