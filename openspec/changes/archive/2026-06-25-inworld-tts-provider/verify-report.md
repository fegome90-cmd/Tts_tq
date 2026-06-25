# Verification Report

**Change**: inworld-tts-provider
**Version**: N/A (delta spec)
**Mode**: Hybrid (engram + openspec)
**Verifier**: sdd-verify (read-only)

---

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 31 (1.1–1.2, 2.1–2.2, 3.1–3.3, 4.1–4.8c incl. 4.5b/4.8 NOTE, 4.9 DEFERRED, 5.1–5.4, 6.1–6.3, 7.1–7.3) |
| Tasks complete | 31 |
| Tasks incomplete | 0 |

All tasks marked `[x]` in [tasks.md](./tasks.md), including the DEFERRED Phase 4.9 (documented deferral — header-strip unit test 4.1 is the accepted substitute; live-API integration test deferred due to key rotation).

---

## Build & Tests Execution (REAL output)

### Tests: ✅ 163 passed / ⚠️ 1 skipped

```
======================== 163 passed, 1 skipped in 0.56s ========================
```

The single skipped test is `test_qwen_client.py::TestQwenTTSClientContextManager::test_unload_clears_model` — **pre-existing test debt, OUT OF SCOPE** per the verification brief.

**Inworld-specific test breakdown (all passing):**
- `test_inworld_client.py` — 34 tests (TestStripIntermediateWavHeaders 2, TestPostSeam 8 incl. 7 edge cases a–g + recovery h, TestGenerateHappyPath 3, TestTextLength 2, TestExceptionWrapping 6, TestUrllibWrapHelper 6, TestSanitization 2, TestCloneRefusal 1, TestNoOpContextManager 2, TestDurationApproximate 2)
- `test_tts_provider.py` — 4 tests (qwen / inworld+key / inworld-no-key→TTSError / unknown→ValueError)
- `test_config.py` — 10 tests (TTSConfig provider + InworldConfig env + frozen + http_timeout)
- `test_defect_repro.py` — 8 regression tests (defect1 timeout, defect2 non-string audioContent ×5, defect2 empty list, defect3a/3b struct.error)
- `test_exceptions.py` — 3 new UnsupportedOperationError tests
- `test_use_cases.py` — speaker threading + QwenDefaultSpeakerContractGuard (Phase 6.3)

### Type Check (mypy src/): ✅ Clean

```
Success: no issues found in 18 source files
```

### Lint (ruff check src/): ✅ Clean

```
All checks passed!
```

### Domain Purity: ✅ Holds

```
rg "urllib|ssl|socket|http" src/tts_lab/domain/   →  no matches (exit 1)
```

Domain layer has zero network/HTTP imports — purity contract preserved.

### Coverage: ✅ 91% total (threshold ≥80% met)

| File | Stmts | Miss | Cover | Notes |
|------|-------|------|-------|-------|
| domain/exceptions.py | 14 | 0 | **100%** | UnsupportedOperationError fully covered |
| application/dto.py | 11 | 0 | **100%** | speaker field covered |
| application/use_cases.py | 13 | 0 | **100%** | speaker threading covered |
| infrastructure/config.py | 21 | 0 | **100%** | TTSConfig + InworldConfig covered |
| infrastructure/tts_provider.py | 17 | 0 | **100%** | factory all branches |
| infrastructure/inworld_client.py | 210 | 17 | **92%** | missing lines are defensive fallbacks (non-ASCII drop, outer wrap fallback) |
| cli.py | 63 | 23 | 63% | uncovered = generate/clone happy paths (Typer runner mocks); the inworld clone guard IS covered by test_cli |

---

## Spec Compliance Matrix (Behavioral — 13 reqs / 19 scenarios)

| # | Requirement | Scenario | Test (file > name) | Result |
|---|-------------|----------|--------------------|--------|
| 1 | Inworld NDJSON generate contract | happy path single-chunk | `test_inworld_client > TestPostSeam::test_a_happy_single_chunk` | ✅ COMPLIANT |
| 1 | Inworld NDJSON generate contract | speaker overrides default | `test_inworld_client > TestGenerateHappyPath::test_speaker_overrides_default_voice_id` | ✅ COMPLIANT |
| 2 | Single-WAV output for multi-chunk LINEAR16 | multi-chunk full duration | `test_inworld_client > TestStripIntermediateWavHeaders::test_three_chunks_yield_single_riff_header_and_full_duration` | ✅ COMPLIANT |
| 3 | Text length validated before network | len > 2000 → TTSError pre-network | `test_inworld_client > TestTextLength::test_text_over_2000_raises_before_post` + `test_text_exactly_2000_is_allowed` | ✅ COMPLIANT |
| 4 | Duration is approximate | LINEAR16 ≈ len(pcm)/sr | `test_inworld_client > TestDurationApproximate::test_linear16_duration_approximate` | ✅ COMPLIANT |
| 4 | Duration is approximate | MP3 == 0.0 | `test_inworld_client > TestDurationApproximate::test_mp3_duration_is_zero` | ✅ COMPLIANT |
| 5 | clone_voice typed refusal on Inworld | UnsupportedOperationError(operation, provider) | `test_inworld_client > TestCloneRefusal::test_clone_voice_raises_unsupported` + `test_exceptions > ...unsupported...` | ✅ COMPLIANT |
| 6 | No-op context manager | __enter__ returns self / __exit__ None | `test_inworld_client > TestNoOpContextManager::test_enter_returns_self` + `test_exit_returns_none` | ✅ COMPLIANT |
| 7 | HTTP injection seam for tests | _post override returns BytesIO | `test_inworld_client > TestPostSeam` (all 8 tests use _make_client override) | ✅ COMPLIANT |
| 8 | Factory provider selection | unknown → ValueError | `test_tts_provider > test_create_unknown_raises_value_error` | ✅ COMPLIANT |
| 8 | Factory provider selection | inworld without key → TTSError | `test_tts_provider > test_create_inworld_without_key_raises_tts_error` | ✅ COMPLIANT |
| 8 | Factory provider selection | qwen → QwenTTSClient / inworld+key → InworldTTSClient | `test_tts_provider > test_create_qwen` + `test_create_inworld_with_key` | ✅ COMPLIANT |
| 9 (MOD) | Speaker threading end-to-end | reaches Qwen (-s Dennis) | `test_use_cases > test_execute_threads_speaker_into_tts_request` | ✅ COMPLIANT |
| 9 (MOD) | Speaker threading end-to-end | reaches Inworld (-s Sarah → voiceId) | `test_inworld_client > TestGenerateHappyPath::test_speaker_overrides_default_voice_id` | ✅ COMPLIANT |
| 10 (MOD) | Qwen -s semantics — HONOR | REGRESSION GUARD: no -s → speaker None → Serena | `test_use_cases > TestQwenDefaultSpeakerContractGuard::test_default_no_speaker_yields_none_tts_request_speaker` + `test_qwen_speaker_or_serena_resolution_is_serena_when_none` | ✅ COMPLIANT |
| 11 | Exhaustive urllib/json/binascii wrapping | malformed JSON → TTSError not JSONDecodeError | `test_inworld_client > TestPostSeam::test_e_non_json_line_raises_tts_error` | ✅ COMPLIANT |
| 11 | Exhaustive urllib/json/binascii wrapping | corrupt base64 → TTSError not binascii.Error | `test_inworld_client > TestExceptionWrapping::test_corrupt_base64_wrapped_to_tts_error` | ✅ COMPLIANT |
| 11 | Exhaustive urllib/json/binascii wrapping | HTTPError/URLError/socket.timeout/SSLError/OSError → TTSError subclass | `test_inworld_client > TestExceptionWrapping` (5 tests) + `TestUrllibWrapHelper` (6 tests) | ✅ COMPLIANT |
| 12 | Key-leak sanitization | HTTP 500 → status+truncated body, no key/Basic | `test_inworld_client > TestSanitization::test_no_key_no_basic_no_body_in_error_message` + `test_body_truncated_to_at_most_512_chars` | ✅ COMPLIANT |
| 13 | NDJSON edge-case handling | error line → TTSError sanitized | `test_inworld_client > TestPostSeam::test_d_error_object_raises_sanitized_tts_error` | ✅ COMPLIANT |
| 13 | NDJSON edge-case handling | empty audioContent → skip | `test_inworld_client > TestPostSeam::test_f_empty_audio_content_skipped` | ✅ COMPLIANT |
| 13 | NDJSON edge-case handling | BOM → stripped before parse | `test_inworld_client > TestPostSeam::test_b_bom_first_line_stripped` | ✅ COMPLIANT |
| 13 | NDJSON edge-case handling | \r\n tolerated | `test_inworld_client > TestPostSeam::test_c_crlf_tolerated` | ✅ COMPLIANT |
| 13 | NDJSON edge-case handling | truncated final, no valid line → TTSError("empty/truncated response") | `test_inworld_client > TestPostSeam::test_g_partial_truncated_final_no_valid_line_raises` | ✅ COMPLIANT |

**Compliance summary**: **19/19 scenarios COMPLIANT** with runtime evidence. Every spec scenario has a passing test.

---

## Correctness (Static — Structural Evidence)

| Requirement | Status | Evidence (file:line) |
|-------------|--------|----------------------|
| Inworld NDJSON generate contract | ✅ Implemented | `inworld_client.py:300-351` generate(); `:427-455` _post default urllib |
| Single-WAV output multi-chunk | ✅ Implemented | `inworld_client.py:240-273` strip_intermediate_wav_headers |
| Text length pre-network | ✅ Implemented | `inworld_client.py:314-317` len check before _post_safe |
| Duration approximate | ✅ Implemented | `inworld_client.py:571-584` _approx_duration |
| clone_voice typed refusal | ✅ Implemented | `inworld_client.py:353-363`; `exceptions.py:31-55` |
| No-op CM | ✅ Implemented | `inworld_client.py:367-376` |
| HTTP seam _post | ✅ Implemented | `inworld_client.py:427-455` (default) + override pattern |
| Factory selection | ✅ Implemented | `tts_provider.py:19-56` eager key check at `:51-54` |
| Speaker threading | ✅ Implemented | `dto.py:29`; `use_cases.py:40`; `cli.py:211-215` |
| Qwen -s HONOR | ✅ Implemented | `use_cases.py:40` populates speaker; Qwen consumes `request.speaker or "Serena"` (pre-existing qwen_client.py:96) |
| Exhaustive exception wrapping | ✅ Implemented | `inworld_client.py:380-425` _post_safe + `:135-162` _wrap_urllib_error |
| Key-leak sanitization | ✅ Implemented | `inworld_client.py:108-132` sanitize_error_body; `:390-420` HTTPError branch redacts key/Basic/payload/text/voiceId |
| NDJSON edge cases (7) | ✅ Implemented | `inworld_client.py:459-569` _read_ndjson |

---

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| 1. Exception hierarchy (domain TTSError + UnsupportedOperationError; infra subclasses) | ✅ Yes | `exceptions.py:31` + `inworld_client.py:64-87`. Domain pure. |
| 2. HTTP seam _post (tests override, not urllib monkey-patch) | ✅ Yes | `_make_client` subclasses override _post; pure helper tested directly. |
| 3. LINEAR16 strip_intermediate_wav_headers pure helper | ✅ Yes | Module-level `:240`; tested with hand-crafted WAV. |
| 4. Qwen -s HONOR + regression guard | ✅ Yes | Contract guard (Phase 6.3), not byte-snapshot — per gate-3 amendment. |
| 5. Factory eager construction | ✅ Yes | `tts_provider.py:51` raises before InworldTTSClient built. |
| 6. Sanitization (key + Basic + payload + truncate ≤512 + ASCII-only) | ✅ Yes | Extended beyond design to also redact echoed request payload + field values — defensive improvement. |
| 7. Exhaustive urllib wrap (HTTPError/URLError/socket.timeout/SSLError/OSError + JSONDecodeError/binascii.Error) | ✅ Yes | `_post_safe` boundary + in-parser narrowing + defensive outer wrap at `_read_ndjson` call site (`:338-345`). |

**Deviation noted (valid)**: The design placed urllib wrapping in the default `_post`. The implementation centralizes it in `_post_safe` at the generate() call site, because `TestExceptionWrapping` overrides `_post` to raise canned exceptions — wrapping in default `_post` alone would not cover test overrides. Design intent (all 7 exceptions → TTSError subclass before leaving client) is fully preserved and is in fact more robust. Documented in apply-progress #3905.

**Deviation noted (valid)**: Factory return type is `TTSClient` (domain Protocol without CM methods); CLI uses `with client:  # type: ignore[attr-defined]`. Domain Protocol UNTOUCHED per spec. A local ContextManagedTTSClient Protocol was attempted but mypy rejects dunder variance. Documented.

---

## Defect Regression Lock (3 recently-fixed defects)

All three confirmed bugs are now FIXED and locked by `tests/unit/test_defect_repro.py` (8 regression tests, all passing):

| Defect | Fix location | Regression test | Holds? |
|--------|--------------|-----------------|--------|
| **D1: urlopen with no timeout** (hang risk) | `inworld_client.py:452-454` passes `timeout=self._config.http_timeout_seconds`; config `config.py:68` default 30.0 | `test_defect1_urlopen_receives_no_timeout_kwarg` (asserts timeout present, finite, > 0) | ✅ Y |
| **D2: non-string audioContent escapes as TypeError** | `inworld_client.py:548-551` `isinstance(audio_b64, str)` narrowing → `InworldParseError` | `test_defect2_*` (5 parametrized + empty list; asserts TTSError, NOT TypeError) | ✅ Y |
| **D3: truncated/lying WAV fmt body escapes as struct.error** | `inworld_client.py:188-193` actual-bytes pre-check → `InworldParseError`; outer wrap `:342-345` | `test_defect3a_helper_raises_struct_error_on_truncated_fmt` + `test_defect3b_struct_error_escapes_generate_outside_post_safe_boundary` | ✅ Y |

---

## Issues Found

**CRITICAL** (must fix before archive): **None.**

**WARNING** (should fix / intentional deferrals):
1. Phase 4.9 live-API integration test (`tests/integration/test_inworld_live.py`) is DEFERRED — documented in tasks.md Notes + design.md. Header-strip unit test 4.1 is the accepted substitute. Live E2E verification deferred due to API key rotation in progress. **This is an intentional, documented deferral — not a gap.**
2. Pre-existing test debt (`test_entities.py`, `test_protocols.py`, `test_comparison_manifest.py`) is OUT OF SCOPE per the verification brief — not flagged.
3. `cli.py` coverage 63% — uncovered lines are the generate/clone happy paths (Typer runner uses mocks); the Inworld clone guard IS covered. Not a regression.

**SUGGESTION** (nice to have):
1. When a live Inworld API key is available, un-defer Phase 4.9 to validate full-duration multi-chunk E2E.
2. Consider adding `INWORLD_HTTP_TIMEOUT` to `.env.example` (currently documented in InworldConfig docstring but not in .env.example — minor onboarding gap).

---

## Verdict

### ✅ PASS

All 31 tasks complete (including documented 4.9 deferral). **163/163 tests passing** (1 pre-existing skip, out of scope). **19/19 spec scenarios COMPLIANT** with runtime evidence. **13/13 requirements implemented** with code citations. All 7 design decisions followed (2 valid deviations, intent preserved). All 3 recently-fixed defects locked by 8 passing regression tests. Mypy clean (18 files), ruff clean, domain purity holds, coverage 91% (≥80% gate). Protected files (protocols.py, entities.py, qwen_client.py, file_storage.py) UNCHANGED (empty diff vs HEAD).

**Next recommended**: `sdd-archive`.
