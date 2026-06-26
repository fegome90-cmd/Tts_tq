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


class TestGenerationSuccess:
    """Tests for GenerationSuccess domain entity (generation-result-envelope R1)."""

    def test_generation_success_construction(self):
        """GenerationSuccess should expose path/warnings/duration/sample_rate."""
        from tts_lab.domain.entities import GenerationSuccess

        result = GenerationSuccess(
            audio_path="/output/speech_abc123.wav",
            warnings=(),
            duration_seconds=2.5,
            sample_rate=24000,
        )
        assert result.audio_path == "/output/speech_abc123.wav"
        assert result.warnings == ()
        assert result.duration_seconds == pytest.approx(2.5)
        assert result.sample_rate == 24000

    def test_generation_success_is_frozen(self):
        """GenerationSuccess should be immutable."""
        from tts_lab.domain.entities import GenerationSuccess

        result = GenerationSuccess(
            audio_path="/x.wav",
            warnings=(),
            duration_seconds=1.0,
            sample_rate=24000,
        )
        with pytest.raises(FrozenInstanceError):
            setattr(result, "audio_path", "/changed.wav")  # noqa: B010

    def test_generation_success_has_no_audio_data(self):
        """GenerationSuccess MUST NOT carry bytes (invalid-state-unrepresentable)."""
        from tts_lab.domain.entities import GenerationSuccess

        result = GenerationSuccess(
            audio_path="/x.wav",
            warnings=(),
            duration_seconds=1.0,
            sample_rate=24000,
        )
        # No audio_data / bytes field on Success — bytes are dead weight post-save.
        assert not hasattr(result, "audio_data")
        assert not hasattr(result, "bytes")


class TestGenerationFailure:
    """Tests for GenerationFailure domain entity (generation-result-envelope R1)."""

    def test_generation_failure_construction(self):
        """GenerationFailure should wrap a TTSError."""
        from tts_lab.domain.entities import GenerationFailure
        from tts_lab.domain.exceptions import ModelLoadError

        failure = GenerationFailure(error=ModelLoadError("boom"))
        assert isinstance(failure.error, ModelLoadError)

    def test_generation_failure_is_frozen(self):
        """GenerationFailure should be immutable."""
        from tts_lab.domain.entities import GenerationFailure
        from tts_lab.domain.exceptions import ModelLoadError

        failure = GenerationFailure(error=ModelLoadError("boom"))
        with pytest.raises(FrozenInstanceError):
            setattr(failure, "error", ModelLoadError("other"))  # noqa: B010

    def test_generation_failure_has_no_audio_path(self):
        """GenerationFailure MUST NOT expose audio_path (guard against flat-envelope drift)."""
        from tts_lab.domain.entities import GenerationFailure
        from tts_lab.domain.exceptions import ModelLoadError

        failure = GenerationFailure(error=ModelLoadError("boom"))
        assert not hasattr(failure, "audio_path")
        assert not hasattr(failure, "duration_seconds")
        assert not hasattr(failure, "sample_rate")


class TestGenerationResultUnion:
    """Tests for GenerationResult TypeAlias (generation-result-envelope R1)."""

    def test_generation_result_union_accepts_both_variants(self):
        """GenerationResult should accept Success and Failure (importable)."""
        from tts_lab.domain.entities import (
            GenerationFailure,
            GenerationResult,
            GenerationSuccess,
        )
        from tts_lab.domain.exceptions import ModelLoadError

        success: GenerationResult = GenerationSuccess(
            audio_path="/x.wav",
            warnings=(),
            duration_seconds=1.0,
            sample_rate=24000,
        )
        failure: GenerationResult = GenerationFailure(error=ModelLoadError("boom"))

        assert isinstance(success, GenerationSuccess)
        assert isinstance(failure, GenerationFailure)
