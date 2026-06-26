# Proposal: generation-result-envelope

## Intent

`GenerateSpeechUseCase.execute()` returns `GenerateSpeechResponse` on success or **raises** on failure — there is no try/except (verified: `use_cases.py:27`). The contract cannot represent failure as data, so LLM agents consuming TTS have no structured handle (they must re-parse exception types), and the result silently lies about partial output. We want a domain `GenerationResult` union that makes success/failure **unrepresentable as the wrong thing** under mypy-strict, and an agent-consumable `to_agent_card` projection.

## Scope

### In Scope (~250-280 line PR)
- Envelope types in `domain/entities.py`: `GenerationSuccess | GenerationFailure` (frozen).
- `execute() -> GenerationResult` — single construction site; `except (TTSError, OSError)` wraps BOTH `generate` AND `save_with_hash` (disk/IO escape).
- `application/agent_card.py` (new): `to_agent_card(result)` with whitelist sanitizer (expose `audio_path` + `error_class_name`; NEVER `str(error)`).
- Delete `GenerateSpeechResponse` from `dto.py` AND `application/__init__.py` (L3 import + L6 `__all__` lockstep — else module-load breaks).
- CLI `generate` migrates `try/except Exception` + attribute access → `match result:` over the union.
- Tests: rewrite success-path, delete immutability-of-deleted-type test, add 2 failure-path tests; new `test_agent_card.py`.

### Out of Scope / Deferred (with justification)
- **Inworld truncation client-signal** — no client raises `TruncatedAudioError(TTSError)` today; `warnings` tuple is the ready slot when one does.
- **Qwen typed-exception subclasses** (incl. `AudioFormatError` dead-code) — Qwen flattens to generic `TTSError`; separate seam, tracked follow-up.
- **`CloneVoiceUseCase`** + protocol widening — CLI clone bypasses `execute()` (`cli.py:124-154`); envelope cannot reach it.
- **Raw-body DEBUG log removal** — defense-in-depth; `to_agent_card` sanitizer already hardens the agent surface this PR.
- **MP3 removal; `save_with_hash` collision fix** — share infra seams, not the envelope seam; folding in conflates reviewer concerns.

## Approach

The judgment-day-approved **2-variant discriminated union** (Round 1 rejected flat envelope for violating "invalid states unrepresentable"; Round 2 cut `TruncationInfo`/`retryable`/`correlation_id`/`GenerationPartial` as impoblabable). Success scalars **duplicate** `AudioResult` fields (lean, no bytes) rather than compose `AudioResult + audio_path` — bytes are dead weight post-save and composition forces the sanitizer to defensively strip `audio_data` (R1 resolution). Construction at `execute()`; clients unchanged (no flag-day).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `domain/entities.py` | New | `GenerationSuccess`, `GenerationFailure`, `GenerationResult` union |
| `application/use_cases.py` | Modified | `execute() -> GenerationResult`; try/except wraps generate+save |
| `application/agent_card.py` | New | `to_agent_card` free function + whitelist sanitizer |
| `application/dto.py` | Removed | `GenerateSpeechResponse` deleted |
| `application/__init__.py` | Modified | Lockstep removal of import + `__all__` entry |
| `cli.py` | Modified | `generate`: `match result:` on Success/Failure |
| `tests/unit/test_use_cases.py` | Modified | Rewrite success, delete immutability test, +2 failure tests |
| `tests/unit/test_agent_card.py` | New | Sanitizer whitelist, never `str(error)` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `__init__.py` lockstep break (module-load) | Med | Two-line cleanup in same PR; gate-review caught this (HIGH) |
| Qwen exception-flattening hollows typed-error promise | Med | Tracked follow-up; card still works (whitelists class name) |
| Clone-descope asymmetry (envelope = generate-only) | Low | Explicit descope; `CloneVoiceUseCase` follow-up |
| Test rewrite mechanical but real (~40 lines, 6 refs) | Low | Covered in tasks; TDD per file |

## Rollback Plan

Clean `git revert`. This is an in-memory contract change — no persisted state, no migrations, no on-disk schema. Clients keep their `AudioResult`/`TTSError` contract throughout, so revert restores the flat DTO without adapter churn.

## Dependencies

- None external. Pure internal refactor of the generate-path contract.

## Success Criteria

- [ ] `execute()` returns `GenerationResult`; no bare `raise` escapes `(TTSError, OSError)`
- [ ] `to_agent_card` never emits `str(error)`; whitelist only
- [ ] mypy-strict passes (invalid success/failure states unrepresentable)
- [ ] CLI `generate` uses `match`; `clone` untouched
- [ ] `from tts_lab.application import GenerateSpeechResponse` raises `ImportError`
- [ ] Unit tests cover success, failure-from-generate, failure-from-save, sanitizer
