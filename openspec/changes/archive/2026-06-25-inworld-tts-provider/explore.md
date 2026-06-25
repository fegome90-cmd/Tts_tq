# Exploration: inworld-tts-provider

## Current State

TTS Lab is a Clean Architecture service with a **single TTS provider**: the local Qwen3-TTS model. The domain defines a `TTSClient` protocol (`protocols.py`) with two methods — `generate(request: TTSRequest) -> AudioResult` (preset voices) and `clone_voice(profile: VoiceProfile, text: str) -> AudioResult` (reference-audio cloning). The only implementation is `QwenTTSClient` (`infrastructure/qwen_client.py`), which lazily loads a PyTorch model.

Provider selection today is **direct instantiation**. `cli.py` builds `QwenTTSClient(model_path=config.model_path, device=config.device)` directly and injects it into `GenerateSpeechUseCase(tts_client=client, audio_repo=repo)`. There is **no factory, registry, or strategy** — the use case receives the client via constructor DI, but the *choice* of client is hardwired at the CLI edge.

`AudioResult` is **buffered bytes** (`audio_data: bytes`, `sample_rate: int`, `duration_seconds: float`). The repository writes those bytes verbatim (`save_with_hash`). There is no async/streaming surface anywhere in the domain.

Config is a single `TTSConfig` dataclass (`infrastructure/config.py`) holding only Qwen concerns (`model_path`, `device`, `output_dir`, `voices_dir`). It is built via `TTSConfig.from_env()` and is not coupled to pydantic-settings despite the CLAUDE.md mention — it is a plain frozen dataclass reading `os.getenv`.

## Affected Areas

- `src/tts_lab/domain/protocols.py` — `TTSClient` protocol. Fits cloud providers for `generate`; `clone_voice` does not map cleanly to Inworld (no reference-audio clone path, only voice IDs).
- `src/tts_lab/domain/entities.py` — `TTSRequest` (text/language/speaker/instruct), `AudioResult` (buffered bytes). Impedance mismatch on voice identity (`speaker` vs `voiceId`) and output format (WAV bytes vs MP3 bytes).
- `src/tts_lab/application/use_cases.py` — `GenerateSpeechUseCase` constructor injection point. No change needed if selection stays at the edge.
- `src/tts_lab/infrastructure/qwen_client.py` — template adapter for a new `InworldTTSClient`.
- `src/tts_lab/infrastructure/config.py` — needs Inworld settings (api key, base URL, model, default voice).
- `src/tts_lab/cli.py` — the only place that picks the client; needs a selection mechanism (factory) when a provider flag is introduced.
- `tests/unit/test_qwen_client.py` — test pattern to replicate (Mock-based, `patch.dict("sys.modules", ...)`, fixture `sample_audio_data`).
- `pyproject.toml` — dependency review. **No HTTP client present today** (no httpx/aiohttp/requests).

## Approaches

### 1. Minimal strategy at the edge + InworldTTSClient adapter (RECOMMENDED)

Add `InworldTTSClient` implementing `TTSClient.generate`. Add a small `tts_provider_factory(settings)` function in infrastructure that returns either `QwenTTSClient` or `InworldTTSClient` based on a `TTS_PROVIDER` env var. Keep selection in `cli.py`/infrastructure — domain stays pure. `clone_voice` raises `NotImplementedError` (or a typed `UnsupportedOperationError`) for Inworld since cloud TTS uses voice IDs, not reference audio.

- Pros: Smallest delta; honors existing architecture (selection is an edge concern); no domain protocol churn; matches the Qwen adapter shape; testable with Mocks.
- Cons: Two providers diverge on capability (clone unavailable for Inworld) — protocol "lies" slightly. Factory is a single decision point that could grow.
- Effort: **Low–Medium**.

### 2. Split protocols (SpeechSynthesizer + VoiceCloner)

Decompose `TTSClient` into two role protocols: `SpeechSynthesizer.generate` and `VoiceCloner.clone_voice`. Each provider implements only what it supports. The use case depends on `SpeechSynthesizer`; cloning becomes a separate use case.

- Pros: Honest interfaces; type system enforces capability; future cloud clone endpoint (Inworld voice cloning API) slots in cleanly.
- Cons: Bigger refactor; touches use case, CLI, tests; ripples through existing working code.
- Effort: **Medium–High**.

### 3. Adapter with async streaming + new `AudioStream` entity

Introduce an `AsyncTTSClient` protocol returning an async iterator of chunks, plus a new domain entity for streams. InworldTTSClient streams the NDJSON response.

- Pros: Matches Inworld's native model; enables low-latency playback later.
- Cons: Premature for v1; current `AudioResult` is buffered and the repo writes whole files; forces async into a sync codebase (use case is sync); breaks `AudioResult` contract.
- Effort: **High**.

## Recommendation

**Approach 1 for v1.** The MINIMAL viable path is buffer-to-completion: `InworldTTSClient.generate` POSTs to `/tts/v1/voice:stream`, consumes the NDJSON stream line-by-line, base64-decodes each `result.audioContent`, accumulates bytes, and returns a single `AudioResult(audio_data=<all bytes>, sample_rate, duration_seconds)`. This matches the existing `AudioResult` contract exactly and the repository writes it unchanged. Streaming (Approach 3) can be a later additive change without breaking the buffered path.

Selection mechanism: a **factory function** in infrastructure (`create_tts_client(config) -> TTSClient`), because the moment there are 2+ providers the choice is shared logic (Scope Rule). It is NOT an abstract factory/framework — just one function returning a `TTSClient`. `GenerateSpeechUseCase` stays unchanged; it already receives the client via DI.

For `clone_voice` on Inworld: raise a domain `UnsupportedOperationError` (new, extends `TTSError`). Do **not** silently no-op.

## Protocol & Entity Mapping (verified against code + official docs)

- Inworld request body fields (official `/tts/v1/voice:stream`): `text`, `voiceId`, `modelId`, `audioConfig: { audioEncoding, sampleRateHertz }`, optional `temperature`, optional `timestampType`.
- Inworld response: **a stream of JSON objects** (one per line, NDJSON). Each object's `result.audioContent` is **base64-encoded audio**. With `LINEAR16`, every chunk includes a complete WAV header (so each is independently playable); with `MP3`, raw MP3 frames. An `error` object may appear on any line mid-stream.
- Mapping: `TTSRequest.text` → `text`. `TTSRequest.speaker or <config default voice>` → `voiceId`. `TTSRequest.language` → no direct Inworld field (language is implicit in the model/voice); document and ignore or use to pick a voice. `audioConfig.audioEncoding` → `MP3` (smaller; domain `AudioResult` is opaque bytes so format-agnostic). `sampleRateHertz` → 22050 default; set `AudioResult.sample_rate` accordingly.
- Impedance mismatch: Qwen "speaker"/reference-audio cloning has no Inworld analog for v1. Inworld "voiceId" (e.g., "Sarah", "Dennis") is closer to Qwen's preset `speaker`. `instruct` (style instructions) has no Inworld equivalent.

## Config Extension

Add Inworld fields to a **separate** config dataclass `InworldConfig` (frozen, `from_env()`) to avoid coupling with `TTSConfig`:
- `api_key: str | None` from `INWORLD_API_KEY` (the pre-base64 `keyId:keySecret` token, sent verbatim as `Authorization: Basic <value>`). REQUIRED at client construction when provider=Inworld; raise a clear error if missing.
- `base_url: str = "https://api.inworld.ai"` (env `INWORLD_BASE_URL`).
- `model_id: str = "inworld-tts-1.5-max"` (env `INWORLD_MODEL_ID`).
- `default_voice_id: str = "Sarah"` (env `INWORLD_DEFAULT_VOICE`).
- `sample_rate_hertz: int = 22050` (env `INWORLD_SAMPLE_RATE`).
- `audio_encoding: Literal["MP3", "LINEAR16"] = "MP3"`.

Plus a top-level `TTS_PROVIDER` env var (`qwen` | `inworld`, default `qwen`) read by the factory.

## Dependency

**None of httpx, aiohttp, or requests are present** in `pyproject.toml` today. `urllib.request` is in the stdlib and suffices for a synchronous buffered POST with streaming response. Recommendation for v1: **use `urllib.request`** (no new dependency) to keep the change minimal. If latency/streaming playback becomes a goal later, add `httpx` (best async + sync story) in a separate change. Do NOT add aiohttp just for this.

## Testing Strategy

Replicate `test_qwen_client.py`'s Mock style. Unit tests for `InworldTTSClient`:
- Construct with config; assert Authorization header value is `Basic <key>` (never log it).
- Mock the HTTP layer (a fake response object yielding NDJSON lines) via dependency injection or `patch` of the request function. Provide a fixture `sample_ndjson_stream` returning 3 lines, each `{"result": {"audioContent": base64(<chunk>)}}`.
- Assert `generate` accumulates all base64-decoded chunks, returns an `AudioResult` with concatenated bytes, correct `sample_rate`, and nonzero `duration_seconds` (or 0.0 if duration cannot be derived — note: Inworld does not return duration; **compute it from bytes** by parsing WAV/MP3, or set `duration_seconds=0.0` and document, or request `LINEAR16` and compute `len(data)/sample_rate`). This is an open decision for propose.
- Assert a mid-stream `{"error": {...}}` line raises `TTSError`.
- Assert `clone_voice` raises `UnsupportedOperationError`.
- Assert missing `INWORLD_API_KEY` raises a config error at construction.
- No real network calls; mark any live test `@pytest.mark.slow`/integration.

## Security

- API key MUST come from `INWORLD_API_KEY` env var. Never hardcode, never commit, never log (the client must not log headers or the key). The value is already the base64 secret copied from the Inworld portal; treat it as a credential.
- Tests must use a dummy key (e.g., `"Basic dGVzdDp0ZXN0"`); assert via constant, never real.
- Add `INWORLD_API_KEY` to `.env.example` (if one exists) with a placeholder; do not write the real value anywhere.
- The client validates input text length client-side (≤2000 chars per Inworld spec) to fail fast and avoid leaking oversized payloads.

## Risks

- **Protocol honesty**: `TTSClient.clone_voice` exists; Inworld cannot satisfy it. Mitigated by raising a typed `UnsupportedOperationError` — but callers must handle it. Alternative (Approach 2) is cleaner but bigger.
- **Duration derivation**: `AudioResult.duration_seconds` is expected; Inworld doesn't return it. v1 decision needed (compute from bytes vs 0.0).
- **NDJSON parsing edge cases**: partial final line, `error` objects mid-stream, empty `result`. Tests must cover these.
- **Format mismatch with repo**: `FileAudioRepository` writes `audio_data` bytes as-is. If Inworld returns MP3 but downstream tools expect WAV, file extension/headers may mislead. Decide audio encoding deliberately.
- **No existing HTTP client**: adding stdlib `urllib` is fine for v1, but error handling/timeout/retry must be hand-rolled.
- **Provider-factory growth**: if a 3rd provider arrives, the factory + `TTS_PROVIDER` string switch becomes unwieldy — acceptable for 2 providers, revisit at 3.

## Ready for Proposal

**Yes.** Clear scope, single new adapter, minimal domain impact, config + factory + tests. The orchestrator should tell the user the two open decisions for the proposal phase: (a) `duration_seconds` derivation strategy, (b) default `audioEncoding` (MP3 vs LINEAR16) and whether the repo/file extension needs to learn the format.
