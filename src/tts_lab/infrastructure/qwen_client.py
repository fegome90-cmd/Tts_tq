"""Infrastructure - Qwen TTS Client.

Handles all Qwen TTS side effects including model loading and inference.
"""

import logging
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, cast

from tts_lab.domain.entities import AudioResult, TTSRequest, VoiceProfile
from tts_lab.domain.exceptions import ModelLoadError, TTSError, VoiceProfileError
from tts_lab.domain.protocols import TTSClient

logger = logging.getLogger(__name__)


class QwenModelProtocol(Protocol):
    """Structural protocol for the external Qwen model object."""

    def generate_custom_voice(
        self,
        *,
        text: str,
        language: str,
        speaker: str,
        instruct: str | None,
    ) -> tuple[list[Any], int]:
        """Generate speech with a preset/custom voice."""
        ...

    def generate_voice_clone(
        self,
        *,
        text: str,
        language: str,
        ref_audio: str,
        ref_text: str,
    ) -> tuple[list[Any], int]:
        """Generate speech by cloning a reference voice."""
        ...


class QwenTTSClient(TTSClient):
    """Infrastructure - handles all Qwen TTS side effects.

    This is an impure component - it has side effects (model loading, inference).
    """

    def __init__(self, model_path: str, device: str = "mps"):
        """Initialize client with model configuration.

        Args:
            model_path: Path or HuggingFace model ID.
            device: Device for inference (mps, cuda, cpu).
        """
        self._model_path = model_path
        self._device = device
        self._model: QwenModelProtocol | None = None

    def _ensure_model_loaded(self) -> None:
        """Lazy load model to save memory.

        Raises:
            ModelLoadError: If model cannot be loaded.
        """
        if self._model is None:
            logger.info("Loading model %s on %s", self._model_path, self._device)
            try:
                import torch
                from qwen_tts import Qwen3TTSModel  # type: ignore

                self._model = cast(
                    QwenModelProtocol,
                    Qwen3TTSModel.from_pretrained(
                        self._model_path,
                        device_map=self._device,
                        dtype=torch.bfloat16,
                    ),
                )
            except ImportError as e:
                raise ModelLoadError(
                    "qwen-tts package not found. Install with: pip install qwen-tts\n"
                    "Alternative: Use ComfyUI as inference engine."
                ) from e
            except Exception as e:
                raise ModelLoadError(f"Failed to load model: {e}") from e

    def _require_model(self) -> QwenModelProtocol:
        """Return a loaded model instance or raise if loading failed."""
        self._ensure_model_loaded()
        if self._model is None:
            raise ModelLoadError("Model failed to load")
        return self._model

    def generate(self, request: TTSRequest) -> AudioResult:
        """Generate speech from text.

        Args:
            request: TTS request with text, language, and optional speaker.

        Returns:
            AudioResult with generated audio data.

        Raises:
            TTSError: If generation fails.
        """
        model = self._require_model()
        try:
            wavs, sr = model.generate_custom_voice(
                text=request.text,
                language=request.language,
                speaker=request.speaker or "Serena",
                instruct=request.instruct,
            )
            return self._to_audio_result(wavs[0], sr)
        except Exception as e:
            logger.error("TTS generation failed: %s", e)
            raise TTSError(f"Failed to generate speech: {e}") from e

    def clone_voice(self, profile: VoiceProfile, text: str) -> AudioResult:
        """Clone voice from reference audio.

        Args:
            profile: Voice profile with reference audio and text.
            text: Text to speak with cloned voice.

        Returns:
            AudioResult with generated audio data.

        Raises:
            VoiceProfileError: If profile validation fails.
            TTSError: If cloning fails.
        """
        model = self._require_model()
        self._validate_voice_profile(profile)
        try:
            wavs, sr = model.generate_voice_clone(
                text=text,
                language="Auto",
                ref_audio=profile.reference_audio_path,
                ref_text=profile.reference_text,
            )
            return self._to_audio_result(wavs[0], sr)
        except Exception as e:
            logger.error("Voice cloning failed: %s", e)
            raise TTSError(f"Failed to clone voice: {e}") from e

    def _validate_voice_profile(self, profile: VoiceProfile) -> None:
        """Validate voice profile before cloning.

        Args:
            profile: Voice profile to validate.

        Raises:
            VoiceProfileError: If profile is invalid.
        """
        ref_path = Path(profile.reference_audio_path)
        if not ref_path.exists():
            raise VoiceProfileError(f"Reference audio not found: {ref_path}")
        if ref_path.suffix.lower() not in [".wav", ".mp3", ".flac"]:
            raise VoiceProfileError(f"Unsupported audio format: {ref_path.suffix}")

    def _to_audio_result(self, wav_array: Any, sample_rate: int) -> AudioResult:
        """Convert wav array to AudioResult.

        Args:
            wav_array: Numpy array with audio data.
            sample_rate: Audio sample rate.

        Returns:
            AudioResult with WAV bytes.
        """
        import io

        import soundfile as sf

        buffer = io.BytesIO()
        sf.write(buffer, wav_array, sample_rate, format="WAV")
        duration = len(wav_array) / sample_rate

        return AudioResult(
            audio_data=buffer.getvalue(),
            sample_rate=sample_rate,
            duration_seconds=duration,
        )

    def unload(self) -> None:
        """Explicitly unload model to free memory."""
        if self._model is not None:
            self._model = None

            # Clear GPU memory if using CUDA
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            logger.info("Model unloaded from memory")

    def __enter__(self) -> "QwenTTSClient":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - unload model."""
        self.unload()


__all__ = ["QwenTTSClient"]
