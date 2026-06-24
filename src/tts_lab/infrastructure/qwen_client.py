"""Infrastructure - Qwen TTS Client.

Handles all Qwen TTS side effects including model loading and inference.
"""

import logging
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from tts_lab.domain.entities import AudioResult, TTSRequest, VoiceProfile
from tts_lab.domain.exceptions import ModelLoadError, TTSError, VoiceProfileError
from tts_lab.domain.protocols import TTSClient

logger = logging.getLogger(__name__)


DEFAULT_CLONE_LANGUAGE: Literal["Spanish", "English", "Auto"] = "Spanish"
DEFAULT_CLONE_SEED = 42
# Sampling defaults anchored to autoresearch O-1 (closure 2026-06-23).
# Baseline (transformers defaults: repetition_penalty=1.05, top_p=1.0,
# temperature=0.9, max_new_tokens=2048) caused repetition collapse in ICL
# mode. These values prevent loops while staying close to the model's
# intended range.
DEFAULT_CLONE_TEMPERATURE = 0.7
DEFAULT_CLONE_TOP_P = 0.9
DEFAULT_CLONE_TOP_K = 50
DEFAULT_CLONE_REPETITION_PENALTY = 1.2
DEFAULT_CLONE_MAX_NEW_TOKENS = 512


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
        self._model: Any = None  # Lazy loading

    def _ensure_model_loaded(self) -> None:
        """Lazy load model to save memory.

        Raises:
            ModelLoadError: If model cannot be loaded.
        """
        if self._model is None:
            logger.info(f"Loading model {self._model_path} on {self._device}")
            try:
                # Try to import qwen-tts package
                import torch
                from qwen_tts import Qwen3TTSModel  # type: ignore

                # Pyright false positive: torch.bfloat16 is a dynamic module
                # attribute not in the stub's public export list, but it is valid
                # at runtime. Verified with torch 2.x.
                self._model = Qwen3TTSModel.from_pretrained(
                    self._model_path,
                    device_map=self._device,
                    dtype=torch.bfloat16,  # pyright: ignore[reportPrivateImportUsage]
                )
            except ImportError as e:
                raise ModelLoadError(
                    "qwen-tts package not found. Install with: pip install qwen-tts\n"
                    "Alternative: Use ComfyUI as inference engine."
                ) from e
            except Exception as e:
                raise ModelLoadError(f"Failed to load model: {e}") from e

    def generate(self, request: TTSRequest) -> AudioResult:
        """Generate speech from text.

        Args:
            request: TTS request with text, language, and optional speaker.

        Returns:
            AudioResult with generated audio data.

        Raises:
            TTSError: If generation fails.
        """
        self._ensure_model_loaded()
        assert self._model is not None
        try:
            wavs, sr = self._model.generate_custom_voice(
                text=request.text,
                language=request.language,
                speaker=request.speaker or "Serena",
                instruct=request.instruct,
            )
            return self._to_audio_result(wavs[0], sr)
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise TTSError(f"Failed to generate speech: {e}") from e

    def clone_voice(
        self,
        profile: VoiceProfile,
        text: str,
        *,
        language: str = DEFAULT_CLONE_LANGUAGE,
        x_vector_only_mode: bool = True,
        seed: int | None = DEFAULT_CLONE_SEED,
        temperature: float = DEFAULT_CLONE_TEMPERATURE,
        top_p: float = DEFAULT_CLONE_TOP_P,
        top_k: int = DEFAULT_CLONE_TOP_K,
        repetition_penalty: float = DEFAULT_CLONE_REPETITION_PENALTY,
        max_new_tokens: int = DEFAULT_CLONE_MAX_NEW_TOKENS,
    ) -> AudioResult:
        """Clone voice from reference audio.

        Args:
            profile: Voice profile with reference audio and text.
            text: Text to speak with cloned voice.
            language: Target synthesis language. Defaults to Spanish.
            x_vector_only_mode: Use embedding-only cloning when True; ICL when False.
            seed: Sampling seed for reproducible cloning. Use None to leave RNG state unchanged.
            temperature: Sampling temperature.
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling threshold.
            repetition_penalty: Penalty for repeated tokens.
            max_new_tokens: Maximum generated tokens.

        Returns:
            AudioResult with generated audio data.

        Raises:
            VoiceProfileError: If profile validation fails.
            TTSError: If cloning fails.
        """
        self._ensure_model_loaded()
        assert self._model is not None
        self._validate_voice_profile(profile)
        try:
            self._seed_generation(seed)
            wavs, sr = self._model.generate_voice_clone(
                text=text,
                language=language,
                ref_audio=profile.reference_audio_path,
                ref_text=profile.reference_text,
                x_vector_only_mode=x_vector_only_mode,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                max_new_tokens=max_new_tokens,
            )
            return self._to_audio_result(wavs[0], sr)
        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            raise TTSError(f"Failed to clone voice: {e}") from e

    def _seed_generation(self, seed: int | None) -> None:
        """Seed PyTorch RNGs before voice cloning generation."""
        if seed is None:
            return

        import torch

        torch.manual_seed(seed)

        cuda = getattr(torch, "cuda", None)
        if cuda is not None and cuda.is_available():
            cuda.manual_seed_all(seed)

        mps = getattr(torch, "mps", None)
        mps_manual_seed = getattr(mps, "manual_seed", None)
        if callable(mps_manual_seed):
            mps_manual_seed(seed)

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
