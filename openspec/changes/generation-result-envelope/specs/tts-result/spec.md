# Spec: TTS Result Envelope (generation-result-envelope)

## Purpose

Define the DOMAIN contract for the outcome of a speech-generation use-case run. Replaces the flat `GenerateSpeechResponse` DTO (success-or-raise) with a 2-variant `GenerationResult` union that makes success and failure **unrepresentable as the wrong thing** under mypy-strict, plus an LLM-safe `to_agent_card` projection for agent consumers. This is a NEW capability — `openspec/specs/tts-result/spec.md` does not exist prior to this change; it is added as a full spec (not a delta) following the repo's per-capability convention (`openspec/specs/<capability>/spec.md`).

## Requirements

### Requirement: R1 — Result contract (2-variant discriminated union)

`GenerateSpeechUseCase.execute()` SHALL return `GenerationResult`, defined as the union `GenerationSuccess | GenerationFailure`. `GenerationSuccess` SHALL carry `audio_path: str`, `warnings: tuple[str, ...]`, `duration_seconds: float`, `sample_rate: int`. `GenerationFailure` SHALL carry `error: TTSError`. Both variants SHALL be frozen dataclasses in `domain/entities.py`. `GenerationSuccess` SHALL NOT carry `AudioResult.audio_data` bytes (bytes are dead weight post-`save_with_hash`; scalars duplicate `AudioResult` fields deliberately — see R1 rationale). Invalid states SHALL be structurally unrepresentable: there SHALL be no nullable `audio_path` on success and no audio fields on failure.

#### Scenario: Success variant carries path not bytes

- WHEN execute() returns `GenerationSuccess`
- THEN the instance SHALL expose `audio_path`, `warnings`, `duration_seconds`, `sample_rate`
- AND SHALL NOT expose any `audio_data` or `bytes` field.

#### Scenario: Failure variant carries typed error

- WHEN execute() returns `GenerationFailure`
- THEN the instance SHALL expose `error: TTSError`
- AND SHALL NOT expose `audio_path`, `duration_seconds`, or `sample_rate`.

#### Scenario: Variants are frozen

- WHEN a caller attempts to mutate `GenerationSuccess.audio_path` or `GenerationFailure.error`
- THEN an exception SHALL be raised (frozen dataclass).

### Requirement: R2 — Single construction site wrapping generate AND save

`execute()` SHALL be the sole construction site for `GenerationResult`. A single `try` block SHALL wrap BOTH `TTSClient.generate(...)` AND `AudioRepository.save_with_hash(...)`. On success the use case SHALL return `GenerationSuccess(audio_path, warnings, duration_seconds, sample_rate)`. On caught exception it SHALL return `GenerationFailure(error=...)`. `save_with_hash`'s `OSError` (disk/IO) SHALL NOT escape as a raised exception — it SHALL be wrapped into `GenerationFailure`. A bare `except Exception` SHALL NOT be used (it would swallow programming bugs like `KeyError`/`AttributeError`).

`GenerationFailure.error` SHALL always be a `TTSError`. The two caught branches differ in how the exception enters the typed-error contract:

- `TTSError` (raised by `generate`) is re-wrapped as-is into `GenerationFailure`.
- `OSError` from `save_with_hash` (disk/IO) is NOT a `TTSError` subclass — it SHALL be wrapped into a new domain exception `AudioStorageError(TTSError)` (added to `domain/exceptions.py` at apply) via `AudioStorageError(f"audio storage failed: {e}") from e`. This preserves the typed-error promise (`error: TTSError`) under mypy-strict for both branches.

The `except` tuple in the use case is `(TTSError, OSError)`. The `TTSError` branch is pass-through; the `OSError` branch performs the `AudioStorageError` wrapping. The card's `error_class_name` therefore reads `"AudioStorageError"` for the storage-failure branch (informative) and the original `TTSError` subclass `__name__` for the generate-failure branch.

#### Scenario: Happy path constructs Success

- GIVEN mocks for `TTSClient` (returns `AudioResult`) and `AudioRepository.save_with_hash` (returns a path)
- WHEN execute() is called
- THEN it SHALL return `GenerationSuccess` with the path, duration, and sample rate from the client.

#### Scenario: Failure from generate

- GIVEN `TTSClient.generate` raises `TTSError`
- WHEN execute() is called
- THEN it SHALL return `GenerationFailure` (NOT raise)
- AND `save_with_hash` SHALL NOT be invoked
- AND `failure.error` SHALL be the original `TTSError` subclass (pass-through).

#### Scenario: Failure from save_with_hash OSError (gate-fix trap)

- GIVEN `generate` succeeds but `AudioRepository.save_with_hash` raises `OSError`
- WHEN execute() is called
- THEN it SHALL return `GenerationFailure` (NOT raise OSError)
- AND `failure.error` SHALL be an `AudioStorageError` (a `TTSError` subclass)
- AND `isinstance(failure.error, TTSError)` SHALL be True (typed-error promise holds for both branches)
- AND `failure.error.__cause__` SHALL be the original `OSError` (preserved via `from e`).

#### Scenario: No bare except Exception

- WHEN the use case encounters a programming bug (`KeyError`, `AttributeError`, etc.) during generate or save
- THEN it SHALL propagate the exception (NOT swallow it)
- AND SHALL NOT use `except Exception` to coerce it into `GenerationFailure`.

### Requirement: R3 — Agent card whitelist sanitizer

`to_agent_card(result: GenerationResult) -> dict` SHALL be a free function in APPLICATION (`application/agent_card.py`), not a method on a domain entity. The returned dict SHALL contain only keys from the whitelist `{status, audio_path?, error_class_name?}`: `status` is `"success"` or `"failure"`; `audio_path` appears ONLY on success; `error_class_name` (the class `__name__`) appears ONLY on failure. The card SHALL NEVER include `str(error)`, the error message body, the request text, the speaker, the language, or any secret/credential. This is fail-closed: anything not in the whitelist SHALL be omitted.

#### Scenario: Success card shape

- WHEN `to_agent_card(GenerationSuccess(...))` is called
- THEN the dict SHALL equal `{"status": "success", "audio_path": <path>}`
- AND SHALL NOT contain `error_class_name`, the request text, or any byte content.

#### Scenario: Sanitization — no leak (gate-fix trap)

- GIVEN `GenerationFailure` whose `TTSError` message contains a secret-like string, raw HTTP body, and the request text
- WHEN `to_agent_card` is called
- THEN the dict SHALL contain only `{"status": "failure", "error_class_name": <class name>}`
- AND SHALL NOT contain the secret, the error message body, or the request text as a substring.

### Requirement: R4 — DTO deletion in lockstep

`GenerateSpeechResponse` SHALL be deleted from `application/dto.py`, from the import at `application/__init__.py` (L3), AND from the `__all__` list at `application/__init__.py` (L6) in the same change. `GenerateSpeechRequest` SHALL remain. After the change, `from tts_lab.application import GenerateSpeechResponse` SHALL raise `ImportError`.

#### Scenario: Package import still works (gate-fix trap)

- WHEN `from tts_lab.application import GenerateSpeechRequest, GenerateSpeechUseCase` is executed
- THEN the import SHALL succeed with no `ImportError`
- AND `from tts_lab.application import GenerateSpeechResponse` SHALL raise `ImportError`.

### Requirement: R5 — CLI generate uses match

The CLI `generate` command SHALL consume the result via `match` on `GenerationResult`. On `GenerationSuccess` it SHALL print `audio_path` and `duration_seconds` and exit 0. On `GenerationFailure` it SHALL print `error_class_name` and exit non-zero. The `generate` command SHALL NOT use `except Exception` to handle `GenerationFailure` (the failure is now data, not a raised exception). The CLI `clone` command SHALL be UNCHANGED.

#### Scenario: CLI success branch

- WHEN `generate` runs and `execute()` returns `GenerationSuccess`
- THEN the CLI SHALL print the path and duration and exit 0.

#### Scenario: CLI failure branch

- WHEN `generate` runs and `execute()` returns `GenerationFailure`
- THEN the CLI SHALL print the error class name and exit non-zero
- AND SHALL NOT print the error message body.

### Requirement: R6 — Scope boundary (non-goals)

The following are explicitly OUT OF SCOPE for this change and SHALL NOT be introduced by it:
- **Truncation-default-policy** — no client raises `TruncatedAudioError`; the `warnings` tuple is the ready slot when one does. Deferred.
- **Qwen typed-exception subclasses** (incl. `AudioFormatError` dead-code removal) — Qwen flattens to generic `TTSError`; separate seam. Deferred.
- **`CloneVoiceUseCase`** + protocol widening — CLI clone bypasses `execute()`; the envelope cannot reach it. Deferred.
- **Raw-body DEBUG log removal** in `inworld_client` — defense-in-depth; the R3 sanitizer already hardens the agent card surface this change. Deferred.
- **MP3 branch removal** — shares the storage seam, not the envelope seam. Deferred.
- **`save_with_hash` hash-collision fix** — shares the storage seam, not the envelope seam. Deferred.

#### Scenario: Change stays within scope

- WHEN the change is applied
- THEN it SHALL NOT modify `clone` behavior, the Inworld client truncation path, the Qwen exception class hierarchy, or the `save_with_hash` hashing scheme.

## NON-GOALS (consolidated)

See R6. This change is a pure in-memory contract refactor of the generate-path; no persisted state, migrations, or on-disk schema changes. Clients keep their `AudioResult` / raise-`TTSError` contract throughout (no flag-day).
