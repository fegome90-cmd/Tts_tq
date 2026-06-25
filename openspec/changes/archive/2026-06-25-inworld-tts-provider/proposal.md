# Proposal: Add Inworld Cloud TTS as a Second Provider

## Problem

TTS Lab has a single TTS provider today: the local Qwen3-TTS model. Provider selection is **direct instantiation** — `cli.py` constructs `QwenTTSClient(model_path=..., device=...)` inline (`cli.py:101`, `:174`). There is no factory, registry, or strategy, so adding a second provider (the cloud Inworld TTS API) has no seam to plug into without editing CLI commands per provider.

We want Inworld as an alternative cloud provider for preset-voice synthesis (voice IDs like `Sarah`, `Dennis`), selectable at runtime without code changes. The domain must stay pure, the existing buffered `AudioResult` contract must be preserved, and voice cloning (reference-audio) must keep working on Qwen only.

The pre-implementation gate also exposed a **latent repo bug**: the `--speaker` CLI flag (`cli.py:145`) is dead code — it is accepted but never threaded into `GenerateSpeechRequest` (no `speaker` field, `dto.py:13-24`) or `GenerateSpeechUseCase.execute` (`use_cases.py:37-40` builds `TTSRequest` without `speaker`), so `request.speaker` is **always `None`**. Inworld's per-request voice selection (`voice_id = request.speaker or default`) would silently fall back to the default. This change fixes the bug at the root.

## Goals

- Add an `InworldTTSClient` infrastructure adapter implementing `TTSClient.generate` via the Inworld `/tts/v1/voice:stream` NDJSON API.
- Introduce a single selection seam — a factory `create_tts_client(settings, ...)` in infrastructure — so the CLI no longer hardwires the provider.
- Make the provider configurable via a `TTS_PROVIDER` env var (`qwen` | `inworld`, default `qwen`), owned by `config.py` and consumed by the factory.
- **Make per-request voice selection actually work** — thread `speaker` end-to-end: `GenerateSpeechRequest.speaker` → `TTSRequest.speaker` (field already exists at `entities.py:23`) → `InworldTTSClient`. This also fixes the latent Qwen dead-code bug.
- Preserve `GenerateSpeechUseCase` constructor DI (signature unchanged; only `execute` populates the new field).
- Keep the Qwen voice-cloning path (`clone` command) fully functional and Qwen-only.
- Fail loudly and typed when an unsupported operation is requested on Inworld (`clone_voice`), never silently no-op.

## Scope

### In Scope (v1)

- New `src/tts_lab/infrastructure/inworld_client.py` — `InworldTTSClient` implementing `TTSClient.generate`; `clone_voice` raises `UnsupportedOperationError`.
- New `src/tts_lab/domain/exceptions.py` exception `UnsupportedOperationError(TTSError)`.
- New `src/tts_lab/infrastructure/config.py` `InworldConfig` frozen dataclass (`from_env()`); **also add `provider` field to `TTSConfig`** (read from `TTS_PROVIDER`, default `qwen`), consistent with the existing `TTSConfig.from_env()` pattern.
- New `src/tts_lab/infrastructure/tts_provider.py` factory `create_tts_client(settings, ...)` returning a `TTSClient` based on `settings.provider`.
- **Modify `application/dto.py`** — add `speaker: str | None = None` to `GenerateSpeechRequest`.
- **Modify `application/use_cases.py`** — `GenerateSpeechUseCase.execute` populates `TTSRequest(speaker=request.speaker)`.
- Modify `cli.py` `generate`: (a) PURE drop-in swap to the factory (no config-construction refactor); (b) pass `speaker` into the DTO.
- Modify `cli.py` `clone`: add a provider guard — when `TTS_PROVIDER=inworld`, print a clear notice or refuse with a typed error (do NOT silently fall back to Qwen and fail with a confusing model-load error).
- Unit tests `tests/unit/test_inworld_client.py` mirroring `test_qwen_client.py` Mock style; tests for the factory, `UnsupportedOperationError`, and the speaker-threading path.
- No new DIRECT runtime dependencies — use stdlib `urllib.request`. (`httpx`/`requests` are transitive via `openai-whisper` but unused by this change.)

### Out of Scope

- Approach 2 protocol split (`SpeechSynthesizer` + `VoiceCloner`) — deferred; bigger refactor.
- Async streaming playback / new `AudioStream` entity (Approach 3) — deferred; `AudioResult` is buffered.
- `httpx` / `aiohttp` adoption — only if streaming playback is added later.
- Voice cloning via Inworld — Inworld v1 has no reference-audio clone path; `clone` stays Qwen-only.
- Generalizing the `clone` command's Qwen-specific kwargs (`x_vector_only_mode`, `seed`, etc.).
- Extending `FileAudioRepository` to honor non-WAV formats (only needed if MP3 becomes default; it is not).
- **Retry/backoff** — v1 is a one-shot POST; explicit non-goal, document as such.

## Approach

Approach 1 from exploration: **minimal strategy at the edge**.

`InworldTTSClient.generate(request)`:
1. Validate `len(request.text) <= 2000` (Inworld hard limit) — raise `TTSError` if exceeded.
2. Resolve `voice_id = request.speaker or inworld_config.default_voice_id`.
3. POST to `{base_url}/tts/v1/voice:stream` with `Authorization: Basic {api_key}`, body `{text, voiceId, modelId, audioConfig:{audioEncoding, sampleRateHertz}}`, via a `_post(payload)` method (the HTTP injection seam — tests override this; do NOT rely solely on `patch("urllib.request.urlopen")`).
4. Read the NDJSON response to completion (see "NDJSON line handling" below): split lines → `json.loads` each → if line has `error`, raise `TTSError`; else base64-decode `result.audioContent` and accumulate.
5. Return one `AudioResult(audio_data=<concatenated>, sample_rate=sampleRateHertz, duration_seconds=<see Decision 1>)`.

`clone_voice` raises `UnsupportedOperationError(message, operation="clone_voice", provider="inworld")`.

**Context-manager seam:** `InworldTTSClient` implements trivial no-op `__enter__`/`__exit__` (returns `self`) so the existing `with create_tts_client(...) as client:` in `cli.py:174` works unchanged. The `TTSClient` domain protocol is NOT extended (keep domain untouched).

**urllib exception wrapping:** ALL urllib exceptions — `urllib.error.HTTPError`, `urllib.error.URLError`, `socket.timeout`, `ssl.SSLError`, `OSError` — are wrapped into `TTSError` subclasses before leaving the client, so the domain exception contract holds (`cli.py:128-130` catches `TTSError`). HTTP non-2xx responses MUST read the error body, sanitize it (strip API key / `Basic` header / secrets), and raise `TTSError` with `status` + truncated body. No retry logic (explicit v1 non-goal).

### NDJSON line handling

Per-line behavior (each line is `\n`-separated, BOM stripped, `\r\n` tolerated):
- (a) Partial final line / truncated JSON → treat as end-of-stream after last valid line; if no valid line was received, raise `TTSError("empty/truncated response")`.
- (b) Line with `result` but missing/empty `audioContent` → skip (no bytes accumulated for that line); not an error.
- (c) Line with `error` → raise `TTSError` with the error message (sanitized).
- (d) Non-JSON line → raise `TTSError("malformed NDJSON line")` (do not silently skip).
- (e) Leading BOM on first line → strip before parsing.

Factory `create_tts_client(settings, inworld_config)`:
- `settings.provider == "qwen"` → `QwenTTSClient(model_path=settings.model_path, device=settings.device)`.
- `settings.provider == "inworld"` → validate `INWORLD_API_KEY` present (else raise `TTSError`-typed config error) → `InworldTTSClient(inworld_config)`.
- Unknown value → raise `ValueError`.

**TTS_PROVIDER ownership:** `TTSConfig.from_env()` reads `os.getenv("TTS_PROVIDER", "qwen")` into `settings.provider`. The CLI passes the `TTSConfig` (not a raw string) into the factory. This removes the cli-vs-config ambiguity — config is the single read-owner of `TTS_PROVIDER`.

**Scope Rule placement (Clean Architecture):**
- `UnsupportedOperationError` → **domain** (`exceptions.py`): domain concept, no deps.
- `InworldConfig`, `TTSConfig.provider` → **infrastructure** (`config.py`): reads env, holds credentials.
- `InworldTTSClient`, `create_tts_client` → **infrastructure**: side-effectful HTTP is an edge concern. Domain stays pure (no `urllib`/`http`).
- `cli.py` change → edge: PURE drop-in swap in `generate`; provider guard in `clone`.
- `dto.py` + `use_cases.py` → application layer: speaker threading (also fixes latent Qwen bug).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/tts_lab/domain/exceptions.py` | Modified | Add `UnsupportedOperationError(TTSError)` with constructor `(message, *, operation, provider)`; export. |
| `src/tts_lab/application/dto.py` | **Modified** | Add `speaker: str \| None = None` to `GenerateSpeechRequest`. |
| `src/tts_lab/application/use_cases.py` | **Modified** | `execute` populates `TTSRequest(speaker=request.speaker)` (fixes latent Qwen dead-code bug too). |
| `src/tts_lab/infrastructure/inworld_client.py` | New | `InworldTTSClient` adapter (`generate` via NDJSON; `clone_voice` raises; no-op `__enter__`/`__exit__`; `_post` injection seam). |
| `src/tts_lab/infrastructure/config.py` | Modified | Add `InworldConfig` frozen dataclass + `from_env()`; add `provider` field to `TTSConfig` (default `qwen`); leave other `TTSConfig` fields untouched. |
| `src/tts_lab/infrastructure/tts_provider.py` | New | `create_tts_client(settings, inworld_config)` factory. |
| `src/tts_lab/cli.py` | Modified | `generate`: PURE drop-in factory swap + pass `--speaker` into DTO; `clone`: add `provider=inworld` guard (refuse with typed error). |
| `tests/unit/test_inworld_client.py` | New | Mock NDJSON tests via `_post` override. |
| `tests/unit/test_tts_provider.py` | New | Factory selection + missing-key error tests. |
| `tests/unit/test_use_case.py` | Modified | Add speaker-threading assertion. |
| `.env.example` | New | ABSENT today — create if convention requires; add `INWORLD_API_KEY=` placeholder (never real values). Only revert if created during impl. |

Unchanged: `domain/protocols.py`, `domain/entities.py`, `infrastructure/qwen_client.py`, `infrastructure/file_storage.py`.

## Decisions Resolved

### 1. `duration_seconds` derivation → compute (approximate) for LINEAR16, `0.0` for MP3

Inworld does not return duration. Choice: **(c)** compute `len(data) / sample_rate` when `audioEncoding == LINEAR16` (default), and return `0.0` for MP3. NOTE: concatenated LINEAR16 chunks may each carry a full WAV header, so the byte count is slightly inflated by N-1 extra headers — this is an **approximate** duration. `FileAudioRepository._read_audio` recomputes the real duration via `soundfile` on `load`, so the field is cosmetic (CLI line, use-case response). Returning `0.0` for MP3 avoids a brittle MP3-frame parser.

### 2. Default `audioEncoding` → LINEAR16 (CONCATENATION UNVERIFIED — flagged)

Choice: **LINEAR16** default (`InworldConfig.audio_encoding = "LINEAR16"`), configurable via `INWORLD_AUDIO_ENCODING` env (`MP3` | `LINEAR16`).

Why: `FileAudioRepository` hardcodes `.wav` — `_sanitize_filename` forces the `.wav` extension, `save_with_hash` always emits `speech_<hash>.wav`, writing `audio.audio_data` verbatim. `AudioResult`'s docstring states "WAV format". Returning MP3 bytes saved as `.wav` is a format lie. MP3 stays selectable for a future change that teaches the repo to honor a format.

⚠️ **TO VERIFY (Decision 2 rationale is "to verify" until confirmed):** The claim that "concatenated LINEAR16 chunks are valid WAV" is **asserted, not verified**. If each Inworld LINEAR16 chunk carries a full WAV header, concatenating N produces N headers and `sf.read()` (`file_storage.py:136`) may read only the first chunk (truncating audio duration). A spec scenario MUST require either: (a) strip intermediate WAV headers and wrap once, OR (b) verify via an integration test (`@pytest.mark.slow`) that `sf.read()` returns the FULL expected duration for a multi-chunk response. Do not mark Decision 2 as verified until confirmed.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Protocol dishonesty: `clone_voice` on `TTSClient`, Inworld can't honor it | Med | Raise typed `UnsupportedOperationError`; Approach 2 deferred. |
| **urllib exceptions leak past the `TTSError` contract** (`HTTPError`/`URLError`/`socket.timeout`/`ssl.SSLError`/`OSError`) | **Med-High** | Wrap ALL urllib exceptions into `TTSError` subclasses at the client boundary; sanitize error bodies; documented non-retry in v1. |
| **LINEAR16 concatenation truncates audio** (N WAV headers → `sf.read()` reads chunk 1 only) | Med | Spec scenario: strip intermediate headers OR integration-test full duration; flag Decision 2 as "to verify". |
| **Clone asymmetry** (`TTS_PROVIDER=inworld` + `clone` → confusing Qwen model-load error) | Med | CLI guard refuses `clone` under `inworld` with a typed notice. |
| **API key leak** in exception messages reaching `cli.py:129` (`console.print({e})`) | Med | Exception messages sanitized + truncated; never contain key, raw body, or `Basic` header. |
| NDJSON edge cases (partial final line, mid-stream `error`, empty `result`, non-JSON, BOM) | Med | Per-line handling enumerated in Approach; unit tests cover each. |
| Factory string-switch grows at 3rd provider | Low | Acceptable for 2 providers; refactor to registry at 3. |
| MP3-selected bytes saved as `.wav` by the repo | Low | Default LINEAR16; MP3 opt-in, documented as needs repo format-awareness follow-up. |
| `instruct` (`TTSRequest.instruct`) silently dropped on Inworld | Low | Document; emit a warning (do not silently drop). |

## Rollback Plan

Constrain the `cli.py` `generate` change to a **PURE drop-in swap** (no config-construction refactor bundled). Reverts:

1. Revert `cli.py` `generate` to direct `QwenTTSClient(...)` construction + revert the speaker pass-through.
2. Revert `cli.py` `clone` provider guard.
3. **Revert `application/dto.py`** (remove `speaker` field).
4. **Revert `application/use_cases.py`** (remove `speaker` population in `execute`).
5. Delete `inworld_client.py`, `tts_provider.py`, `test_inworld_client.py`, `test_tts_provider.py`, and the speaker-threading test in `test_use_case.py`.
6. Revert `config.py` (`InworldConfig` removal + `TTSConfig.provider` field removal) and `exceptions.py` (`UnsupportedOperationError` removal).
7. Revert `.env.example` **only if created during implementation** (confirmed ABSENT today).

Because the default provider is `qwen` and the default no-`-s` Qwen path is preserved by the regression guard (6.3) — `TTSRequest.speaker is None` → Qwen maps to "Serena" via `qwen_client.py:96` `or` fallback — removing this change restores prior default behavior. Note: `-s <name>` on Qwen now intentionally changes voice per the HONOR decision (spec MODIFIED req `Qwen -s semantics — HONOR`); that is a deliberate behavior change, not a regression, and reverts cleanly with the DTO/use-case rollback steps above.

## Dependencies

- **Runtime**: no new DIRECT dependency. stdlib `urllib.request`, `json`, `base64`, `ssl`, `socket` only. (`httpx`/`requests` are transitive via `openai-whisper` but unused by this change.)
- **External service**: Inworld TTS API (`https://api.inworld.ai/tts/v1/voice:stream`), credential from the Inworld portal (`INWORLD_API_KEY` = base64 `keyId:keySecret`).
- **No DIRECT dependency on** httpx/aiohttp/requests (confirmed absent as direct deps in `pyproject.toml`).

## Success Criteria

- [ ] `TTS_PROVIDER=qwen` (or unset) reproduces current Qwen `generate` behavior; all existing unit tests pass.
- [ ] **Speaker actually works:** `tts generate "..." -s Sarah` with `TTS_PROVIDER=inworld` produces audio for voice `Sarah` (not the default); a unit test asserts `request.speaker` reaches `InworldTTSClient.generate` end-to-end through the use case.
- [ ] `TTS_PROVIDER=inworld` with `INWORLD_API_KEY` set produces an `AudioResult` whose `audio_data` is playable WAV (LINEAR16 default), correct `sample_rate`, and **approximate** `duration_seconds` (concatenated WAV headers inflate byte count slightly).
- [ ] **LINEAR16 full-duration verified:** an integration test (`@pytest.mark.slow`) OR a header-strip strategy confirms `sf.read()` returns the FULL expected duration for a multi-chunk response.
- [ ] `InworldTTSClient.clone_voice(...)` raises `UnsupportedOperationError`; `clone` CLI command still works on Qwen.
- [ ] **Clone guard under Inworld:** `TTS_PROVIDER=inworld tts clone ...` refuses with a clear typed notice (no confusing Qwen model-load error).
- [ ] Mid-stream Inworld `error` line raises `TTSError`; text > 2000 chars raises before the network call.
- [ ] **No key in exception messages:** no exception text reaching `cli.py:129` contains the API key, raw response body, or literal `Basic` header (unit test asserts sanitization + truncation).
- [ ] All urllib exceptions (`HTTPError`, `URLError`, `socket.timeout`, `ssl.SSLError`, `OSError`) surface as `TTSError` subclasses.
- [ ] Missing `INWORLD_API_KEY` with `TTS_PROVIDER=inworld` raises a clear config error at client construction.
- [ ] No secret value appears in any log line or test assertion constant.
- [ ] `uv run pytest tests/unit/ -v` green; `uv run mypy src/` clean; `uv run ruff check src/` clean.
- [ ] Domain layer has zero new external imports (no `urllib`/`http` in `src/tts_lab/domain/`).

## Delivery Strategy

Ask-on-risk (matches `openspec/project.md`). Automatic execution. The diff is additive and gated by an env var defaulting to the current provider; risk is concentrated in the new adapter, which is fully unit-tested via the `_post` injection seam (not `urllib.request.urlopen` monkey-patching alone).

## Verified code facts grounding this revision

- `TTSRequest` (`entities.py:10-24`) **already has** `speaker: str | None = None` (line 23) — NO domain change needed.
- `GenerateSpeechRequest` (`dto.py:12-24`) has NO `speaker` field — bug confirmed.
- `GenerateSpeechUseCase.execute` (`use_cases.py:37-40`) builds `TTSRequest(text=..., language=...)` WITHOUT speaker — bug confirmed.
- `cli.py:145` accepts `--speaker` / `-s`; `cli.py:178-181` builds `GenerateSpeechRequest(text=..., language=...)` WITHOUT speaker — dead-code path confirmed.
- `TTSConfig.from_env()` (`config.py:26-38`) is the natural owner of `TTS_PROVIDER` (consistent `os.getenv` pattern).
- `cli.py:174` uses `with QwenTTSClient(...) as client:` — context-manager seam required for `InworldTTSClient`.
- `TTSClient` protocol (`protocols.py:12-36`) — NOT extended (no-op CM is client-internal).
- `.env.example` is ABSENT (only `.env` exists) — confirmed via `ls`.
