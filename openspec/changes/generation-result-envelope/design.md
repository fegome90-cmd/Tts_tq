# Design: generation-result-envelope

## Technical Approach

Replace the flat `GenerateSpeechResponse` DTO with a 2-variant discriminated union in the DOMAIN layer: `GenerationResult = GenerationSuccess | GenerationFailure`. `GenerateSpeechUseCase.execute()` becomes the single construction site — it wraps BOTH `TTSClient.generate()` AND `AudioRepository.save_with_hash()` in one try/except (Round 3 trap: disk/IO escapes must be caught too). Clients keep their current contract (`AudioResult` / raise `TTSError`); only the use case catches+wraps. `to_agent_card(result)` in APPLICATION (`agent_card.py`) renders an LLM-safe dict via a whitelist sanitizer. `GenerateSpeechResponse` is deleted; the CLI `generate` migrates from attribute access to `match`.

## Architecture Decisions

| Decision | Choice | Rejected | Rationale (judgment-day why) |
|---|---|---|---|
| Result shape | 2-variant union `Success \| Failure` | Flat envelope (status-string + nullable audio); 3-variant union (+ `GenerationPartial`) | Project rule "invalid states unrepresentable" (mypy-strict). Flat envelopes encode impossible states; 3rd variant invented impoblabable fields. Judges demolished both in Rounds 1-2. |
| Success scalars | Duplicate (`audio_path, warnings, duration_seconds, sample_rate`) | Compose `AudioResult + audio_path` | Bytes are dead weight post-`save_with_hash`; composing couples domain result to client transport type and forces the sanitizer to defensively strip `audio_data` (footgun). Duplicate makes byte-leak structurally impossible. |
| CUT fields | None of: `TruncationInfo`, `retryable`, `correlation_id` | Include for "completeness" | No client computes chars / no retry hints in `TTSError` hierarchy / no tracing consumer. YAGNI per Round 2. |
| `to_agent_card` location | Free function in APPLICATION (`agent_card.py`) | Method on domain entity | Domain stays pure + side-effect-free; sanitization is an application/agent concern. |
| Sanitizer policy | Whitelist `{status, audio_path?, error_class_name?}`; NEVER `str(error)` | Pass-through | Agent cards cannot hold secrets/PII; `str(TTSError)` may carry noisy bodies. Whitelist = fail-closed. |
| `provider` field | DROPPED from result | Carry on result | Already lives on `TTSConfig` (input-side) and `UnsupportedOperationError.provider`. Result is provider-agnostic. |
| try/except scope | Wraps `generate` AND `save_with_hash` catching `(TTSError, OSError)` | Wrap `generate` only; bare `except Exception` | Round 3 trap: `save_with_hash` does disk IO and raises `OSError`, escaping as a non-`TTSError`. Whitelisted tuple catches domain contract errors AND disk/IO WITHOUT a bare `except Exception` that would swallow programming bugs (KeyError/AttributeError). The two branches differ: `TTSError` is pass-through; `OSError` MUST be wrapped into a new domain exception `AudioStorageError(TTSError)` so `GenerationFailure.error: TTSError` holds for BOTH branches (mypy-strict). The card's `error_class_name` reads `"AudioStorageError"` for the storage branch — informative, not leaky. |
| Clone scope | DESCOPEADO (generate-only) | Widen to cover clone | CLI clone bypasses the use case (`cli.py:132-146`); no clone use case today. `CloneVoiceUseCase` = follow-up. |

## Data Flow

```
CLI ──GenerateSpeechRequest──▶ UseCase.execute()
                                  │ try:
                                  │   tts.generate() ──▶ AudioResult(bytes,sr,dur)
                                  │   repo.save_with_hash() ──▶ audio_path
                                  │   return GenerationSuccess(path, (), dur, sr)
                                  │ except TTSError as e:                # pass-through
                                  │   return GenerationFailure(e)        # error: TTSError ✓
                                  │ except OSError as e:                 # disk/IO from save
                                  │   wrapped = AudioStorageError(
                                  │     f"audio storage failed: {e}") from e
                                  │   return GenerationFailure(wrapped)  # error: TTSError ✓
                                  ▼
                         GenerationResult
                                  │
            ┌─────────────────────┴──────────────────────┐
            ▼                                            ▼
   CLI match(Success/Failure)              to_agent_card(result) ──▶ dict
   print path+duration / error_class       {status, audio_path?, error_class_name?}
                                            error_class_name =
                                              "AudioStorageError"  (storage branch)
                                              type(error).__name__ (generate branch)
```

Both branches of the union end with `GenerationFailure.error: TTSError`. The `OSError`-from-`save_with_hash` path is wrapped into `AudioStorageError(TTSError)` before construction — the typed-error promise holds for both branches under mypy-strict, and the `(TTSError, OSError)` tuple still excludes programming bugs (`KeyError`/`AttributeError`).

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/tts_lab/domain/exceptions.py` | Modify | Add `class AudioStorageError(TTSError)` + append to `__all__`. Wraps `save_with_hash` `OSError` so `GenerationFailure.error: TTSError` holds for both branches (mypy-strict). |
| `src/tts_lab/domain/entities.py` | Modify | Add `GenerationSuccess`, `GenerationFailure`, `GenerationResult` (frozen). |
| `src/tts_lab/application/dto.py` | Modify | Delete `GenerateSpeechResponse`. |
| `src/tts_lab/application/__init__.py` | Modify | Remove `GenerateSpeechResponse` from BOTH the import (L3) AND `__all__` (L6); else `from tts_lab.application import GenerateSpeechResponse` breaks at module load. |
| `src/tts_lab/application/use_cases.py` | Modify | `execute() -> GenerationResult`; try/except wraps generate+save_with_hash; `except TTSError` pass-through, `except OSError` wraps into `AudioStorageError(...) from e`. |
| `src/tts_lab/application/agent_card.py` | Create | `to_agent_card(result) -> dict[str,str]` with whitelist sanitizer. |
| `src/tts_lab/cli.py` | Modify | `generate` command: `match result:` on Success/Failure. |
| `tests/unit/test_use_cases.py` | Modify | 6 refs to `GenerateSpeechResponse` across ≥3 functions: REWRITE success-path test (~L30-60); DELETE standalone immutability test (~L301-306, type gone); add 2 failure-path tests (failure-from-generate, failure-from-save_with_hash asserting `isinstance(error, AudioStorageError)`). |
| `tests/unit/test_agent_card.py` | Create | Sanitizer: whitelist only, never `str(error)`. |

## Interfaces / Contracts

```python
# domain/exceptions.py  (NEW subclass added at apply)
class AudioStorageError(TTSError):
    """Disk/IO failure during audio persistence (save_with_hash).
    Wraps OSError so GenerationFailure.error is always a TTSError (mypy-strict)."""
    pass

# domain/entities.py
@dataclass(frozen=True)
class GenerationSuccess:
    audio_path: str
    warnings: tuple[str, ...]
    duration_seconds: float
    sample_rate: int

@dataclass(frozen=True)
class GenerationFailure:
    error: TTSError   # TTSError subclass (generate) OR AudioStorageError (save_with_hash OSError)

GenerationResult = GenerationSuccess | GenerationFailure

# application/agent_card.py
def to_agent_card(result: GenerationResult) -> dict[str, str]: ...
#   Success -> {"status": "success", "audio_path": <path>}
#   Failure -> {"status": "failure", "error_class_name": type(result.error).__name__}
```

The `execute()` body (two-clause `except TTSError` pass-through / `except OSError` → `AudioStorageError(...) from e`) is shown in the Data Flow diagram above.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Success construction + frozen; use-case success path scalars | Mock client+repo, assert `GenerationSuccess` fields |
| Unit | Failure from `generate` (`TTSError`); failure from `save_with_hash` (`OSError`) (Round 3 trap) | Mock raising `TTSError` at generate → assert `isinstance(failure.error, TTSError)` pass-through. Mock raising `OSError` at save_with_hash → assert `isinstance(failure.error, AudioStorageError)` AND `isinstance(failure.error, TTSError)` (typed-error promise holds for both branches) AND `failure.error.__cause__` is the original `OSError`. |
| Unit | Sanitizer whitelist; never `str(error)` | Construct `GenerationFailure` with noisy error, assert card omits message body |

## Migration / Rollout

No migration. In-memory contract change; no persisted data shape changes.

## Scope Boundary (300-line PR)

**IN this PR (~250-280 lines; ~244 total):** envelope types ~35, dto deletion ~12, `__init__` cleanup ~2, execute refactor ~20, `agent_card.py` new ~50, CLI `match` ~15, test rewrites/deletes ~40, `test_agent_card.py` new ~40, sanitizer tests ~30.
**DEFERRED (separate PRs, same change-set family):** (a) Inworld truncation client-signal (needs `TruncatedAudioError` first); (b) Qwen typed-exception subclasses (includes `AudioFormatError` dead-code removal); (c) `CloneVoiceUseCase`; (d) raw-body log removal in `inworld_client._post_safe` (defense-in-depth, DEBUG-gated — `logger.debug` is not default-on and THIS PR's `to_agent_card` sanitizer already hardens the card surface; still land the 1-line deletion first as review-hygiene); (e) MP3 branch removal; (f) `save_with_hash` collision fix (include audio bytes in hash). Items (d)-(f) share the `inworld_client`/`file_storage` seams but NOT the envelope seam — folding them in would force reviewers to reason about provider behavior + storage hashing + domain contracts at once.

## Open Questions

- None blocking. R1 divergence resolved (duplicate scalars). Scope boundary is the riskiest call.
