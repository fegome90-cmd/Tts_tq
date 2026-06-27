# Tasks: generation-result-envelope

TDD order per task: RED (failing test first) → GREEN (minimal impl) → REFACTOR. Scope budget ~250-280 lines PR. Design = `design.md` (GATE-FIXED); rationale in engram obs 3936.

## Phase 1: Domain envelope (foundation — depended on by agent_card, use case, CLI)

- [x] 1.1 RED — `tests/unit/test_entities.py` (new or extend): `test_generation_success_construction` (audio_path, warnings=(), duration_seconds, sample_rate scalars correct); `test_generation_success_is_frozen` (setattr → FrozenInstanceError); `test_generation_failure_construction` (wraps a `TTSError`); `test_generation_failure_is_frozen`; `test_generation_failure_has_no_audio_path` (invalid-state-unrepresentable: `hasattr(failure, "audio_path") is False` — guard against accidental flat-envelope drift); `test_generation_result_union_accepts_both_variants` (TypeAlias importable + isinstance both). Satisfies design "Result shape" row + "invalid states unrepresentable" rule.
- [x] 1.2 GREEN — `src/tts_lab/domain/entities.py`: add `from tts_lab.domain.exceptions import TTSError`; add `@dataclass(frozen=True) class GenerationSuccess: audio_path: str; warnings: tuple[str, ...]; duration_seconds: float; sample_rate: int`; add `@dataclass(frozen=True) class GenerationFailure: error: TTSError`; add `GenerationResult = GenerationSuccess | GenerationFailure` TypeAlias; update `__all__` → `["AudioResult", "GenerationFailure", "GenerationResult", "GenerationSuccess", "TTSRequest", "VoiceProfile"]`. Satisfies design Interfaces/Contracts block.

## Phase 2: Agent card sanitizer (APPLICATION — depends on Phase 1)

- [x] 2.1 RED — `tests/unit/test_agent_card.py` (new): `test_success_card_has_status_and_audio_path` (`{"status": "success", "audio_path": "/x.wav"}`); `test_success_card_has_no_duration_no_warnings_no_sample_rate` (whitelist enforces — extras stripped); `test_failure_card_has_status_and_error_class_name` (`{"status": "failure", "error_class_name": "ModelLoadError"}`); `test_failure_card_never_includes_str_error` (build `GenerationFailure(ModelLoadError("KEY=sk-live-xxxx noisy body"))` → assert card has NO key/body/text; `error_class_name == "ModelLoadError"`); `test_failure_card_omits_audio_path_key_entirely` (key absent, not None); `test_card_is_dict_of_str_to_str` (values all `str`). Status strings MUST match spec R3 exactly: `"success"` / `"failure"` (NOT `"ok"` / `"error"` — gate-fix HIGH: status drift). Satisfies spec R3 lines 55/60/67 + design "Sanitizer policy" + "to_agent_card location" rows.
- [x] 2.2 GREEN — `src/tts_lab/application/agent_card.py` (new): `def to_agent_card(result: GenerationResult) -> dict[str, str]`; match on variant — Success → `{"status": "success", "audio_path": result.audio_path}`; Failure → `{"status": "failure", "error_class_name": type(result.error).__name__}`; whitelist only those keys; NEVER call `str(result.error)`. Status strings MUST match spec R3: `"success"` / `"failure"` (NOT `"ok"` / `"error"`). Import `GenerationResult, GenerationSuccess, GenerationFailure` from domain. Satisfies spec R3 + design Interfaces/Contracts `to_agent_card` block.

## Phase 3: Use case refactor (core — depends on Phase 1)

- [x] 3.1 RED — `tests/unit/test_use_cases.py`: REWRITE `test_execute_returns_response` (~L31-59) → `test_execute_returns_generation_success` asserting `isinstance(response, GenerationSuccess)` AND scalars correct (`audio_path == "/output/speech_abc123.wav"`, `warnings == ()`, `duration_seconds == 2.5`, `sample_rate == 24000`); ADD `test_execute_failure_from_generate` (mock `generate` raises `ModelLoadError("boom")` → `isinstance(response, GenerationFailure)` AND `isinstance(response.error, ModelLoadError)` AND `isinstance(response.error, TTSError)`); ADD `test_execute_failure_from_save_with_hash_oserror` (mock `save_with_hash` raises `OSError("disk full")` → `isinstance(response, GenerationFailure)` AND `isinstance(response.error, AudioStorageError)` AND `isinstance(response.error, TTSError)` — typed-error promise holds; AND `isinstance(response.error.__cause__, OSError)` — original cause preserved via `from e`). Round 3 trap: disk/IO must be caught by `(TTSError, OSError)` tuple and wrapped into `AudioStorageError(TTSError)`, NOT escape, NOT enter as bare OSError (mypy-strict: error: TTSError must hold for both branches). Satisfies spec R2 (incl. AudioStorageError clause + scenario) + design "try/except scope" row + Testing Strategy failure row.
- [x] 3.2 GREEN — `src/tts_lab/domain/exceptions.py`: add `class AudioStorageError(TTSError): """Disk/IO failure during audio persistence (save_with_hash).""" pass` and append `"AudioStorageError"` to `__all__` (alphabetical). This is a sub-step of the use-case GREEN — the exception is the typed-error adapter for the OSError branch.
- [x] 3.3 GREEN — `src/tts_lab/application/use_cases.py`: change import to `from tts_lab.application.dto import GenerateSpeechRequest` (drop `GenerateSpeechResponse`); import `GenerationFailure, GenerationResult, GenerationSuccess` + `from tts_lab.domain.exceptions import AudioStorageError, TTSError`; rewrite `execute(self, request) -> GenerationResult`; wrap BOTH `self._tts.generate(...)` AND `self._repo.save_with_hash(...)` in one try block with TWO except clauses: `except TTSError as e: return GenerationFailure(e)` (pass-through) and `except OSError as e: return GenerationFailure(AudioStorageError(f"audio storage failed: {e}") from e)` (wrap into TTSError subclass); build `GenerationSuccess(audio_path=path, warnings=(), duration_seconds=audio.duration_seconds, sample_rate=audio.sample_rate)` from `AudioResult` post-save. NO `except Exception`. Satisfies spec R2 + design Data Flow diagram + Interfaces/Contracts block.

## Phase 4: Delete GenerateSpeechResponse (cleanup — depends on Phase 3 RED)

- [x] 4.1 RED — `tests/unit/test_use_cases.py`: DELETE `test_generate_speech_response_is_frozen` (~L300-308) — type no longer exists; assert import of `GenerateSpeechResponse` raises `ImportError` via a guard test `test_generate_speech_response_is_removed` (`with pytest.raises(ImportError): from tts_lab.application.dto import GenerateSpeechResponse`). Confirm no remaining test references `GenerateSpeechResponse`.
- [x] 4.2 GREEN — `src/tts_lab/application/dto.py`: delete `class GenerateSpeechResponse` (~L40-50); update `__all__` → `["GenerateSpeechRequest", "Language"]`.
- [x] 4.3 GREEN — `src/tts_lab/application/__init__.py`: edit L3 import → `from tts_lab.application.dto import GenerateSpeechRequest`; edit L6 `__all__` → `["GenerateSpeechRequest", "GenerateSpeechUseCase"]`. (Gate-fix HIGH: WITHOUT this two-line cleanup `from tts_lab.application import GenerateSpeechResponse` breaks at module load.)

## Phase 5: CLI migration (integration — depends on Phase 1, Phase 3)

- [x] 5.1 RED — `tests/unit/test_cli.py` (new or extend): `test_generate_success_prints_path_and_duration` (CliRunner, mocked use case via monkeypatch of `GenerateSpeechUseCase` returning `GenerationSuccess` → stdout contains path + "Duration:"); `test_generate_failure_prints_error_class_and_exits_1` (mock returns `GenerationFailure(ModelLoadError("noisy body"))` → stdout contains `ModelLoadError`, exit_code == 1, stdout does NOT contain "noisy body"). RED requires `match` on GenerationResult variant to exist in cli.py (import fails until 5.2).
- [x] 5.2 GREEN — `src/tts_lab/cli.py`: import `GenerationFailure, GenerationSuccess` from domain; in `generate_speech` replace `response = use_case.execute(request)` block (L217-221) + outer `except Exception` (L223-225) with `result = use_case.execute(request)` then `match result:` — `case GenerationSuccess(): console.print(path); console.print(duration)` / `case GenerationFailure(): console.print(f"[red]✗ Error:[/red] {type(result.error).__name__}"); raise typer.Exit(code=1) from None`. Drop the bare `except Exception` (use case no longer raises; it returns Failure). Satisfies design File Changes cli.py row.

## Phase 6: Verification (no new impl — green checks)

- [x] 6.1 `uv run pytest tests/unit/ -q` — all green (incl. new test_entities, test_agent_card, rewritten test_use_cases, test_cli).
- [x] 6.2 `uv run mypy src/ tests/` — clean (mypy-strict: `GenerationResult` union narrows via `match`).
- [x] 6.3 `uv run ruff check src/ tests/` — clean.
- [x] 6.4 Traceability: every design File Changes row (7) + Architecture Decision (8) maps to ≥1 task above. Y.

## Deferred — OUT OF SCOPE (documented, do NOT implement this PR)

Per design "Scope Boundary" + engram obs 3936 deferred list. Separate PRs in the same change-set family:

- (a) Inworld truncation client-signal (`TruncatedAudioError(TTSError)` + warning upgrade).
- (b) Qwen typed-exception subclasses (incl. `AudioFormatError` dead-code removal in exceptions.py:25-28).
- (c) `CloneVoiceUseCase` (+ `clone_voice` protocol widening — CLI clone bypasses use case today, cli.py:125-146).
- (d) Raw-body log removal in `inworld_client._post_safe` (defense-in-depth, DEBUG-gated; `to_agent_card` sanitizer already hardens the card surface — land the 1-line deletion first as review-hygiene in its own PR).
- (e) MP3 branch removal (inworld_client encoding paths).
- (f) `save_with_hash` collision fix (include audio bytes in hash — file_storage seam, NOT envelope seam).

## Notes

- Domain `protocols.py`, `qwen_client.py`, `file_storage.py` UNCHANGED this PR.
- `provider` field DROPPED from result (lives on `TTSConfig` input-side + `UnsupportedOperationError.provider`) — design "provider field" row.
- Clients keep their current contract (`AudioResult` / raise `TTSError`); only the use case catches+wraps — design Technical Approach.
