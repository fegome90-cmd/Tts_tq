"""Application layer use cases.

Use cases orchestrate domain logic and delegate side effects to infrastructure.
"""

from tts_lab.application.dto import GenerateSpeechRequest
from tts_lab.domain.entities import (
    GenerationFailure,
    GenerationResult,
    GenerationSuccess,
    TTSRequest,
)
from tts_lab.domain.exceptions import AudioStorageError, TTSError
from tts_lab.domain.protocols import AudioRepository, TTSClient


class GenerateSpeechUseCase:
    """Orchestrates speech generation using TTSClient and AudioRepository.

    This is pure orchestration - all side effects are delegated to infrastructure.
    """

    def __init__(self, tts_client: TTSClient, audio_repo: AudioRepository):
        """Initialize use case with dependencies.

        Args:
            tts_client: TTS client for generating speech.
            audio_repo: Repository for saving audio files.
        """
        self._tts = tts_client
        self._repo = audio_repo

    def execute(self, request: GenerateSpeechRequest) -> GenerationResult:
        """Execute speech generation.

        Single construction site for GenerationResult. One try block wraps BOTH
        generate() AND save_with_hash(). On caught exception returns
        GenerationFailure (data, not raised). NO bare `except Exception` —
        programming bugs (KeyError/AttributeError) MUST propagate.

        Args:
            request: Request with text, language, and optional voice profile.

        Returns:
            GenerationSuccess on success, GenerationFailure on caught TTS or
            disk/IO error.
        """
        tts_request = TTSRequest(
            text=request.text,
            language=request.language,
            speaker=request.speaker,
            instruct=request.instruct,
        )

        try:
            audio = self._tts.generate(tts_request)
            path = self._repo.save_with_hash(audio, request.text, request.language)
        except TTSError as e:
            # Pass-through: generate() raised a typed TTS error.
            return GenerationFailure(e)
        except OSError as e:
            # Wrap disk/IO from save_with_hash into AudioStorageError(TTSError)
            # so GenerationFailure.error: TTSError holds for BOTH branches
            # (mypy-strict). Original OSError preserved via explicit chaining.
            wrapped = AudioStorageError(f"audio storage failed: {e}")
            wrapped.__cause__ = e
            return GenerationFailure(wrapped)

        return GenerationSuccess(
            audio_path=path,
            warnings=(),
            duration_seconds=audio.duration_seconds,
            sample_rate=audio.sample_rate,
        )


__all__ = ["GenerateSpeechUseCase"]
