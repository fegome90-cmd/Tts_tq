"""Infrastructure configuration for TTS Lab.

Configuration loaded from environment variables.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TTSConfig:
    """Configuration for TTS service.

    Attributes:
        model_path: Path or HuggingFace model ID.
        device: Device for inference (mps, cuda, cpu).
        output_dir: Directory for generated audio files.
        voices_dir: Directory for voice profiles.
    """

    model_path: str
    device: str = "mps"  # Default for Apple Silicon
    output_dir: str = "output"
    voices_dir: str = "voice_profiles"

    @classmethod
    def from_env(cls) -> "TTSConfig":
        """Load configuration from environment variables.

        Returns:
            TTSConfig with values from environment or defaults.
        """
        return cls(
            model_path=os.getenv("TTS_MODEL_PATH", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"),
            device=os.getenv("TTS_DEVICE", "mps"),
            output_dir=os.getenv("TTS_OUTPUT_DIR", "output"),
            voices_dir=os.getenv("TTS_VOICES_DIR", "voice_profiles"),
        )
