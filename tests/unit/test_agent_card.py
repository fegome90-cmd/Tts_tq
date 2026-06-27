"""Tests for application/agent_card.py sanitizer (generation-result-envelope R3).

TDD RED Phase: Defines the LLM-safe `to_agent_card` projection whitelist BEFORE
implementation. Fail-closed sanitizer: only {status, audio_path?, error_class_name?}
keys are emitted; NEVER str(error), error body, request text, or secrets.
"""

from typing import cast

import pytest

from tts_lab.application.agent_card import to_agent_card
from tts_lab.domain.entities import (
    GenerationFailure,
    GenerationResult,
    GenerationSuccess,
)
from tts_lab.domain.exceptions import ModelLoadError


class TestToAgentCardSuccess:
    """Success-variant card shape (R3)."""

    def test_success_card_has_status_and_audio_path(self):
        """Success card must contain status='success' and audio_path."""
        result = GenerationSuccess(
            audio_path="/output/x.wav",
            warnings=(),
            duration_seconds=2.5,
            sample_rate=24000,
        )
        card = to_agent_card(result)
        assert card == {"status": "success", "audio_path": "/output/x.wav"}

    def test_success_card_has_no_duration_no_warnings_no_sample_rate(self):
        """Success card whitelist strips duration/warnings/sample_rate."""
        result = GenerationSuccess(
            audio_path="/x.wav",
            warnings=("truncated",),
            duration_seconds=2.5,
            sample_rate=24000,
        )
        card = to_agent_card(result)
        # Whitelist enforces — extras stripped.
        assert "duration_seconds" not in card
        assert "warnings" not in card
        assert "sample_rate" not in card
        assert set(card.keys()) == {"status", "audio_path"}


class TestToAgentCardFailure:
    """Failure-variant card shape + sanitization (R3, gate-fix trap)."""

    def test_failure_card_has_status_and_error_class_name(self):
        """Failure card must contain status='failure' and error_class_name."""
        result = GenerationFailure(error=ModelLoadError("boom"))
        card = to_agent_card(result)
        assert card == {"status": "failure", "error_class_name": "ModelLoadError"}

    def test_failure_card_never_includes_str_error(self):
        """Card MUST NEVER leak str(error) — secrets, bodies, request text."""
        noisy = ModelLoadError("KEY=sk-live-xxxx noisy body")
        result = GenerationFailure(error=noisy)
        card = to_agent_card(result)
        card_text = " ".join(f"{k}={v}" for k, v in card.items())
        assert "sk-live" not in card_text
        assert "noisy body" not in card_text
        assert "KEY=" not in card_text
        # error_class_name is the class __name__, not the message.
        assert card["error_class_name"] == "ModelLoadError"

    def test_failure_card_omits_audio_path_key_entirely(self):
        """Failure card MUST NOT have audio_path key (not None — absent)."""
        result = GenerationFailure(error=ModelLoadError("boom"))
        card = to_agent_card(result)
        assert "audio_path" not in card  # key absent, NOT None

    def test_card_values_are_all_str(self):
        """All card values MUST be str (LLM-safe transport)."""
        success = GenerationSuccess(
            audio_path="/x.wav",
            warnings=(),
            duration_seconds=1.0,
            sample_rate=24000,
        )
        failure = GenerationFailure(error=ModelLoadError("boom"))
        for card in (to_agent_card(success), to_agent_card(failure)):
            assert all(isinstance(v, str) for v in card.values())
            assert all(isinstance(k, str) for k in card)


class TestToAgentCardFailClosed:
    """Runtime fail-closed defense for values outside the 2-variant union (R3).

    mypy makes the `match` exhaustive at static-analysis time, but Python does
    not enforce the GenerationResult contract at runtime. An unexpected object
    can reach `to_agent_card` via untyped code, a broken mock, deserialization,
    `Any`, or a future variant added to the union without updating the
    sanitizer. The function MUST fail closed (raise) rather than fall through
    the match and implicitly return None, which would contradict both the
    `dict[str, str]` return annotation and the "fail-closed sanitizer" promise.
    """

    def test_unsupported_result_fails_closed(self):
        """Non-variant object MUST raise TypeError, not return None."""
        unsupported = cast(GenerationResult, object())

        with pytest.raises(TypeError, match="Unsupported generation result"):
            to_agent_card(unsupported)
