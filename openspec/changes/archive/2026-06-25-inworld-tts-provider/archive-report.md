# Archive Report: inworld-tts-provider

**Archived:** 2026-06-25
**Change:** inworld-tts-provider
**Status:** PASS — fully archived

## What Shipped

Added Inworld Cloud TTS as a second provider alongside the local Qwen3-TTS model, selectable at runtime via a `TTS_PROVIDER` env var through a new infrastructure factory seam (`create_tts_client`). The change also fixed a latent dead-code bug by threading `--speaker` end-to-end (CLI → DTO → use case → `TTSRequest.speaker`), reaching both providers, while keeping the domain layer pure and voice cloning Qwen-only.

## Spec Delta Applied

- ADDED: Inworld NDJSON generate contract
- ADDED: Single-WAV output for multi-chunk LINEAR16
- ADDED: Text length validated before network
- ADDED: Duration is approximate
- ADDED: clone_voice typed refusal on Inworld
- ADDED: No-op context manager on InworldTTSClient
- ADDED: HTTP injection seam for tests
- ADDED: Factory provider selection
- ADDED: Exhaustive urllib/json/binascii exception wrapping
- ADDED: Key-leak sanitization in error messages
- ADDED: NDJSON edge-case handling
- MODIFIED (new requirement heading in spec): Speaker threading end-to-end
- MODIFIED (new requirement heading in spec): Qwen `-s` semantics — HONOR
- REMOVED: none

> Merge note: the delta labeled 2 requirements as "MODIFIED" because they modify prior *CLI/runtime behavior*, but neither heading existed in the main spec previously — both were appended as new requirement headings. No main-spec requirement was overwritten or deleted. Final main spec: 17 requirements (4 original + 13 added), zero duplicates, zero conflicts.

## Verification

- **Verdict:** PASS
- **Requirements:** 13/13 implemented
- **Scenarios:** 19/19 compliant
- **Tests:** 163 passed, 1 skipped (pre-existing, out of scope)
- **Coverage:** 91% (gate ≥80%)
- **mypy:** clean (18 source files, no issues)
- **ruff:** clean
- **Domain purity:** HOLDS (no urllib/ssl/socket/http in domain/)

## Defects Fixed (3 — regression-locked by tests/unit/test_defect_repro.py)

- D1: urlopen-no-timeout — FIXED at inworld_client.py:452-454 (timeout=config.http_timeout_seconds; config.py:68 default 30.0). Test: test_defect1_urlopen_receives_no_timeout_kwarg.
- D2: non-string audioContent → TypeError escape — FIXED at inworld_client.py:548-551 (isinstance str narrowing → InworldParseError). Tests: test_defect2_* (5 parametrized + empty list).
- D3: truncated/lying WAV fmt → struct.error escape — FIXED at inworld_client.py:188-193 (actual-bytes pre-check) + outer wrap :342-345. Tests: test_defect3a/3b.

## Known Deferrals

- Phase 4.9 @slow (live-API integration test) — DEFERRED, intentional (key rotation in progress). Header-strip unit test 4.1 is accepted substitute. NOT a gap.
- Pre-existing test debt (test_unload_clears_model skip) — OUT OF SCOPE.

## Design Deviations (2 — valid, intent preserved)

1. urllib wrapping lives in _post_safe at generate() call site (not in default _post) — because TestExceptionWrapping overrides _post to RAISE. Design intent (all 7 exceptions → TTSError subclass) fully preserved.
2. Factory returns TTSClient (domain Protocol, no CM methods); CLI uses `with client:  # type: ignore[attr-defined]`. Domain Protocol UNTOUCHED. A local ContextManagedTTSClient Protocol was attempted but mypy rejects dunder variance.

## Traceability (Engram observation IDs)

- proposal: 3885
- spec: 3898
- design: 3897
- tasks: 3901
- verify-report: 3927

## Source of Truth

- Main spec updated: openspec/specs/qwen-tts/spec.md
