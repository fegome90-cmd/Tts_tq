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
        provider: Active TTS provider ("qwen" or "inworld"). Owned by config;
            read from the TTS_PROVIDER env var so the CLI/factory never parse
            raw env strings themselves.
    """

    model_path: str
    device: str = "mps"  # Default for Apple Silicon
    output_dir: str = "output"
    voices_dir: str = "voice_profiles"
    provider: str = "qwen"

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
            provider=os.getenv("TTS_PROVIDER", "qwen"),
        )


@dataclass(frozen=True)
class InworldConfig:
    """Configuration for the Inworld cloud TTS provider.

    Attributes:
        api_key: Base64-encoded ``keyId:keySecret`` used for HTTP Basic auth.
            May be empty here; the factory owns the eager presence check.
        base_url: Inworld API root (no trailing slash).
        default_voice_id: Preset voice used when a request carries no speaker.
        audio_encoding: "LINEAR16" (default, WAV-friendly) or "MP3".
        http_timeout_seconds: Per-request socket timeout passed to
            ``urllib.request.urlopen``. Bounds both the connect and read phases
            so a non-responsive Inworld endpoint cannot hang the client forever
            (the previous default of ``None`` blocked indefinitely). A timed-out
            call raises ``socket.timeout`` which :func:`_wrap_urllib_error` maps
            to :class:`InworldConnectionError`.
    """

    api_key: str
    base_url: str = "https://api.inworld.ai"
    default_voice_id: str = "Sarah"
    audio_encoding: str = "LINEAR16"
    http_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "InworldConfig":
        """Load Inworld configuration from environment variables.

        Does NOT raise on a missing API key — the factory performs the eager
        presence check so callers get a single, well-typed config error at
        client construction rather than at first network call.

        Returns:
            InworldConfig with values from environment or defaults.
        """
        return cls(
            api_key=os.getenv("INWORLD_API_KEY", ""),
            base_url=os.getenv("INWORLD_BASE_URL", "https://api.inworld.ai"),
            default_voice_id=os.getenv("INWORLD_DEFAULT_VOICE_ID", "Sarah"),
            audio_encoding=os.getenv("INWORLD_AUDIO_ENCODING", "LINEAR16"),
            http_timeout_seconds=float(
                os.getenv("INWORLD_HTTP_TIMEOUT", "30.0")
            ),
        )


__all__ = ["InworldConfig", "TTSConfig"]
