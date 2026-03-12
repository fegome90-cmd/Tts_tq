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
