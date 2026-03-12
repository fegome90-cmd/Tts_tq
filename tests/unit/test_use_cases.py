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

    def test_execute_returns_response(self):
        """Execute should return GenerateSpeechResponse."""
        from tts_lab.application.use_cases import (
            GenerateSpeechRequest,
            GenerateSpeechResponse,
            GenerateSpeechUseCase,
        )
        from tts_lab.domain.entities import AudioResult

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

        # Verify
        assert isinstance(response, GenerateSpeechResponse)
        assert response.audio_path == "/output/speech_abc123.wav"
        assert response.duration_seconds == pytest.approx(2.5)

    def test_execute_calls_tts_client_with_correct_request(self):
        """Execute should call TTSClient.generate with correct TTSRequest."""
        from tts_lab.application.use_cases import (
            GenerateSpeechRequest,
            GenerateSpeechUseCase,
        )
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
        from tts_lab.application.use_cases import (
            GenerateSpeechRequest,
            GenerateSpeechUseCase,
        )
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


class TestDTOs:
    """Tests for Request/Response DTOs."""

    def test_generate_speech_request_is_frozen(self):
        """GenerateSpeechRequest should be immutable."""
        from dataclasses import FrozenInstanceError

        from tts_lab.application.dto import GenerateSpeechRequest

        request = GenerateSpeechRequest(text="Test")
        with pytest.raises(FrozenInstanceError):
            request.text = "Changed"

    def test_generate_speech_request_defaults(self):
        """GenerateSpeechRequest should have sensible defaults."""
        from tts_lab.application.dto import GenerateSpeechRequest

        request = GenerateSpeechRequest(text="Test")
        assert request.language == "Auto"
        assert request.voice_profile_name is None

    def test_generate_speech_response_is_frozen(self):
        """GenerateSpeechResponse should be immutable."""
        from dataclasses import FrozenInstanceError

        from tts_lab.application.dto import GenerateSpeechResponse

        response = GenerateSpeechResponse(audio_path="/test.wav", duration_seconds=1.0)
        with pytest.raises(FrozenInstanceError):
            response.audio_path = "/changed.wav"
