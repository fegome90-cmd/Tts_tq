"""Tests for QwenTTSClient - mocked unit tests.

These tests mock the model to avoid loading the actual Qwen model.
"""

import sys
from unittest.mock import Mock, patch

import pytest


class TestQwenTTSClientInit:
    """Tests for QwenTTSClient initialization."""

    def test_client_exists(self):
        """QwenTTSClient should exist."""
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        assert QwenTTSClient is not None

    def test_client_initializes_with_model_path(self):
        """QwenTTSClient should accept model_path."""
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")
        assert client is not None

    def test_client_accepts_device_parameter(self):
        """QwenTTSClient should accept device parameter."""
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model", device="cuda")
        assert client is not None


class TestQwenTTSClientValidation:
    """Tests for voice profile validation."""

    def test_validate_voice_profile_rejects_missing_file(self, tmp_path):
        """_validate_voice_profile should reject missing reference audio."""
        from tts_lab.domain.entities import VoiceProfile
        from tts_lab.domain.exceptions import VoiceProfileError
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")
        profile = VoiceProfile(
            name="test",
            reference_audio_path=str(tmp_path / "nonexistent.wav"),
            reference_text="Test",
        )

        with pytest.raises(VoiceProfileError, match="not found"):
            client._validate_voice_profile(profile)

    def test_validate_voice_profile_rejects_invalid_format(self, tmp_path):
        """_validate_voice_profile should reject unsupported formats."""
        from tts_lab.domain.entities import VoiceProfile
        from tts_lab.domain.exceptions import VoiceProfileError
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        # Create a file with invalid extension
        invalid_file = tmp_path / "reference.txt"
        invalid_file.write_text("not audio")

        profile = VoiceProfile(
            name="test",
            reference_audio_path=str(invalid_file),
            reference_text="Test",
        )

        with pytest.raises(VoiceProfileError, match="Unsupported audio format"):
            client._validate_voice_profile(profile)

    def test_validate_voice_profile_accepts_wav(self, tmp_path, sample_audio_data):
        """_validate_voice_profile should accept .wav files."""
        from tts_lab.domain.entities import VoiceProfile
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        # Create valid wav file
        wav_file = tmp_path / "reference.wav"
        wav_file.write_bytes(sample_audio_data)

        profile = VoiceProfile(
            name="test",
            reference_audio_path=str(wav_file),
            reference_text="Test",
        )

        # Should not raise
        client._validate_voice_profile(profile)


class TestQwenTTSClientToAudioResult:
    """Tests for _to_audio_result method."""

    def test_to_audio_result_converts_array(self):
        """_to_audio_result should convert numpy array to AudioResult."""
        import numpy as np

        from tts_lab.domain.entities import AudioResult
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        # Create sample audio array
        sample_rate = 24000
        duration = 1.0
        samples = int(sample_rate * duration)
        audio_array = np.zeros(samples, dtype=np.float32)

        result = client._to_audio_result(audio_array, sample_rate)

        assert isinstance(result, AudioResult)
        assert result.sample_rate == sample_rate
        assert result.duration_seconds == duration
        assert len(result.audio_data) > 0


class TestQwenTTSClientContextManager:
    """Tests for context manager functionality."""

    def test_context_manager_returns_client(self):
        """Context manager should return the client."""
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        with QwenTTSClient(model_path="test_model") as client:
            assert client is not None

    @pytest.mark.skipif(
        sys.version_info >= (3, 14),
        reason="torch has compatibility issues with Python 3.14",
    )
    def test_unload_clears_model(self):
        """unload() should clear the model reference."""
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")
        client._model = Mock()  # Simulate loaded model
        client.unload()

        assert client._model is None


class TestQwenTTSClientModelLoading:
    """Tests for model loading behavior."""

    def test_ensure_model_loaded_raises_on_missing_package(self):
        """_ensure_model_loaded should raise ModelLoadError if qwen-tts not installed."""
        from tts_lab.domain.exceptions import ModelLoadError
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        with (
            patch.dict("sys.modules", {"qwen_tts": None}),
            patch("builtins.__import__", side_effect=ImportError("No module")),
            pytest.raises(ModelLoadError, match="qwen-tts package not found"),
        ):
            client._ensure_model_loaded()

    def test_ensure_model_loaded_success(self):
        """_ensure_model_loaded should load model successfully."""
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        # Mock the qwen_tts module and model
        mock_model = Mock()
        mock_model_class = Mock()
        mock_model_class.from_pretrained.return_value = mock_model

        with (
            patch.dict("sys.modules", {"qwen_tts": Mock(Qwen3TTSModel=mock_model_class)}),
            patch("torch.bfloat16", 1),
        ):
            client._ensure_model_loaded()

        assert client._model is not None
        mock_model_class.from_pretrained.assert_called_once()

    def test_generate_calls_model(self, sample_audio_data):
        """generate should call model.generate_custom_voice."""
        import numpy as np

        from tts_lab.domain.entities import TTSRequest
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        # Mock model
        mock_model = Mock()
        audio_array = np.zeros(24000, dtype=np.float32)
        mock_model.generate_custom_voice.return_value = ([audio_array], 24000)

        with patch.dict("sys.modules", {"qwen_tts": Mock()}):
            client._model = mock_model

            request = TTSRequest(text="Hello", language="English")
            result = client.generate(request)

            assert result.sample_rate == 24000
            mock_model.generate_custom_voice.assert_called_once()

    def test_generate_raises_on_error(self):
        """generate should raise TTSError on model error."""
        from tts_lab.domain.entities import TTSRequest
        from tts_lab.domain.exceptions import TTSError
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")
        client._model = Mock()
        client._model.generate_custom_voice.side_effect = RuntimeError("Model error")

        request = TTSRequest(text="Hello")

        with pytest.raises(TTSError, match="Failed to generate speech"):
            client.generate(request)

    def test_clone_voice_defaults_to_icl(self, sample_audio_data, tmp_path):
        """clone_voice should call model.generate_voice_clone in ICL mode by default."""
        import numpy as np

        from tts_lab.domain.entities import VoiceProfile
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        # Create valid reference audio
        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(sample_audio_data)

        # Mock model
        mock_model = Mock()
        audio_array = np.zeros(24000, dtype=np.float32)
        mock_model.generate_voice_clone.return_value = ([audio_array], 24000)

        client._model = mock_model
        mock_torch = Mock()
        mock_torch.cuda.is_available.return_value = True

        profile = VoiceProfile(
            name="test",
            reference_audio_path=str(ref_audio),
            reference_text="Reference text",
        )

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = client.clone_voice(profile, "Hello world")

        assert result.sample_rate == 24000
        mock_torch.manual_seed.assert_called_once_with(42)
        mock_torch.cuda.manual_seed_all.assert_called_once_with(42)
        mock_torch.mps.manual_seed.assert_called_once_with(42)
        mock_model.generate_voice_clone.assert_called_once_with(
            text="Hello world",
            language="Spanish",
            ref_audio=str(ref_audio),
            ref_text="Reference text",
            x_vector_only_mode=False,
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            repetition_penalty=1.2,
            max_new_tokens=512,
        )

    def test_clone_voice_supports_embedding_only(self, sample_audio_data, tmp_path):
        """clone_voice should support explicit embedding-only mode."""
        import numpy as np

        from tts_lab.domain.entities import VoiceProfile
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")
        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(sample_audio_data)

        mock_model = Mock()
        audio_array = np.zeros(24000, dtype=np.float32)
        mock_model.generate_voice_clone.return_value = ([audio_array], 24000)
        client._model = mock_model
        mock_torch = Mock()
        mock_torch.cuda.is_available.return_value = False

        profile = VoiceProfile(
            name="test",
            reference_audio_path=str(ref_audio),
            reference_text="Reference text",
        )

        with patch.dict("sys.modules", {"torch": mock_torch}):
            client.clone_voice(
                profile,
                "Hola mundo",
                language="Spanish",
                x_vector_only_mode=True,
                seed=123,
                temperature=0.7,
                top_p=0.9,
                top_k=40,
                repetition_penalty=1.05,
                max_new_tokens=1024,
            )

        mock_torch.manual_seed.assert_called_once_with(123)
        mock_torch.cuda.manual_seed_all.assert_not_called()
        mock_torch.mps.manual_seed.assert_called_once_with(123)
        mock_model.generate_voice_clone.assert_called_once_with(
            text="Hola mundo",
            language="Spanish",
            ref_audio=str(ref_audio),
            ref_text="Reference text",
            x_vector_only_mode=True,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.05,
            max_new_tokens=1024,
        )

    def test_clone_voice_skips_rng_seeding_when_seed_is_none(self, sample_audio_data, tmp_path):
        """clone_voice should not change RNG state when seed is None."""
        import numpy as np

        from tts_lab.domain.entities import VoiceProfile
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")
        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(sample_audio_data)

        mock_model = Mock()
        audio_array = np.zeros(24000, dtype=np.float32)
        mock_model.generate_voice_clone.return_value = ([audio_array], 24000)
        client._model = mock_model
        mock_torch = Mock()

        profile = VoiceProfile(
            name="test",
            reference_audio_path=str(ref_audio),
            reference_text="Reference text",
        )

        with patch.dict("sys.modules", {"torch": mock_torch}):
            client.clone_voice(profile, "Hola mundo", seed=None)

        mock_torch.manual_seed.assert_not_called()
        mock_torch.cuda.manual_seed_all.assert_not_called()
        mock_torch.mps.manual_seed.assert_not_called()
        assert "seed" not in mock_model.generate_voice_clone.call_args.kwargs

    def test_clone_voice_raises_on_error(self, sample_audio_data, tmp_path):
        """clone_voice should raise TTSError on model error."""
        from tts_lab.domain.entities import VoiceProfile
        from tts_lab.domain.exceptions import TTSError
        from tts_lab.infrastructure.qwen_client import QwenTTSClient

        client = QwenTTSClient(model_path="test_model")

        # Create valid reference audio
        ref_audio = tmp_path / "ref.wav"
        ref_audio.write_bytes(sample_audio_data)

        client._model = Mock()
        client._model.generate_voice_clone.side_effect = RuntimeError("Model error")

        profile = VoiceProfile(
            name="test",
            reference_audio_path=str(ref_audio),
            reference_text="Reference text",
        )

        with pytest.raises(TTSError, match="Failed to clone voice"):
            client.clone_voice(profile, "Hello world")
