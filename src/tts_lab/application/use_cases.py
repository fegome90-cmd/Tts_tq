"""Application layer use cases.

Use cases orchestrate domain logic and delegate side effects to infrastructure.
"""

from tts_lab.application.dto import GenerateSpeechRequest, GenerateSpeechResponse
from tts_lab.domain.entities import TTSRequest
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

    def execute(self, request: GenerateSpeechRequest) -> GenerateSpeechResponse:
        """Execute speech generation.

        Args:
            request: Request with text, language, and optional voice profile.

        Returns:
            Response with audio path and duration.
        """
        # Create domain request
        tts_request = TTSRequest(
            text=request.text,
            language=request.language,
        )

        # Generate speech (side effect in infrastructure)
        audio = self._tts.generate(tts_request)

        # Save audio (side effect in infrastructure)
        # Repository handles filename generation internally
        path = self._repo.save_with_hash(audio, request.text, request.language)

        return GenerateSpeechResponse(
            audio_path=path,
            duration_seconds=audio.duration_seconds,
        )


__all__ = ["GenerateSpeechUseCase"]
