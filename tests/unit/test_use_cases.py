"""Tests for application layer - GenerateSpeechUseCase.

TDD RED Phase: These tests define expected behavior BEFORE implementation.
"""

from unittest.mock import Mock

import pytest


class TestGenerateSpeechUseCase:
    """Tests for GenerateSpeechUseCase."""

    def test_use_case_exists(self):
        """GenerateSpeechUseCase should exist."""
        from tts_lab.application.use_cases import GenerateSpeechUseCase

        assert GenerateSpeechUseCase is not None

    def test_use_case_requires_dependencies(self):
        """GenerateSpeechUseCase should require TTSClient and AudioRepository."""
        from tts_lab.application.use_cases import GenerateSpeechUseCase

        mock_client = Mock()
        mock_repo = Mock()

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)

        assert use_case is not None

    def test_execute_returns_generation_success(self):
        """Execute should return GenerationSuccess with path/warnings/duration/sample_rate."""
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, GenerationSuccess

        # Setup mocks
        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake_audio",
            sample_rate=24000,
            duration_seconds=2.5,
        )

        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/speech_abc123.wav"

        # Execute
        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Hello world", language="English")
        response = use_case.execute(request)

        # Verify GenerationSuccess variant with all scalars
        assert isinstance(response, GenerationSuccess)
        assert response.audio_path == "/output/speech_abc123.wav"
        assert response.warnings == ()
        assert response.duration_seconds == pytest.approx(2.5)
        assert response.sample_rate == 24000

    def test_execute_failure_from_generate(self):
        """TTSError from generate -> GenerationFailure pass-through (R2)."""
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import GenerationFailure
        from tts_lab.domain.exceptions import ModelLoadError, TTSError

        mock_client = Mock()
        mock_client.generate.side_effect = ModelLoadError("model not found")
        mock_repo = Mock()

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Hi")
        response = use_case.execute(request)

        assert isinstance(response, GenerationFailure)
        assert isinstance(response.error, ModelLoadError)
        assert isinstance(response.error, TTSError)  # typed-error promise
        # save_with_hash MUST NOT be invoked when generate fails.
        mock_repo.save_with_hash.assert_not_called()

    def test_execute_failure_from_save_with_hash_oserror(self):
        """OSError from save_with_hash -> GenerationFailure(AudioStorageError) (R2 trap)."""
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, GenerationFailure
        from tts_lab.domain.exceptions import AudioStorageError, TTSError

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.side_effect = OSError("disk full")

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Hi")
        response = use_case.execute(request)

        # OSError MUST be wrapped into AudioStorageError(TTSError), NOT escape.
        assert isinstance(response, GenerationFailure)
        assert isinstance(response.error, AudioStorageError)
        assert isinstance(response.error, TTSError)  # typed-error promise holds
        # Original OSError preserved via `from e` (exception chaining).
        assert isinstance(response.error.__cause__, OSError)
        assert "disk full" in str(response.error)

    def test_execute_calls_tts_client_with_correct_request(self):
        """Execute should call TTSClient.generate with correct TTSRequest."""
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, TTSRequest

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/test.wav"

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Test text", language="Spanish")
        use_case.execute(request)

        # Verify TTSClient was called with correct TTSRequest
        mock_client.generate.assert_called_once()
        called_request = mock_client.generate.call_args[0][0]
        assert isinstance(called_request, TTSRequest)
        assert called_request.text == "Test text"
        assert called_request.language == "Spanish"

    def test_execute_calls_repo_save_with_hash(self):
        """Execute should call AudioRepository.save_with_hash with correct params."""
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/test.wav"

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Test", language="Auto")
        use_case.execute(request)

        # Verify repo was called
        mock_repo.save_with_hash.assert_called_once()
        call_args = mock_repo.save_with_hash.call_args
        assert call_args[0][1] == "Test"  # text
        assert call_args[0][2] == "Auto"  # language

    def test_execute_threads_speaker_into_tts_request(self):
        """Execute should populate TTSRequest.speaker from the DTO."""
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, TTSRequest

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/test.wav"

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Hello", language="English", speaker="Dennis")
        use_case.execute(request)

        mock_client.generate.assert_called_once()
        called_request = mock_client.generate.call_args[0][0]
        assert isinstance(called_request, TTSRequest)
        assert called_request.speaker == "Dennis"

    def test_execute_default_speaker_is_none(self):
        """Regression guard: no speaker supplied → TTSRequest.speaker is None.

        The Qwen client maps ``request.speaker or "Serena"`` (qwen_client.py:96),
        so a None speaker preserves the pre-change default-path behavior.
        """
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, TTSRequest

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/test.wav"

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Hello", language="English")
        use_case.execute(request)

        called_request = mock_client.generate.call_args[0][0]
        assert isinstance(called_request, TTSRequest)
        assert called_request.speaker is None

    def test_execute_threads_instruct_into_tts_request(self):
        """Execute should populate TTSRequest.instruct from the DTO.

        Mirror of ``--speaker`` threading: the CLI already accepts ``--instruct``/
        ``-i`` (cli.py:170) and the Qwen client already consumes
        ``request.instruct`` (qwen_client.py:97), but the DTO/use-case dropped it.
        """
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, TTSRequest

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/test.wav"

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Hello", language="English", instruct="speak calmly")
        use_case.execute(request)

        mock_client.generate.assert_called_once()
        called_request = mock_client.generate.call_args[0][0]
        assert isinstance(called_request, TTSRequest)
        assert called_request.instruct == "speak calmly"

    def test_execute_default_instruct_is_none(self):
        """Regression guard: no instruct supplied → TTSRequest.instruct is None.

        ``instruct`` defaults to None, so a missing ``-i`` preserves the
        pre-change default-path behavior. Passing ``-i <text>`` is a
        DELIBERATE behavior change (activates Qwen instruction-tuning).
        """
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, TTSRequest

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/test.wav"

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        request = GenerateSpeechRequest(text="Hello", language="English")
        use_case.execute(request)

        called_request = mock_client.generate.call_args[0][0]
        assert isinstance(called_request, TTSRequest)
        assert called_request.instruct is None


class TestQwenDefaultSpeakerContractGuard:
    """Contract guard for the default no-``-s`` Qwen path (Phase 6.3).

    NOT a byte-identical output snapshot — model load is infeasible at unit
    speed. This locks the INPUT WIRING contract: when the user supplies no
    speaker, ``TTSRequest.speaker is None``, which Qwen maps to "Serena" via
    ``request.speaker or "Serena"`` (qwen_client.py:96). Using ``-s <name>``
    is a DELIBERATE behavior change per the HONOR decision (spec MODIFIED
    req ``Qwen -s semantics — HONOR``), NOT a regression.
    """

    def test_default_no_speaker_yields_none_tts_request_speaker(self):
        """No speaker supplied -> TTSRequest.speaker is None -> Qwen Serena."""
        from tts_lab.application.dto import GenerateSpeechRequest
        from tts_lab.application.use_cases import GenerateSpeechUseCase
        from tts_lab.domain.entities import AudioResult, TTSRequest

        mock_client = Mock()
        mock_client.generate.return_value = AudioResult(
            audio_data=b"fake", sample_rate=24000, duration_seconds=1.0
        )
        mock_repo = Mock()
        mock_repo.save_with_hash.return_value = "/output/test.wav"

        use_case = GenerateSpeechUseCase(tts_client=mock_client, audio_repo=mock_repo)
        # Mirrors the CLI default path: no --speaker -> GenerateSpeechRequest(text=...).
        request = GenerateSpeechRequest(text="Hello world")
        use_case.execute(request)

        called = mock_client.generate.call_args[0][0]
        assert isinstance(called, TTSRequest)
        # CONTRACT: speaker is None at the boundary, so qwen_client.py:96's
        # `request.speaker or "Serena"` resolves to "Serena" — preserving the
        # pre-change default-path behavior.
        assert called.speaker is None

    def test_qwen_speaker_or_serena_resolution_is_serena_when_none(self):
        """Lock the qwen_client.py:96 resolution logic: None -> 'Serena'."""
        # This mirrors exactly qwen_client.py:96: `request.speaker or "Serena"`.
        speaker = None
        assert (speaker or "Serena") == "Serena"


class TestDTOs:
    """Tests for Request/Response DTOs."""

    def test_generate_speech_request_is_frozen(self):
        """GenerateSpeechRequest should be immutable."""
        from dataclasses import FrozenInstanceError

        from tts_lab.application.dto import GenerateSpeechRequest

        request = GenerateSpeechRequest(text="Test")
        with pytest.raises(FrozenInstanceError):
            setattr(request, "text", "Changed")  # noqa: B010

    def test_generate_speech_request_defaults(self):
        """GenerateSpeechRequest should have sensible defaults."""
        from tts_lab.application.dto import GenerateSpeechRequest

        request = GenerateSpeechRequest(text="Test")
        assert request.language == "Auto"
        assert request.voice_profile_name is None

    def test_generate_speech_request_has_speaker_default_none(self):
        """GenerateSpeechRequest should accept speaker, defaulting to None."""
        from tts_lab.application.dto import GenerateSpeechRequest

        request = GenerateSpeechRequest(text="Test")
        assert request.speaker is None

        with_speaker = GenerateSpeechRequest(text="Test", speaker="Sarah")
        assert with_speaker.speaker == "Sarah"

    def test_generate_speech_request_has_instruct_default_none(self):
        """GenerateSpeechRequest should accept instruct, defaulting to None.

        Mirror of the speaker DTO test. Backs the ``--instruct``/``-i`` CLI flag.
        """
        from tts_lab.application.dto import GenerateSpeechRequest

        request = GenerateSpeechRequest(text="Test")
        assert request.instruct is None

        with_instruct = GenerateSpeechRequest(text="Test", instruct="speak calmly")
        assert with_instruct.instruct == "speak calmly"

    def test_generate_speech_response_is_removed(self):
        """GenerateSpeechResponse MUST be deleted from dto.py (R4)."""
        import importlib

        dto = importlib.import_module("tts_lab.application.dto")
        assert not hasattr(dto, "GenerateSpeechResponse")
