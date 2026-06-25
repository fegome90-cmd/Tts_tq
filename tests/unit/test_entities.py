"""Tests for domain entities - TTSRequest, AudioResult, VoiceProfile.

TDD RED Phase: These tests define the expected behavior BEFORE implementation.
"""

from dataclasses import FrozenInstanceError

import pytest


class TestTTSRequest:
    """Tests for TTSRequest domain entity."""

    def test_tts_request_is_frozen(self):
        """TTSRequest should be immutable."""
        from tts_lab.domain.entities import TTSRequest

        request = TTSRequest(text="Hola mundo", language="Spanish")
        with pytest.raises(FrozenInstanceError):
            setattr(request, "text", "Changed")  # noqa: B010

    def test_tts_request_defaults(self):
        """TTSRequest should have sensible defaults."""
        from tts_lab.domain.entities import TTSRequest

        request = TTSRequest(text="Test")
        assert request.language == "Auto"
        assert request.speaker is None
        assert request.instruct is None

    def test_tts_request_with_all_fields(self):
        """TTSRequest should accept all optional fields."""
        from tts_lab.domain.entities import TTSRequest

        request = TTSRequest(
            text="Hello world",
            language="English",
            speaker="Serena",
            instruct="speak happily",
        )
        assert request.text == "Hello world"
        assert request.language == "English"
        assert request.speaker == "Serena"
        assert request.instruct == "speak happily"

    def test_tts_request_language_literal(self):
        """TTSRequest language should be a Literal type."""
        from tts_lab.domain.entities import TTSRequest

        # Valid languages
        TTSRequest(text="Test", language="Spanish")
        TTSRequest(text="Test", language="English")
        TTSRequest(text="Test", language="Auto")


class TestAudioResult:
    """Tests for AudioResult domain entity."""

    def test_audio_result_is_frozen(self):
        """AudioResult should be immutable."""
        from tts_lab.domain.entities import AudioResult

        audio = AudioResult(audio_data=b"fake", sample_rate=24000, duration_seconds=1.0)
        with pytest.raises(FrozenInstanceError):
            setattr(audio, "sample_rate", 48000)  # noqa: B010

    def test_audio_result_required_fields(self):
        """AudioResult should require audio_data, sample_rate, duration_seconds."""
        from tts_lab.domain.entities import AudioResult

        audio = AudioResult(
            audio_data=b"fake_audio_data",
            sample_rate=24000,
            duration_seconds=2.5,
        )
        assert audio.audio_data == b"fake_audio_data"
        assert audio.sample_rate == 24000
        assert audio.duration_seconds == pytest.approx(2.5)

    def test_audio_result_with_empty_data(self):
        """AudioResult should accept empty audio data (edge case)."""
        from tts_lab.domain.entities import AudioResult

        audio = AudioResult(audio_data=b"", sample_rate=24000, duration_seconds=0.0)
        assert audio.audio_data == b""
        assert audio.duration_seconds == pytest.approx(0.0)


class TestVoiceProfile:
    """Tests for VoiceProfile domain entity."""

    def test_voice_profile_is_frozen(self):
        """VoiceProfile should be immutable."""
        from tts_lab.domain.entities import VoiceProfile

        profile = VoiceProfile(
            name="felipe",
            reference_audio_path="/path/to/ref.wav",
            reference_text="Hola, esta es mi voz.",
        )
        with pytest.raises(FrozenInstanceError):
            setattr(profile, "name", "changed")  # noqa: B010

    def test_voice_profile_required_fields(self):
        """VoiceProfile should require name, reference_audio_path, reference_text."""
        from tts_lab.domain.entities import VoiceProfile

        profile = VoiceProfile(
            name="felipe",
            reference_audio_path="/voice_profiles/felipe/reference.wav",
            reference_text="Esta es una grabación de referencia.",
        )
        assert profile.name == "felipe"
        assert profile.reference_audio_path == "/voice_profiles/felipe/reference.wav"
        assert profile.reference_text == "Esta es una grabación de referencia."
