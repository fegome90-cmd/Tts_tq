# Apply Progress: generation-result-envelope

**Phase**: apply (completed) → next: verify
**Mode**: TDD strict (RED → GREEN → REFACTOR per task)
**Date**: 2026-06-26

## Files Created

| File | Purpose |
|------|---------|
| `src/tts_lab/application/agent_card.py` | `to_agent_card(result)` free function — fail-closed whitelist sanitizer (R3). |
| `tests/unit/test_agent_card.py` | 6 tests covering whitelist + sanitization trap. |

## Files Modified

| File | Change |
|------|--------|
| `src/tts_lab/domain/entities.py` | Added `GenerationSuccess`, `GenerationFailure` (frozen), `type GenerationResult = ...` (Python 3.12 `type` statement, not `TypeAlias`). Updated `__all__`. |
| `src/tts_lab/domain/exceptions.py` | Added `AudioStorageError(TTSError)` for OSError wrapping (R2 trap). Updated `__all__`. |
| `src/tts_lab/application/use_cases.py` | `execute() -> GenerationResult`; single try/except wrapping generate+save; `except TTSError` pass-through, `except OSError` wraps into `AudioStorageError(...) from e`. NO bare `except Exception`. |
| `src/tts_lab/application/dto.py` | Deleted `GenerateSpeechResponse`. |
| `src/tts_lab/application/__init__.py` | Lockstep removal of `GenerateSpeechResponse` from import + `__all__` (R4 gate-fix HIGH). |
| `src/tts_lab/cli.py` | `generate` command: `match result:` on Success/Failure; moved `match` OUT of try (failure is data, not raised); kept narrow `except Exception` for INIT-ONLY failures (model load, provider guard) with `except typer.Exit: raise` re-raise. |
| `tests/unit/test_entities.py` | +3 test classes (TestGenerationSuccess, TestGenerationFailure, TestGenerationResultUnion). |
| `tests/unit/test_use_cases.py` | Rewrote `test_execute_returns_response` → `test_execute_returns_generation_success`; +2 failure-path tests (generate + save_with_hash OSError); replaced `test_generate_speech_response_is_frozen` with `test_generate_speech_response_is_removed` (uses `importlib.import_module` + `hasattr` — `pytest.raises(ImportError)` did not catch the `from X import Y` form reliably). |
| `tests/unit/test_cli.py` | +1 test class `TestGenerateCommandResultEnvelope` (success branch + failure branch with noisy body sanitization check). |

## TDD Evidence (per task)

| Task | RED | GREEN |
|------|-----|-------|
| 1.1 / 1.2 | 17 errors (unknown import `GenerationSuccess`/`GenerationFailure`/`GenerationResult`) | 16 entities tests pass |
| 2.1 / 2.2 | 3 errors (`tts_lab.application.agent_card` unresolved) | 6 agent_card tests pass |
| 3.1 / 3.2 / 3.3 | 3 errors (`AudioStorageError` unknown import) | 18 use_cases tests pass |
| 4.1 / 4.2 / 4.3 | test rewrite (response_is_frozen → response_is_removed) | all use_cases tests green |
| 5.1 / 5.2 | RED on Failure branch (`'GenerationFailure' object has no attribute 'audio_path'`) | 9 CLI tests pass |
| 6.1 / 6.2 / 6.3 / 6.4 | n/a (verification) | 183 passed, mypy clean, ruff clean |

## Deviations from tasks.md

1. **`type` statement instead of `TypeAlias`**: tasks.md said `GenerationResult = ... TypeAlias`; ruff `UP040` required `type GenerationResult = ...` (Python 3.12+). Functionally identical; project requires 3.12+.
2. **`__cause__` assignment instead of `from e` in expression context**: tasks.md wrote `return GenerationFailure(AudioStorageError(f"...") from e)`. Python rejects `from` outside `raise` statement. Used `wrapped = AudioStorageError(...); wrapped.__cause__ = e; return GenerationFailure(wrapped)` — semantically equivalent (exception chaining preserved, `failure.error.__cause__ is the original OSError`).
3. **`importlib` for ImportError test**: `pytest.raises(ImportError)` around `from X import Y` did not reliably raise at runtime in this Python 3.14 environment (the import statement is resolved at compile time when the name is missing). Switched to `importlib.import_module(...) + hasattr(...)` which is the canonical runtime symbol-presence check.
4. **CLI `except Exception` retained for INIT-ONLY path**: spec R5 forbids `except Exception` for handling `GenerationFailure` (which is now data). But `create_tts_client(config)` and the context manager CAN raise (model load, Inworld provider guard) — those are initialization failures, not result-envelope failures. Kept a narrow `except Exception` wrapping ONLY the init/CM block, with `except typer.Exit: raise` first to avoid swallowing Typer's own exit signal. The `match result` block sits OUTSIDE the try. This preserves R5's intent (no `except Exception` for GenerationFailure) while keeping graceful init-error UX.

## Traps hit (and resolved)

- **OSError wrapping**: confirmed via test `test_execute_failure_from_save_with_hash_oserror` — `isinstance(response.error, AudioStorageError)`, `isinstance(response.error, TTSError)`, `isinstance(response.error.__cause__, OSError)`, `"disk full" in str(response.error)`.
- **Sanitizer no-leak**: confirmed via `test_failure_card_never_includes_str_error` and CLI `test_generate_failure_prints_error_class_and_exits_1` — noisy body `KEY=sk-live-xxxx noisy body` does NOT appear in stdout.
- **Lockstep deletion**: confirmed via `test_generate_speech_response_is_removed` — `hasattr(dto, "GenerateSpeechResponse") is False`.
- **Status strings**: confirmed `"success"` / `"failure"` (not `"ok"`/`"error"`) in `test_success_card_has_status_and_audio_path` and `test_failure_card_has_status_and_error_class_name`.

## Verification Results (Phase 6)

- `uv run pytest tests/unit/ -q` → **183 passed, 1 skipped** (1 pre-existing slow skip)
- `uv run mypy src/ tests/` → **Success: no issues found in 39 source files**
- `uv run ruff check src/ tests/` → **All checks passed!**
- Coverage on touched files: `agent_card.py` 100%, `use_cases.py` 100%, `entities.py` 100%, `exceptions.py` 100%, `dto.py` 100%, `__init__.py` 100%, `cli.py` 82% (missing lines are model-load paths not unit-testable).

## Scope delta vs design

- Design budget: ~250-280 production lines.
- Actual: ~224 production lines (within budget).
- Tests: ~241 additional lines (not counted against production budget per design "Scope Boundary").
- Deferred items (R6): NOT touched. ✓

## Next recommended

`verify` — run `sdd-verify` against spec + tasks + this apply-progress.
