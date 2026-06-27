"""Application-layer LLM-safe projection of GenerationResult.

`to_agent_card` is a fail-closed whitelist sanitizer that renders the domain
result as a dict safe for LLM consumption. It MUST NEVER include `str(error)`,
the error message body, request text, speaker, language, secrets, or any
credentials that may appear in TTSError messages.

Whitelist policy (generation-result-envelope R3):
  - `status`: "success" | "failure" (always present)
  - `audio_path`: present ONLY on success
  - `error_class_name`: present ONLY on failure (class __name__, not message)
"""

from tts_lab.domain.entities import (
    GenerationFailure,
    GenerationResult,
    GenerationSuccess,
)

__all__ = ["to_agent_card"]


def to_agent_card(result: GenerationResult) -> dict[str, str]:
    """Project a GenerationResult into an LLM-safe dict.

    Fail-closed sanitizer: anything not in the whitelist {status, audio_path?,
    error_class_name?} is omitted. NEVER calls `str(result.error)`.

    Args:
        result: The generation result (Success or Failure variant).

    Returns:
        Dict with only whitelisted string keys and string values:
        - Success: {"status": "success", "audio_path": <path>}
        - Failure: {"status": "failure", "error_class_name": <class name>}
    """
    # Status strings MUST match spec R3 exactly: "success" / "failure"
    # (NOT "ok" / "error" — gate-fix HIGH: status drift).
    match result:
        case GenerationSuccess():
            return {
                "status": "success",
                "audio_path": result.audio_path,
            }
        case GenerationFailure():
            return {
                "status": "failure",
                # Class __name__ only — NEVER str(result.error).
                "error_class_name": type(result.error).__name__,
            }
        case _:
            # Fail-closed defense: mypy makes the match exhaustive statically,
            # but Python does not enforce GenerationResult at runtime. An
            # unexpected value (untyped caller, broken mock, deserialization,
            # `Any`, or a future variant added without updating this sanitizer)
            # MUST raise rather than fall through and implicitly return None,
            # which would contradict both the `dict[str, str]` return type and
            # the "fail-closed" promise. Generic message — no object data.
            raise TypeError("Unsupported generation result type")
