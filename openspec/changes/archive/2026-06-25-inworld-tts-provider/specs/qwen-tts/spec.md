# Spec Delta: Inworld TTS Provider + Speaker Threading

## ADDED Requirements

### Requirement: Inworld NDJSON generate contract

The `InworldTTSClient.generate` SHALL POST to `/tts/v1/voice:stream` with `Authorization: Basic {api_key}`, parse the NDJSON response line-by-line, base64-decode each `result.audioContent`, and accumulate raw audio bytes into an `AudioResult`. The client SHALL select `voiceId` from `request.speaker` when present, else from `InworldConfig.default_voice_id`. The default `audioEncoding` SHALL be `LINEAR16`.

#### Scenario: Happy path single-chunk LINEAR16

- WHEN generate is called with valid text and a known speaker on provider=inworld
- THEN the client SHALL return an `AudioResult` whose `audio_data` is a single valid WAV
- AND `sample_rate` SHALL equal the requested `sampleRateHertz`.

#### Scenario: Speaker overrides default voice

- WHEN `request.speaker` is provided
- THEN the request body `voiceId` SHALL equal `request.speaker`, not the config default.

### Requirement: Single-WAV output for multi-chunk LINEAR16

Because each LINEAR16 NDJSON chunk carries a full WAV header, concatenating N chunks verbatim yields N headers and `soundfile.read` truncates to chunk 1. The client SHALL strip intermediate WAV headers and wrap the concatenated PCM payload in exactly one WAV header, producing a deterministic valid single-WAV `audio_data`.

#### Scenario: Multi-chunk yields full-duration single WAV

- WHEN the stream emits 3 LINEAR16 chunks
- THEN the resulting `audio_data` SHALL contain exactly one WAV header
- AND `soundfile.read` on the bytes SHALL return the full concatenated duration.

### Requirement: Text length validated before network

The client SHALL raise a `TTSError` when `len(request.text) > 2000` before issuing any HTTP request.

#### Scenario: Oversized text rejected pre-network

- WHEN generate is called with text of length 2001
- THEN a `TTSError` SHALL be raised
- AND no HTTP request SHALL be sent.

### Requirement: Duration is approximate

`duration_seconds` SHALL be computed as `len(pcm_bytes) / sample_rate` for LINEAR16 and SHALL be `0.0` for MP3. The value is approximate; `FileAudioRepository._read_audio` recomputes the true duration via soundfile on load.

#### Scenario: MP3 duration is zero

- WHEN `audioEncoding` is MP3
- THEN `AudioResult.duration_seconds` SHALL be `0.0`.

### Requirement: clone_voice typed refusal on Inworld

`InworldTTSClient.clone_voice` SHALL raise `UnsupportedOperationError(message, *, operation="clone_voice", provider="inworld")`. The domain `TTSClient` protocol SHALL NOT be modified.

#### Scenario: Clone on Inworld raises typed error

- WHEN clone_voice is invoked on an InworldTTSClient
- THEN `UnsupportedOperationError` SHALL be raised with `operation` and `provider` keyword fields.

### Requirement: No-op context manager on InworldTTSClient

`InworldTTSClient` SHALL implement `__enter__` returning self and `__exit__` returning `None` as no-ops, so the CLI `with` block works unchanged. The domain `TTSClient` protocol SHALL NOT declare these methods.

#### Scenario: With-block works without protocol change

- WHEN `InworldTTSClient` is used in a `with` statement
- THEN `__enter__` SHALL return the client instance
- AND the `TTSClient` Protocol SHALL remain unchanged.

### Requirement: HTTP injection seam for tests

`InworldTTSClient` SHALL expose a `_post(payload)` method returning the raw response bytes/stream. Tests SHALL exercise the client by overriding `_post` rather than monkey-patching `urllib.request.urlopen` alone.

#### Scenario: Tests override _post

- WHEN a test injects a fake `_post` returning canned NDJSON
- THEN generate SHALL produce the expected `AudioResult` without network access.

### Requirement: Factory provider selection

`create_tts_client(settings)` SHALL return `QwenTTSClient` when `settings.provider == "qwen"`, `InworldTTSClient` when `settings.provider == "inworld"` (requiring `INWORLD_API_KEY`, else a `TTSError`-typed config error), and raise `ValueError` for any unknown provider. `TTSConfig.from_env` SHALL be the single read-owner of `TTS_PROVIDER` (default `qwen`).

#### Scenario: Unknown provider rejected

- WHEN `settings.provider` is an unsupported string
- THEN `create_tts_client` SHALL raise `ValueError`.

#### Scenario: Inworld without API key

- WHEN provider is inworld and `INWORLD_API_KEY` is unset
- THEN a `TTSError` subclass SHALL be raised at construction.

## MODIFIED Requirements

### Requirement: Speaker threading end-to-end

`GenerateSpeechRequest` SHALL gain `speaker: str | None = None`. `GenerateSpeechUseCase.execute` SHALL populate `TTSRequest(speaker=request.speaker)`. The CLI `generate` command SHALL pass `--speaker` into the DTO. This reaches both `InworldTTSClient` (voice selection) and `QwenTTSClient` (multi-speaker models). This MODIFIES prior behavior: `--speaker` was previously accepted by the CLI but silently dropped.

#### Scenario: Speaker reaches Qwen

- WHEN `tts generate -s Dennis` runs on the default Qwen provider
- THEN `QwenTTSClient.generate` SHALL receive `request.speaker == "Dennis"`
- AND the model SHALL be invoked with `speaker="Dennis"` (not the prior hardcoded `"Serena"`).

#### Scenario: Speaker reaches Inworld

- WHEN provider=inworld and `-s Sarah` is passed
- THEN the Inworld request body `voiceId` SHALL be `"Sarah"`.

### Requirement: Qwen `-s` semantics — HONOR

`QwenTTSClient` SHALL honor `request.speaker` (passing it to `generate_custom_voice`) rather than warn-and-ignore. Rationale: `entities.py:17` documents speaker for multi-speaker models, and `qwen_client.py:96` already consumes `request.speaker or "Serena"` — the field was designed to be honored; warn-and-ignore would preserve dead-code semantics.

#### Scenario: Default Qwen path byte-identical to pre-change (regression guard)

- WHEN `tts generate "Hello"` runs with no `-s` on provider=qwen
- THEN `request.speaker` SHALL be `None`
- AND `QwenTTSClient` SHALL invoke the model with `speaker="Serena"` (the `or` fallback)
- AND the generated audio SHALL be byte-identical to pre-change behavior.

## ADDED Requirements (error wrapping)

### Requirement: Exhaustive urllib/json/binascii exception wrapping

ALL of `urllib.error.HTTPError`, `urllib.error.URLError`, `socket.timeout`, `ssl.SSLError`, `OSError`, `json.JSONDecodeError` (malformed NDJSON line), and `binascii.Error` (corrupt base64 `audioContent`) raised inside the client SHALL be wrapped into `TTSError` subclasses before leaving the client, so the domain exception contract (caught at `cli.py:128-130`) holds.

#### Scenario: Malformed JSON line wrapped

- WHEN a stream line is not valid JSON
- THEN a `TTSError` SHALL be raised (not a bare `JSONDecodeError`).

#### Scenario: Corrupt base64 wrapped

- WHEN `result.audioContent` is not valid base64
- THEN a `TTSError` SHALL be raised (not a bare `binascii.Error`).

### Requirement: Key-leak sanitization in error messages

HTTP non-2xx responses SHALL produce a `TTSError` whose message contains the status code and a sanitized+truncated body. The `TTSError.message` SHALL NOT contain the API key, the `Authorization: Basic` header, or the raw request body as a substring.

#### Scenario: HTTP 500 sanitized

- WHEN the API returns HTTP 500 with a body
- THEN the `TTSError` message SHALL include the status and a truncated body
- AND SHALL NOT contain the key or the `Basic` header.

## ADDED Requirements (NDJSON edge cases)

### Requirement: NDJSON edge-case handling

The client SHALL handle each `\n`-separated line: (a) leading BOM on the first line stripped before parsing; (b) `\r\n` line endings tolerated; (c) `error` object on any line → `TTSError` with sanitized message; (d) non-JSON line → `TTSError("malformed NDJSON line")` (not silently skipped); (e) `result` present but `audioContent` missing/empty → skip without error; (f) partial/truncated final line → end-of-stream after the last valid line; if no valid line was seen → `TTSError("empty/truncated response")`.

#### Scenario: Error line mid-stream

- WHEN a line contains an `error` object
- THEN a `TTSError` SHALL be raised with a sanitized message.

#### Scenario: Empty audioContent skipped

- WHEN a line has `result` but empty `audioContent`
- THEN the line SHALL be skipped without raising.

#### Scenario: BOM stripped

- WHEN the first line begins with a UTF-8 BOM
- THEN the BOM SHALL be stripped before JSON parsing.

## NON-GOALS

- **`--instruct` threading is OUT OF SCOPE.** `--instruct` (cli.py:146-148) is dead code in the same pattern as `--speaker` was: the CLI accepts it, the DTO drops it, and `use_cases.py` never populates `TTSRequest.instruct` (though `entities.py:24` has the field and `qwen_client.py:97` consumes it). This change fixes `speaker` only; `instruct` remains a known latent bug to be addressed separately.
- Async streaming / `AudioStream` entity — deferred.
- Protocol split (`SpeechSynthesizer` + `VoiceCloner`) — deferred.
- Retry/backoff — explicit v1 non-goal.
- Voice cloning via Inworld — no ref-audio clone in v1.
