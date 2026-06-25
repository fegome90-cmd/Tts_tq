# Design: Inworld Cloud TTS as a Second Provider

## Technical Approach

Add an `InworldTTSClient` infrastructure adapter that implements the existing `TTSClient` protocol via the Inworld `/tts/v1/voice:stream` NDJSON endpoint, plus a `create_tts_client(settings)` factory so the CLI no longer hardwires `QwenTTSClient`. Provider selection reads `TTS_PROVIDER` (default `qwen`) inside `TTSConfig.from_env()` — config is the single owner. A latent dead-code bug (`--speaker` accepted but never threaded) is fixed at the root so per-voice selection actually works. Uses stdlib `urllib.request` only — no new direct dependency.

Maps to proposal Approach 1 (minimal strategy at the edge). Domain layer untouched except for one new typed exception. Gate-2 findings (speaker behavior change, `--instruct` non-goal, urllib wrap exhaustiveness) are folded in below.

## Architecture Decisions

| # | Decision | Choice | Rejected Alternative | Rationale |
|---|----------|--------|----------------------|-----------|
| 1 | Exception hierarchy location | `TTSError` base + `UnsupportedOperationError` in **domain** `exceptions.py`; Inworld-specific subclasses in **infrastructure** `inworld_client.py`, each raising/mapping to a domain `TTSError` before leaving the client | Put all subclasses in domain | Domain stays pure (no `urllib`/`ssl`/`socket` imports) but owns the abstract contract callers catch. Infra owns the concrete wrappers it produces — Clean Architecture's "impure edge maps to pure contract." Verified `cli.py:128` catches `Exception` then exits; `TTSError` is the documented contract. |
| 2 | HTTP seam | `_post(self, payload: dict) -> http.client.HTTPResponse` instance method on `InworldTTSClient`; unit tests **override `_post`** to return a `BytesIO`-backed fake | Monkey-patch `urllib.request.urlopen` | Override is a clean injection point (no global state), lets each test craft exact byte streams for the 5 NDJSON edge cases + each exception. Patching stdlib internals is brittle and doesn't exercise our wrapper logic. |
| 3 | LINEAR16 PCM helper | Pure function `strip_intermediate_wav_headers(chunks: list[bytes]) -> bytes` in `inworld_client.py` (module-level, no `self`): parse first chunk as full RIFF/WAV to get sample_rate+PCM body; for chunks 2..N strip the 44-byte (or fmt-size-derived) RIFF header and keep the PCM body; rebuild one RIFF wrapper around the concatenated bodies | Trust raw concatenation; or `pydub` | `sf.read()` at `file_storage.py:138` reads ONE RIFF block — N concatenated headers truncate to chunk 1 (verified). Pure helper is independently unit-testable with hand-crafted WAV bytes. |
| 4 | Qwen `-s` semantics | **HONOR** — thread `request.speaker` through to Qwen (`qwen_client.py:96` already does `request.speaker or "Serena"`). Add a **default-speaker contract guard**: unit test asserting the default no-`-s` Qwen path keeps `TTSRequest.speaker is None` → Qwen maps to "Serena" via the `or` fallback. This is a CONTRACT lock (input wiring), not a byte-identical output snapshot — the `-s <name>` path is a DELIBERATE behavior change, not a regression | Warn-and-ignore | Gate-2 finding: proposal's "additive, Qwen ignores it" is FALSE — `request.speaker or "Serena"` means `-s Dennis` now changes Qwen's voice. Honoring is the honest fix; the contract guard locks the default INPUT wiring so the latent-bug-fix doesn't silently shift default behavior. (Relabeled from "byte-identical regression guard" per gate-3 — model load is infeasible at unit-test speed.) |
| 5 | Factory construction | `InworldConfig.from_env()` called **eagerly** inside `create_tts_client` when `settings.provider == "inworld"`; key-missing raises `TTSError`-typed config error at construction (not first request) | Lazy (read env on each request) | Fail-fast at construction matches existing `TTSConfig.from_env()` pattern; avoids repeated env reads; missing key surfaces before any network attempt. |
| 6 | Sanitization algorithm | Regex-redact any `INWORLD_API_KEY`-shaped token, the literal `Authorization: Basic ...` header value, and the substring `Basic`; truncate raw response body to ≤512 chars; drop non-ASCII; log only the sanitized form | Block all message context | Gate-1 finding: key could leak via `cli.py:129`. Scrub at the raise site so even a careless `f"..."` stays safe. 512-char cap bounds log noise. |
| 7 | urllib exception wrap set (exhaustive) | Wrap **all** of: `urllib.error.HTTPError`, `urllib.error.URLError`, `socket.timeout`, `ssl.SSLError`, `OSError`, `json.JSONDecodeError`, `binascii.Error` → `TTSError` subclasses before leaving client | Wrap only network errors | Gate-2 finding: `JSONDecodeError` (malformed NDJSON line) and `binascii.Error` (corrupt base64 `audioContent`) are raised *inside* the parse loop and would otherwise leak as `ValueError` past the `TTSError` contract. |

## Data Flow

```
CLI (cli.py generate)
  │ TTSConfig.from_env()  ── reads TTS_PROVIDER (default qwen)
  ▼
create_tts_client(settings)  ── factory: qwen→QwenTTSClient, inworld→InworldTTSClient
  │                                                          │
  │                                                          ▼
  │                                          InworldConfig.from_env() (eager, fail-fast)
  ▼
GenerateSpeechUseCase.execute(request)
  │ request.speaker threaded → TTSRequest(speaker=...)   ◄── latent-bug fix
  ▼
InworldTTSClient.generate(TTSRequest)
  │ 1. len(text) ≤ 2000 pre-check
  │ 2. voice_id = request.speaker or inworld_config.default_voice_id
  │ 3. payload = {text, voiceId, modelId, audioConfig{audioEncoding, sampleRateHertz}}
  │ 4. response = self._post(payload)   ◄── HTTP injection seam (tests override)
  │ 5. NDJSON loop (5 edge cases) → list[bytes] audio chunks
  │ 6. LINEAR16: strip_intermediate_wav_headers(chunks); MP3: b"".join(chunks)
  │ 7. duration = len(pcm)/sample_rate (LINEAR16) | 0.0 (MP3)
  ▼
AudioResult(audio_data, sample_rate, duration_seconds)
  ▼
FileAudioRepository.save_with_hash → speech_<hash>.wav
```

NDJSON parse loop (line-splitter tolerant of partial final line):
- (a) Partial final line / truncated JSON → stop at end-of-stream after last valid line; if **no** valid line → `TTSError("empty/truncated response")`.
- (b) `result` present but missing/empty `audioContent` → skip (no error).
- (c) `error` object → `TTSError` with sanitized message.
- (d) Non-JSON line → `TTSError("malformed NDJSON line")` (never silently skip).
- (e) Leading BOM on first line → strip before parsing; tolerate `\r\n`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/tts_lab/domain/exceptions.py` | Modify | Add `UnsupportedOperationError(TTSError)` with ctor `(message, *, operation: str, provider: str)`; export. |
| `src/tts_lab/application/dto.py` | Modify | Add `speaker: str \| None = None` to `GenerateSpeechRequest` (latent-bug fix). |
| `src/tts_lab/application/use_cases.py` | Modify | `execute` populates `TTSRequest(speaker=request.speaker)` (latent-bug fix; also makes Qwen `-s` honor). |
| `src/tts_lab/infrastructure/config.py` | Modify | Add `InworldConfig` frozen dataclass + `from_env()` (reads `INWORLD_API_KEY`, `INWORLD_BASE_URL`, `INWORLD_DEFAULT_VOICE_ID`, `INWORLD_AUDIO_ENCODING`, `INWORLD_SAMPLE_RATE`, `INWORLD_MODEL_ID`); add `provider: str = "qwen"` to `TTSConfig` + read `TTS_PROVIDER` in `from_env()`. |
| `src/tts_lab/infrastructure/inworld_client.py` | Create | `InworldTTSClient` (NDJSON `generate`; `clone_voice` raises `UnsupportedOperationError`; no-op `__enter__/__exit__`; `_post` seam); infra exception subclasses; `strip_intermediate_wav_headers` pure helper; sanitization fn. |
| `src/tts_lab/infrastructure/tts_provider.py` | Create | `create_tts_client(settings) -> TTSClient` (qwen→Qwen; inworld→validate key→Inworld; unknown→`ValueError`). |
| `src/tts_lab/cli.py` | Modify | `generate`: drop-in factory swap + pass `--speaker` into DTO; `clone`: refuse when `settings.provider == "inworld"` with typed notice (no Qwen model-load confusion). |
| `tests/unit/test_inworld_client.py` | Create | Override `_post` with `BytesIO` NDJSON fixtures (5 edge cases + each exception); `strip_intermediate_wav_headers` unit test; sanitization unit test. |
| `tests/unit/test_tts_provider.py` | Create | Factory qwen/inworld/unknown; missing-key config error. |
| `tests/unit/test_use_cases.py` | Modify | Speaker-threading assertion; **default-speaker contract guard**: default no-`-s` Qwen path keeps `TTSRequest.speaker is None` (locks input wiring; NOT byte snapshot). |
| `tests/integration/test_inworld_live.py` | Create (DEFERRED) | `@pytest.mark.slow`: real API + full-duration verification — **DEFERRED** (key rotation); header-strip unit test 4.1 is the accepted deterministic substitute. |

Unchanged: `domain/protocols.py`, `domain/entities.py`, `infrastructure/qwen_client.py`, `infrastructure/file_storage.py`. `--instruct` is acknowledged as **also dead code** in the same pattern but explicitly **OUT OF SCOPE** (gate-2 honesty requirement) — `TTSRequest.instruct` exists (`entities.py:24`) and `qwen_client.py:97` consumes it, but DTO/use-case threading is a separate change.

## Interfaces / Contracts

```python
# domain/exceptions.py (Modify)
class UnsupportedOperationError(TTSError):
    """Provider cannot perform this operation."""
    def __init__(self, message: str, *, operation: str, provider: str):
        super().__init__(message)
        self.operation = operation
        self.provider = provider

# infrastructure/inworld_client.py (Create) — infra-only exception wrappers
class InworldAPIError(TTSError): ...      # HTTP non-2xx
class InworldConnectionError(TTSError): ...  # URLError/socket.timeout/ssl/OSError
class InworldParseError(TTSError): ...    # JSONDecodeError/binascii.Error/malformed line

class InworldTTSClient:
    def __init__(self, config: InworldConfig) -> None: ...
    def generate(self, request: TTSRequest) -> AudioResult: ...  # implements TTSClient
    def clone_voice(self, profile, text) -> AudioResult:  # raises UnsupportedOperationError
        raise UnsupportedOperationError(
            "Inworld does not support voice cloning",
            operation="clone_voice", provider="inworld",
        )
    def __enter__(self) -> "InworldTTSClient": return self   # no-op CM
    def __exit__(self, *exc) -> None: ...                      # no-op
    def _post(self, payload: dict) -> Any: ...                 # HTTP seam (tests override)

def strip_intermediate_wav_headers(chunks: list[bytes]) -> tuple[bytes, int]: ...  # pure → (wav_bytes, sample_rate)

# infrastructure/tts_provider.py (Create)
def create_tts_client(settings: TTSConfig) -> TTSClient: ...  # EAGER single-param — InworldConfig.from_env() called inside when provider=="inworld"
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | 7 NDJSON edge cases | Override `_post` with `BytesIO` fixtures per case (happy, BOM, `\r\n`, error, non-JSON, empty/missing audioContent skip, partial/truncated final line). |
| Unit | Each exception wrap | `_post` raising `HTTPError`/`URLError`/`socket.timeout`/`ssl.SSLError`/`OSError`/`JSONDecodeError`/`binascii.Error` → assert `TTSError` subclass. |
| Unit | `strip_intermediate_wav_headers` | Hand-crafted 3-chunk WAV bytes → assert single valid RIFF header + `sf.read()` returns full duration. |
| Unit | Sanitization | Fixture messages containing key/`Basic`/raw body/non-ASCII → assert scrubbed + truncated ≤512. |
| Unit | Factory | qwen/inworld/unknown; missing `INWORLD_API_KEY` → `TTSError`. |
| Unit | **Default-speaker contract guard** | Default no-`-s` Qwen path → assert `TTSRequest.speaker is None` → Qwen maps to "Serena" via `or` fallback (locks default INPUT wiring; NOT a byte snapshot — model load infeasible at unit speed). `-s <name>` is a deliberate behavior change per HONOR. |
| Unit | Speaker threading | `generate -s Sarah` → assert `request.speaker == "Sarah"` reaches client end-to-end. |
| Integration (`@slow`) — DEFERRED | Real Inworld API | `tests/integration/test_inworld_live.py` DEFERRED (key rotation in progress); the deterministic header-strip unit test 4.1 is the accepted substitute. Header-strip verified deterministically; live-API verification deferred. |

## Migration / Rollout

No data migration. Feature is gated by `TTS_PROVIDER` env (default `qwen` → unchanged behavior). Per proposal rollback plan: `cli.py generate` is a pure drop-in factory swap (no config refactor bundled); revert is mechanical. `.env.example` created **only if** project convention requires — absent today, revert if created.

## Open Questions

- [ ] `.env.example`: confirm whether project convention requires creating it (currently absent; only `.env` exists). Decision deferred to apply phase unless convention check resolves it sooner.
- [ ] `INWORLD_DEFAULT_VOICE_ID` default value — proposal references Sarah/Dennis as preset voices but does not pin a default; apply phase should pick one (or require explicit).
