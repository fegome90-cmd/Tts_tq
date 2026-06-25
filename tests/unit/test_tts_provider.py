"""Tests for the TTS provider factory.

TDD RED Phase: These tests define expected behavior BEFORE implementation.
"""

import pytest

from tts_lab.domain.exceptions import TTSError
from tts_lab.infrastructure.config import TTSConfig


class TestCreateTtsClient:
    """create_tts_client dispatches on settings.provider."""

    def test_create_qwen(self):
        """provider='qwen' -> QwenTTSClient (no network, just construction)."""
        from tts_lab.infrastructure.qwen_client import QwenTTSClient
        from tts_lab.infrastructure.tts_provider import create_tts_client

        settings = TTSConfig(
            model_path="some/model", device="cpu", provider="qwen"
        )
        client = create_tts_client(settings)
        assert isinstance(client, QwenTTSClient)

    def test_create_inworld_with_key(self, monkeypatch):
        """provider='inworld' + INWORLD_API_KEY set -> InworldTTSClient."""
        from tts_lab.infrastructure.inworld_client import InworldTTSClient
        from tts_lab.infrastructure.tts_provider import create_tts_client

        monkeypatch.setenv("INWORLD_API_KEY", "dGhpcy1pcy1hLWZha2Uta2V5")
        settings = TTSConfig(
            model_path="ignored", device="cpu", provider="inworld"
        )
        client = create_tts_client(settings)
        assert isinstance(client, InworldTTSClient)

    def test_create_inworld_without_key_raises_tts_error(self, monkeypatch):
        """provider='inworld' + no key -> TTSError at construction."""
        from tts_lab.infrastructure.tts_provider import create_tts_client

        monkeypatch.delenv("INWORLD_API_KEY", raising=False)
        settings = TTSConfig(
            model_path="ignored", device="cpu", provider="inworld"
        )
        with pytest.raises(TTSError):
            create_tts_client(settings)

    def test_create_unknown_raises_value_error(self):
        """Unknown provider -> ValueError."""
        from tts_lab.infrastructure.tts_provider import create_tts_client

        settings = TTSConfig(
            model_path="ignored", device="cpu", provider="not-a-provider"
        )
        with pytest.raises(ValueError):
            create_tts_client(settings)
