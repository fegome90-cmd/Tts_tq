"""Tests for domain exceptions."""

import pytest


class TestExceptions:
    """Tests for domain exceptions."""

    def test_tts_error_is_exception(self):
        """TTSError should be an Exception."""
        from tts_lab.domain.exceptions import TTSError

        assert issubclass(TTSError, Exception)

    def test_tts_error_can_be_raised(self):
        """TTSError can be raised with a message."""
        from tts_lab.domain.exceptions import TTSError

        with pytest.raises(TTSError, match="test error"):
            raise TTSError("test error")

    def test_voice_profile_error_is_tts_error(self):
        """VoiceProfileError should inherit from TTSError."""
        from tts_lab.domain.exceptions import TTSError, VoiceProfileError

        assert issubclass(VoiceProfileError, TTSError)

    def test_voice_profile_error_can_be_raised(self):
        """VoiceProfileError can be raised with a message."""
        from tts_lab.domain.exceptions import VoiceProfileError

        with pytest.raises(VoiceProfileError, match="profile error"):
            raise VoiceProfileError("profile error")

    def test_model_load_error_is_tts_error(self):
        """ModelLoadError should inherit from TTSError."""
        from tts_lab.domain.exceptions import ModelLoadError, TTSError

        assert issubclass(ModelLoadError, TTSError)

    def test_model_load_error_can_be_raised(self):
        """ModelLoadError can be raised with a message."""
        from tts_lab.domain.exceptions import ModelLoadError

        with pytest.raises(ModelLoadError, match="load error"):
            raise ModelLoadError("load error")

    def test_audio_format_error_is_tts_error(self):
        """AudioFormatError should inherit from TTSError."""
        from tts_lab.domain.exceptions import AudioFormatError, TTSError

        assert issubclass(AudioFormatError, TTSError)

    def test_audio_format_error_can_be_raised(self):
        """AudioFormatError can be raised with a message."""
        from tts_lab.domain.exceptions import AudioFormatError

        with pytest.raises(AudioFormatError, match="format error"):
            raise AudioFormatError("format error")

    def test_unsupported_operation_error_is_tts_error(self):
        """UnsupportedOperationError should inherit from TTSError."""
        from tts_lab.domain.exceptions import TTSError, UnsupportedOperationError

        assert issubclass(UnsupportedOperationError, TTSError)

    def test_unsupported_operation_error_requires_operation_provider_kwargs(self):
        """UnsupportedOperationError ctor takes message + kw-only operation/provider."""
        from tts_lab.domain.exceptions import UnsupportedOperationError

        err = UnsupportedOperationError(
            "not supported", operation="clone_voice", provider="inworld"
        )
        assert str(err) == "not supported"
        assert err.operation == "clone_voice"
        assert err.provider == "inworld"

    def test_unsupported_operation_error_operation_provider_are_keyword_only(self):
        """operation and provider must be keyword-only (positional rejected)."""
        from tts_lab.domain.exceptions import UnsupportedOperationError

        with pytest.raises(TypeError):
            UnsupportedOperationError(  # type: ignore[misc]
                "msg", "clone_voice", "inworld"
            )
