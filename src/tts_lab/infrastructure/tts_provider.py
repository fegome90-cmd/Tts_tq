"""TTS provider factory.

Selects a :class:`tts_lab.domain.protocols.TTSClient` implementation based on
the active provider configured in :class:`tts_lab.infrastructure.config.TTSConfig`.
The CLI uses this factory instead of hardwiring a specific provider, so
``TTS_PROVIDER`` (default ``qwen``) is the single switch.

Construction is EAGER: a missing ``INWORLD_API_KEY`` surfaces as a typed
:class:`tts_lab.domain.exceptions.TTSError` at factory call time (fail-fast),
not deferred to the first network request.
"""

from tts_lab.domain.exceptions import TTSError
from tts_lab.domain.protocols import TTSClient
from tts_lab.infrastructure.config import TTSConfig
from tts_lab.infrastructure.qwen_client import QwenTTSClient


def create_tts_client(settings: TTSConfig) -> TTSClient:
    """Build the TTS client selected by ``settings.provider``.

    Both concrete implementations (:class:`QwenTTSClient`,
    :class:`InworldTTSClient`) are also context managers, so callers may use
    ``with create_tts_client(...) as client:``. The domain :class:`TTSClient`
    protocol deliberately omits resource-management methods; the CLI casts to
    a context-manager-aware view locally where it needs the ``with`` block.

    Args:
        settings: TTS configuration. ``settings.provider`` selects the
            implementation; ``model_path``/``device`` configure Qwen.

    Returns:
        A :class:`TTSClient` for the requested provider.

    Raises:
        TTSError: If provider is ``"inworld"`` and ``INWORLD_API_KEY`` is
            missing or empty (config error at construction).
        ValueError: If ``settings.provider`` is not a known provider.
    """
    provider = settings.provider
    if provider == "qwen":
        return QwenTTSClient(
            model_path=settings.model_path, device=settings.device
        )
    if provider == "inworld":
        # EAGER key check — fail-fast at construction, not first request.
        from tts_lab.infrastructure.config import InworldConfig
        from tts_lab.infrastructure.inworld_client import InworldTTSClient

        inworld_config = InworldConfig.from_env()
        if not inworld_config.api_key:
            raise TTSError(
                "INWORLD_API_KEY is not set; required when TTS_PROVIDER=inworld"
            )
        return InworldTTSClient(inworld_config)
    raise ValueError(f"Unknown provider: {provider!r}")


__all__ = ["create_tts_client"]
