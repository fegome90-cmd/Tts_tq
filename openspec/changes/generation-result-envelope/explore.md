# Exploration: generation-result-envelope

> Backfill note — this exploration formalizes the rationale that was produced
> via a 3-round / 6-judge `judgment-day` adversarial review (engram
> observations #3936 and #3941). The design and tasks already exist; this
> document captures the problem framing, alternatives, and codebase findings
> that informed them so the SDD dependency graph is complete.

## Current State

`GenerateSpeechUseCase.execute(request: GenerateSpeechRequest) -> GenerateSpeechResponse`
is the TTS contract today (`src/tts_lab/application/use_cases.py:27`). It is a
two-state contract expressed with a single type:

- **Success** → returns `GenerateSpeechResponse(audio_path, duration_seconds)`
  (`application/dto.py:41`). Note: the use case returns a **path** (from
  `AudioRepository.save_with_hash`), not the `AudioResult` bytes the client
  produced — the response is a thin post-storage projection.
- **Failure** → raises. `execute()` has **no `try/except`**: any
  `TTSError` from `TTSClient.generate` (`qwen_client.py:102`,
  `inworld_client.py` raises typed subclasses) or any `OSError` from
  `FileAudioRepository.save_with_hash` (`file_storage.py:48`, disk/IO escape
  via `_write_audio` → `open(..., "wb")`) propagates straight to the caller.

The CLI consumes this contract in two places (`cli.py`):

- `generate` command (`cli.py:217`) — wraps `execute()` in its own
  `try/except Exception` and renders `response.audio_path` /
  `response.duration_seconds` directly to the terminal.
- `clone` command (`cli.py:124-154`) — **BYPASSES the use case entirely**.
  It instantiates `QwenTTSClient`, calls `client.clone_voice(...)`, then
  `repo.save(...)` directly. There is no `CloneVoiceUseCase`. Any envelope
  placed on `GenerateSpeechUseCase` cannot reach the clone path.

Two structural gaps follow from this:

1. **Agents can't consume failures.** A caller that wants to act on
   "generation failed because the model could not load" vs "the disk was
   full" has no structured handle — it must `try/except` around `execute()`
   and re-parse exception types. There is no card/DTO an LLM agent can read.
2. **No warnings channel.** `InworldTTSClient._read_ndjson`
   (`inworld_client.py:502`) already logs `"NDJSON stream truncated; partial
   audio returned"` at WARNING when it returns partial audio, but the result
   type has nowhere to carry that signal. The success path silently lies.

The `TTSError` hierarchy (`domain/exceptions.py`) is:
`TTSError` ← `VoiceProfileError`, `ModelLoadError`, `AudioFormatError`
(dead — no `raise` site), `UnsupportedOperationError`. **None carries a
retry hint** — no `retryable` attribute anywhere. The Inworld client adds
its own infrastructure-only subclasses `InworldAPIError(status)`,
`InworldConnectionError`, `InworldParseError` (all `TTSError`). The Qwen
client (`qwen_client.py:100-102`, `157-159`) **flattens every exception to
generic `TTSError`**, hollowing the typed-error promise for the Qwen path.

No client in the codebase signals truncation structurally — Inworld's only
truncation signal is the WARNING log line. No code counts "requested chars"
or "synthesized chars"; the `MAX_TEXT_LENGTH` check raises before any
request is sent.

## Affected Areas

- `src/tts_lab/application/use_cases.py` — `execute()` is the single
  construction site for the envelope (catches + wraps both `generate` and
  `save_with_hash` failures). The return type widens from
  `GenerateSpeechResponse` to `GenerationResult`.
- `src/tts_lab/application/dto.py` — `GenerateSpeechResponse` is deleted.
  No replacement DTO lives here: the envelope is a **domain** type.
- `src/tts_lab/application/__init__.py` — the `GenerateSpeechResponse`
  import (L3) and `__all__` entry (L6) MUST be removed in lockstep or the
  package import breaks at module load.
- `src/tts_lab/domain/entities.py` — new types
  `GenerationSuccess` / `GenerationFailure` / `GenerationResult` union.
  Domain stays pure (frozen dataclasses, no external imports).
- `src/tts_lab/domain/exceptions.py` — `GenerationFailure.error: TTSError`
  reuses this hierarchy. No new exception types added in this change.
- `src/tts_lab/cli.py` — `generate` migrates its `try/except Exception` +
  attribute access to a `match result:` over the 2-variant union. `clone`
  is **untouched** (descope — it bypasses the use case; a future
  `CloneVoiceUseCase` would carry its own envelope).
- `src/tts_lab/infrastructure/qwen_client.py` — **no change in this PR**
  (clients keep returning `AudioResult` / raising `TTSError`). The Qwen
  exception-flattening is a tracked follow-up, not part of this envelope.
- `tests/unit/test_use_cases.py` — **6 references to
  `GenerateSpeechResponse`** verified across ≥3 functions: success-path
  test (~L30-60, rewrite), standalone immutability test (~L301-306,
  delete — the type goes away), plus 2 new failure-path tests
  (failure-from-`generate`, failure-from-`save_with_hash`).
- `tests/unit/test_agent_card.py` (new) — covers the APPLICATION-layer
  `to_agent_card(result)` free function + its whitelist sanitizer.

## Approaches

### 1. Flat envelope with `status` + nullable `audio` — REJECTED

A single DTO `GenerationResult(status: Literal["success","failure"],
audio_path: str | None, duration_seconds: float | None, error: TTSError | None)`.

- Pros: One type, one constructor.
- Cons: **Violates the project's own rule** (CLAUDE.md core.md:
  "invalid states unrepresentable" + mypy-strict). The flat shape permits
  `status="success", error=<TTSError>` and `status="failure",
  audio_path="/x.wav"` — both nonsense. Forces every consumer to re-validate
  the cross-field invariant at every use site. The judges demolished this
  in Round 1 for directly contradicting the type-safety bar the rest of the
  codebase upholds.
- Effort: Low — but the cost is paid forever at every call site.

### 2. 3-variant union with `TruncationInfo` / `retryable` / `correlation_id` — REJECTED

`GenerationResult = GenerationSuccess | GenerationPartial | GenerationFailure`
where `GenerationPartial` carries `TruncationInfo(requested_chars,
synthesized_chars)` and `GenerationFailure` carries `retryable: bool` +
`correlation_id: str`.

- Pros: Seemingly "complete" — models partial output, retry semantics, and
  distributed tracing in one shot.
- Cons: **Every added field is impoblabable** (no consumer, no producer):
  - `TruncationInfo` — no client computes `requested_chars` /
    `synthesized_chars`; Inworld's only truncation signal is a WARNING log.
  - `retryable` — the `TTSError` hierarchy has zero retry hints; the field
    would always be `None` / a guess.
  - `correlation_id` — no tracing system is wired in this codebase today.
  - `GenerationPartial` — Inworld-only, dead for Qwen and clone.
  - The original 3-variant pitch also **claimed clone scope that does not
    exist** — the CLI clone path bypasses `GenerateSpeechUseCase`, so any
    envelope on `execute()` cannot reach it.
- Effort: Medium now, negative-value later (YAGNI fields that mislead).

### 3. Minimal "warnings on `AudioResult`" — REJECTED

Leave `execute() -> GenerateSpeechResponse | raise` unchanged; bolt a
`warnings: list[str]` onto `AudioResult` so clients can flag truncation.

- Pros: Smallest possible delta; no new union.
- Cons: **Not a card agents can consume.** Callers still `try/except`
  around `execute()` for failures — the original problem is unaddressed.
  Also pollutes the wrong layer: `AudioResult` is the client output, but
  the use case returns a **path** (post-storage), so the warnings would
  have to survive a translation the response type doesn't perform.
- Effort: Trivial — and worth exactly that.

## Recommendation

**The 2-variant discriminated union (the judgment-day-approved design).**

```python
# domain/entities.py
@dataclass(frozen=True)
class GenerationSuccess:
    audio_path: str
    warnings: tuple[str, ...]
    duration_seconds: float
    sample_rate: int

@dataclass(frozen=True)
class GenerationFailure:
    error: TTSError

GenerationResult = GenerationSuccess | GenerationFailure
```

Construction at `GenerateSpeechUseCase.execute()` — the single site that
sees both `TTSError` (from `generate`) and `OSError` (from `save_with_hash`).
Clients are **untouched**: they keep returning `AudioResult` and raising
`TTSError`. This avoids a flag-day where every adapter changes shape.

Agent consumption is a **free function in the APPLICATION layer**,
`to_agent_card(result: GenerationResult) -> dict[str, Any]`, with a
whitelist sanitizer (expose `error.__class__.__name__` and `audio_path`;
**never** `str(error)` — exception messages echo raw HTTP bodies in the
Inworld path). The card carries the **path**, not bytes — agents don't
need the audio payload.

Key questions answered by the judgment-day review:

| Question | Answer |
|---|---|
| Where does the envelope live? | **Domain** (frozen dataclasses, zero deps). Matches the existing `AudioResult` / `TTSRequest` placement. |
| Where is it constructed? | **`GenerateSpeechUseCase.execute()`** — not in the clients. Clients keep their current `AudioResult`/`TTSError` contract, avoiding a flag-day across both adapters. |
| How is failure carried? | **Typed `TTSError`**, not flattened to a string. Preserves the Inworld subclasses (`InworldAPIError.status` etc.); the Qwen flattening is a tracked follow-up, not this PR. |
| Agent serialization? | **`to_agent_card` free function in APPLICATION**, path (not bytes), whitelist sanitizer. |
| Clone path? | **Descope.** Clone bypasses the use case today; a future `CloneVoiceUseCase` would carry its own envelope. Touching it here would balloon scope without benefit. |
| Truncation? | **Defer.** No client signals it structurally today (only a WARNING log). When a 2nd truncating provider exists AND a client raises `TruncatedAudioError(TTSError)`, the `warnings` tuple on `GenerationSuccess` is the slot — already present, zero churn to add. |

## Tradeoffs + YAGNI Cuts

The judgment-day Round 2 explicitly demolished these as impoblabable
(no producer, no consumer):

- **`TruncationInfo(requested_chars, synthesized_chars)`** — no client
  computes char counts. Cut.
- **`retryable: bool`** — `TTSError` hierarchy has no retry hint. Cut.
- **`correlation_id: str`** — no tracing consumer. Cut.
- **`GenerationPartial` variant** — Inworld-only; dead for Qwen and clone.
  Cut; `warnings: tuple[str, ...]` on `GenerationSuccess` is the lightweight
  slot when truncation becomes a real signal.
- **`provider` field on the result** — `provider` already lives on
  `TTSConfig` / the request; duplicating it on the result has no consumer.
  Cut.

What is kept, and why:

- `warnings: tuple[str, ...]` on `GenerationSuccess` — near-free today,
  already produced by Inworld's parser; the only honest answer to "did we
  return partial audio?".
- `sample_rate` + `duration_seconds` as scalar fields on `GenerationSuccess`
  (duplicate of `AudioResult` scalars, lean — no `audio_data` bytes) —
  chosen over composing `AudioResult` + `audio_path` to avoid drift between
  the client-output shape and the post-storage projection. The design's
  R1 decision.
- `error: TTSError` (the typed exception itself) on `GenerationFailure` —
  preserves `InworldAPIError.status` etc.; a future Qwen-typing follow-up
  upgrades the Qwen path without touching the envelope.

## Deferred / Out of Scope (tracked)

- **`CloneVoiceUseCase`** + `clone_voice` protocol widening — protocol is
  `(profile, text)` vs Qwen's ~10 sampling kwargs. Separate change.
- **Qwen typed-exception subclasses** (includes `AudioFormatError`
  dead-code removal) — `qwen_client.py` currently flattens to generic
  `TTSError`, hollowing the typed-error promise this envelope relies on.
  Follow-up.
- **Inworld truncation default-policy** — needs the client to raise
  `TruncatedAudioError(TTSError)` first; stays a WARNING for now.
- **Raw-body log** — defense-in-depth, DEBUG-gated. The `to_agent_card`
  sanitizer already hardens the agent-facing surface in this PR.

## Risks

- **Test rewrite is mechanical but real.** 6 `GenerateSpeechResponse` refs
  across `tests/unit/test_use_cases.py`; the standalone immutability test
  must be deleted (type gone), the success-path test rewritten, 2 new
  failure-path tests added. Affects ~40 lines.
- **`__init__.py` lockstep.** Deleting `GenerateSpeechResponse` from
  `dto.py` without removing the L3 import + L6 `__all__` entry in
  `application/__init__.py` breaks `from tts_lab.application import
  GenerateSpeechResponse` at module load. Two-line cleanup, easy to miss.
- **Qwen flattening undercuts the typed-error promise.** The envelope
  carries `TTSError`, but the Qwen path loses the original exception class
  inside the generic `TTSError("Failed to generate speech: …")` wrap. The
  card still works (it whitelists `error.__class__.__name__`), but the
  Inworld-vs-Qwen fidelity gap is real until the follow-up lands.
- **Clone path stays un-enveloped.** Anyone consuming clone results still
  gets raw `try/except`. This is explicit in the descope but worth flagging
  to anyone reading the envelope as "the TTS contract" — it is the
  `generate`-path contract.

## Ready for Proposal

**Yes.** The exploration is the judgment-day record; the design and tasks
already encode the recommendation. The next step in the SDD graph is
`sdd-propose` (or, since proposal/spec/design/tasks already exist for
this change, proceed directly to `sdd-apply`).
