# Chained PR Plan: generation-result-envelope

**Strategy**: Stacked PRs to main (conventional two-PR stack, no tracker)
**Date**: 2026-06-26
**Status**: PLANNED — awaiting user approval before git execution

## Rationale

The change totals 467 changed lines (prod ~254 + tests ~319), exceeding the
session review budget of 300 lines. Per `ask-on-risk` strategy and the
`chained-pr` skill (split PRs over 400 lines), the change is split into two
stacked PRs that each land on main in dependency order.

## Strategy Choice: Conventional Stack (no tracker)

A tracker / feature-branch integration layer is unnecessary here because:

- PR 1 is internally coherent: it adds types + sanitizer + their tests. The
  new types are NOT code-zombie — `agent_card.to_agent_card()` consumes
  `GenerationResult` within PR 1 itself.
- The operational test for landing PR 1 alone is: does it compile, pass
  tests, and form a coherent unit? Yes.
- A tracker only adds value when no subset can land on main, when multiple
  teams integrate in parallel, or when a single atomic final merge is
  required. None apply here (2 PRs, ~467 lines, single author).

A stacked PR (`PR 2 → branch-pr1`) already shows the incremental diff
correctly in GitHub — reviewers of PR 2 see only the migration slice, not
the accumulated 467 lines.

## Split Criteria

The cut preserves **green build at every intermediate state**. PR 1 is
purely additive (introduces new types + sanitizer without removing or
migrating anything); PR 2 performs the migration (rewires consumers +
deletes the old DTO in lockstep).

## PR Breakdown

### PR 1 — Envelope types + sanitizer (additive)

**Branch**: `generation-result-domain`
**Base**: `main`
**Depends on**: None
**Follow-up**: PR 2

**Files**:

| File | Change | Lines |
|------|--------|-------|
| `src/tts_lab/domain/entities.py` | Add `GenerationSuccess`, `GenerationFailure`, `type GenerationResult` (the `-1` is the old `__all__` being replaced by a superset) | +54/-1 |
| `src/tts_lab/domain/exceptions.py` | Add `AudioStorageError(TTSError)` | +12/0 |
| `src/tts_lab/application/agent_card.py` | NEW: `to_agent_card` whitelist sanitizer | +50 (new) |
| `tests/unit/test_entities.py` | Add 3 test classes for the new types | +101/0 |
| `tests/unit/test_agent_card.py` | NEW: 6 sanitizer tests | +81 (new) |

**Total**: **+298/-1 = 299 lines** ✓ (within 300-line budget)

**Deliverable**: The domain has a 2-variant `GenerationResult` union and an
LLM-safe `to_agent_card` projection. `to_agent_card` is the consumer that
exercises the new types — they are not dead code. The old
`GenerateSpeechResponse` still exists and the old code paths still work.

**Restriction**: this PR MUST NOT contain any partial hunk of
`tests/unit/test_use_cases.py`. That file lands atomically in PR 2 (see
Restriction below).

---

### PR 2 — Migrate use case + CLI to envelope (consumers)

**Branch**: `generation-result-application`
**Base**: `generation-result-domain` (stacked on PR 1)
**Depends on**: PR 1
**Follow-up**: None (chain complete)

**Files**:

| File | Change | Lines |
|------|--------|-------|
| `src/tts_lab/application/use_cases.py` | `execute() -> GenerationResult`; try/except wraps generate+save | +32/-12 |
| `src/tts_lab/application/dto.py` | Delete `GenerateSpeechResponse` | +1/-14 |
| `src/tts_lab/application/__init__.py` | Lockstep removal of import + `__all__` | +2/-2 |
| `src/tts_lab/cli.py` | `generate` uses `match result`; `execute()` outside try (judgment-day fix) | +63/-25 |
| `tests/unit/test_use_cases.py` | Rewrite success test + 2 failure-path tests + `is_removed` test (ATOMIC — see Restriction) | +62/-23 |
| `tests/unit/test_cli.py` | Add `TestGenerateCommandResultEnvelope` (success + failure branches) | +63/0 |
| `openspec/changes/generation-result-envelope/*.md` | SDD artifacts (proposal, spec, design, tasks, apply-progress, verify-report, this plan) | docs only |

**Total**: **+223/-76 = 299 lines** (code) + SDD docs

**Deliverable**: `GenerateSpeechResponse` is gone. `execute()` returns
`GenerationResult`. The CLI consumes it via `match`. Failure is data, not
raised. The old DTO cannot be imported (`ImportError`).

### ⚠️ Restriction: `test_use_cases.py` atomicity

`tests/unit/test_use_cases.py` MUST be committed atomically in PR 2. It
contains:

- `test_execute_returns_generation_success` — imports `GenerationSuccess`
  and asserts `use_case.execute()` returns it (requires migrated use case).
- `test_execute_failure_from_generate` / `test_execute_failure_from_save_with_hash_oserror`
  — require the migrated control flow.
- `test_generate_speech_response_is_removed` — requires the DTO deletion.

Committing any subset of these without the corresponding production change
(use case migration + DTO deletion) leaves the branch red. No partial
hunks of this file in either PR.

## Chain Overview

```text
main
 └── generation-result-domain          ← PR 1 → main
      └── generation-result-application ← PR 2 → generation-result-domain
                                         📍
```

After PR 1 merges to main: rebase `generation-result-application` onto the
new main, retarget PR 2 to `main`, re-run CI, confirm the PR 2 diff still
contains only the migration slice, then merge PR 2.

## Dependency Note

PR 2 imports `GenerationSuccess`, `GenerationFailure`, `GenerationResult`
from `domain/entities` and `AudioStorageError` from `domain/exceptions` —
all introduced by PR 1. If PR 1 is rejected or substantially changed, PR 2
must be reworked. This is the only cross-PR dependency.

## Out of Scope (Deferred — R6)

These items from the change's R6 are NOT in either PR and remain deferred to
future change-set family members:

- (a) Inworld truncation client-signal (`TruncatedAudioError`)
- (b) Qwen typed-exception subclasses (incl. `AudioFormatError` dead-code)
- (c) `CloneVoiceUseCase` (+ protocol widening)
- (d) Raw-body log removal in `inworld_client._post_safe`
- (e) MP3 branch removal
- (f) `save_with_hash` collision fix

## Files Excluded from Both PRs

These modified files in the working tree are NOT part of this change and
must NOT be committed to either PR branch:

- `README.md` (pre-existing bitácora update)
- `autoresearch.jsonl` (autoresearch log)
- `openspec/config.yaml` (created by sdd-init; separate concern)

## Verification Plan Per PR

### PR 1 verification

- `uv run pytest tests/unit/test_entities.py tests/unit/test_agent_card.py -q` → green
- `uv run pytest tests/unit/ -q` → full suite green (old code paths intact; new types additive)
- `uv run mypy src/ tests/` → clean
- `uv run ruff check src/ tests/` → clean
- Manual: `uv run python -c "from tts_lab.application.dto import GenerateSpeechResponse"` → succeeds (old DTO still present in PR 1)

### PR 2 verification

- `uv run pytest tests/unit/ -q --cov=src` → 183 passed, coverage on touched files 100%
- `uv run mypy src/ tests/` → clean
- `uv run ruff check src/ tests/` → clean
- Manual: `uv run python -c "from tts_lab.application.dto import GenerateSpeechResponse"` → ImportError

## Rollback Scope

- **PR 1 rollback**: revert single PR. Old code unaffected (PR 1 was additive).
- **PR 2 rollback**: revert single PR. Returns to PR 1 state (types + sanitizer present; old DTO restored).

## Commit Messages (final, post-judgment)

No `!` / `BREAKING CHANGE` footer: `GenerateSpeechResponse` has no external
consumers (verified: only references are the deletion-test and its own
definition). `tts-lab` is at `version = "0.1.0"`, internal app, exports not
treated as stable public API. The change is internal refactor.

```
PR 1: feat(domain): add generation result envelope and agent-card sanitization

PR 2: refactor(application): migrate generation flow to GenerationResult
```

Optional body for PR 2:

```
GenerateSpeechUseCase.execute now returns GenerationResult (Success | Failure)
instead of GenerateSpeechResponse. Failure is data, not raised. The CLI
consumes it via match. GenerateSpeechResponse is removed in lockstep from
dto.py and application/__init__.py.
```

## Execution Steps (after user approval)

1. Preflight: `gh auth status` (confirm GitHub CLI authenticated).
2. Create branch `generation-result-domain` from `main`.
3. Stage ONLY PR 1 files (explicit paths — never `git add -A`).
4. Commit PR 1.
5. Push `generation-result-domain`; open PR 1 → `main` with Chain Context body.
6. Create branch `generation-result-application` from `generation-result-domain`.
7. Stage ONLY PR 2 files (explicit paths, including `openspec/changes/generation-result-envelope/*.md`).
8. Commit PR 2.
9. Push `generation-result-application`; open PR 2 → `generation-result-domain` with Chain Context body.

## Open Question for User

**Execution scope**: after `gh auth status` preflight, do you want me to:

- (a) push + `gh pr create` both PRs, OR
- (b) create local branches + commits only, stop before push for your review?

(Commit messages, SDD artifacts in PR 2, atomicity restriction, and
conventional-stack strategy are settled — no further questions on those.)
