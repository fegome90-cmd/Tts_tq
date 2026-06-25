"""Tests for the Inworld TTS client adapter.

TDD RED Phase: These tests define expected behavior BEFORE implementation.

Tests use the ``_post`` override seam (subclass returning canned NDJSON bytes)
rather than monkey-patching ``urllib.request.urlopen``. The pure helper
``_wrap_urllib_error`` is unit-tested directly.
"""

import base64
import email.message
import io
import json
import ssl
import struct
import urllib.error
from typing import Any

import pytest

from tts_lab.domain.entities import AudioResult, TTSRequest, VoiceProfile
from tts_lab.domain.exceptions import TTSError, UnsupportedOperationError
from tts_lab.infrastructure.config import InworldConfig

# ---------------------------------------------------------------------------
# Helpers for hand-crafting WAV bytes (deterministic, no model needed).
# ---------------------------------------------------------------------------


def _make_wav_bytes(pcm_samples: bytes, sample_rate: int, num_channels: int = 1,
                    bits_per_sample: int = 16) -> bytes:
    """Build a complete RIFF/WAVE byte blob around PCM samples."""
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(pcm_samples)
    fmt_chunk = struct.pack(
        "<HHIIHH",
        1,                  # PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    )
    riff = b"RIFF"
    wave = b"WAVE"
    fmt = b"fmt "
    data = b"data"
    riff_size = 4 + (8 + len(fmt_chunk)) + (8 + data_size)
    return (
        riff + struct.pack("<I", riff_size) + wave
        + fmt + struct.pack("<I", len(fmt_chunk)) + fmt_chunk
        + data + struct.pack("<I", data_size) + pcm_samples
    )


def _ndjson_line(audio_b64: str | None = None, *, sample_rate: int = 24000,
                 error: dict[str, Any] | None = None) -> str:
    """Build a single NDJSON line carrying result.audioContent or an error."""
    if error is not None:
        return json.dumps({"error": error})
    result: dict[str, Any] = {"sampleRateHertz": sample_rate}
    if audio_b64 is not None:
        result["audioContent"] = audio_b64
    return json.dumps({"result": result})


class _FakePostClient:
    """Mixin holding a canned NDJSON byte stream returned by _post.

    Subclasses of InworldTTSClient override ``_post`` directly; this helper
    just prepares bytes + records the payload passed in.
    """

    pass


def _make_client(ndjson_bytes: bytes, **config_kwargs: Any) -> Any:
    """Build an InworldTTSClient whose _post returns canned NDJSON bytes."""
    from tts_lab.infrastructure import inworld_client

    cfg_kwargs: dict[str, Any] = {"api_key": "dGhpcy1pcy1hLWZha2Uta2V5"}
    cfg_kwargs.update(config_kwargs)
    config = InworldConfig(**cfg_kwargs)

    recorded: dict[str, Any] = {}

    class _Client(inworld_client.InworldTTSClient):
        def _post(self, payload: dict[str, Any]) -> io.BytesIO:
            recorded["payload"] = payload
            return io.BytesIO(ndjson_bytes)

    client = _Client(config)
    return client, recorded


def _make_raising_client(exc: BaseException, **config_kwargs: Any) -> Any:
    """Build a client whose _post raises a canned exception."""
    from tts_lab.infrastructure import inworld_client

    cfg_kwargs: dict[str, Any] = {"api_key": "fake-key"}
    cfg_kwargs.update(config_kwargs)
    config = InworldConfig(**cfg_kwargs)

    class _Client(inworld_client.InworldTTSClient):
        def _post(self, payload: dict[str, Any]) -> io.BytesIO:
            raise exc

    return _Client(config)


# ===========================================================================
# 4.1 / 4.2 — strip_intermediate_wav_headers (pure helper)
# ===========================================================================


class TestStripIntermediateWavHeaders:
    """Pure helper: N concatenated WAV chunks -> 1 RIFF header, full duration."""

    def test_three_chunks_yield_single_riff_header_and_full_duration(self):
        """3 LINEAR16 chunks -> exactly 1 RIFF header; sf.read full duration."""
        import soundfile as sf

        from tts_lab.infrastructure.inworld_client import (
            strip_intermediate_wav_headers,
        )

        sample_rate = 24000
        # 0.5s of PCM per chunk (zeros) — 3 chunks = 1.5s total.
        per_chunk_samples = sample_rate // 2
        # int16 little-endian zeros
        pcm_chunk = b"\x00\x00" * per_chunk_samples
        chunk = _make_wav_bytes(pcm_chunk, sample_rate)

        wav_bytes, sr = strip_intermediate_wav_headers([chunk, chunk, chunk])

        assert sr == sample_rate
        # Exactly one RIFF header.
        assert wav_bytes.count(b"RIFF") == 1
        assert wav_bytes.count(b"data") == 1
        # sf.read returns full duration (3 * 0.5s = 1.5s).
        data, read_sr = sf.read(io.BytesIO(wav_bytes))
        assert read_sr == sample_rate
        assert len(data) == per_chunk_samples * 3

    def test_single_chunk_passes_through(self):
        """Single chunk -> still exactly one RIFF header."""
        from tts_lab.infrastructure.inworld_client import (
            strip_intermediate_wav_headers,
        )

        sr = 24000
        pcm = b"\x01\x00" * 100
        chunk = _make_wav_bytes(pcm, sr)
        wav_bytes, out_sr = strip_intermediate_wav_headers([chunk])
        assert wav_bytes.count(b"RIFF") == 1
        assert out_sr == sr


# ===========================================================================
# 4.3 — _post seam: 7 NDJSON edge cases
# ===========================================================================


class TestPostSeam:
    """Override _post to feed canned NDJSON; 7 edge cases (a-g)."""

    def test_a_happy_single_chunk(self):
        """(a) Happy path: one valid result line -> AudioResult."""
        pcm = b"\x00\x00" * 240  # 240 int16 samples
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        ndjson = _ndjson_line(b64, sample_rate=24000) + "\n"

        client, _ = _make_client(ndjson.encode("utf-8"))
        result = client.generate(TTSRequest(text="hi", language="English"))

        assert isinstance(result, AudioResult)
        assert result.sample_rate == 24000

    def test_b_bom_first_line_stripped(self):
        """(b) Leading UTF-8 BOM on first line is stripped before parse."""
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        line = _ndjson_line(b64, sample_rate=24000)
        ndjson = b"\xef\xbb\xbf" + (line + "\n").encode("utf-8")

        client, _ = _make_client(ndjson)
        result = client.generate(TTSRequest(text="hi"))
        assert isinstance(result, AudioResult)

    def test_c_crlf_tolerated(self):
        """(c) \\r\\n line endings are tolerated."""
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        ndjson = (_ndjson_line(b64) + "\r\n").encode("utf-8")

        client, _ = _make_client(ndjson)
        result = client.generate(TTSRequest(text="hi"))
        assert isinstance(result, AudioResult)

    def test_d_error_object_raises_sanitized_tts_error(self):
        """(d) An error object line -> TTSError (no key/body leak)."""
        err = {"message": "boom internal", "code": 500}
        ndjson = (_ndjson_line(error=err) + "\n").encode("utf-8")

        client, _ = _make_client(ndjson)
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="hi"))

    def test_e_non_json_line_raises_tts_error(self):
        """(e) A non-JSON line -> TTSError('malformed NDJSON line')."""
        ndjson = b"this is not json at all\n"
        client, _ = _make_client(ndjson)
        with pytest.raises(TTSError, match="malformed"):
            client.generate(TTSRequest(text="hi"))

    def test_f_empty_audio_content_skipped(self):
        """(f) result with empty/missing audioContent -> skipped, no error.

        A subsequent valid line still produces an AudioResult.
        """
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        # First line: result but no audioContent. Second: valid.
        line1 = _ndjson_line(None)  # no audioContent key
        line2 = _ndjson_line(b64)
        ndjson = (line1 + "\n" + line2 + "\n").encode("utf-8")

        client, _ = _make_client(ndjson)
        result = client.generate(TTSRequest(text="hi"))
        assert isinstance(result, AudioResult)

    def test_g_partial_truncated_final_no_valid_line_raises(self):
        """(g) No valid line ever seen -> TTSError('empty/truncated response')."""
        ndjson = b'{"result": {"sampleRateHertz": 24000, "audioCon'  # truncated
        client, _ = _make_client(ndjson)
        with pytest.raises(TTSError, match="empty/truncated"):
            client.generate(TTSRequest(text="hi"))

    def test_h_truncated_final_line_after_valid_line_returns_audioresult(self):
        """(h) Recovery: valid audio line + '\\n' + truncated-final-line ('{...').

        The real-world truncation path: Inworld sometimes drops the connection
        mid-stream. A line that looks started as JSON (begins with '{') but
        fails JSON parse is treated as end-of-stream and the parse breaks out
        of the loop. If at least one valid audio line was already collected,
        ``generate()`` returns an ``AudioResult`` (does NOT raise). This locks
        the recovery path so a future change can't silently re-introduce a
        raise-on-truncation regression.
        """
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        valid_line = _ndjson_line(b64, sample_rate=24000)
        # A truncated line that looks like it started as JSON.
        truncated_line = '{"result":{"audioContent":"SGVsbG8'
        ndjson = (valid_line + "\n" + truncated_line).encode("utf-8")

        client, _ = _make_client(ndjson)
        result = client.generate(TTSRequest(text="hi"))

        # Must return an AudioResult — the truncation is recovered, not raised.
        assert isinstance(result, AudioResult)
        assert result.sample_rate == 24000


# ===========================================================================
# 4.4 — generate happy path details + text length
# ===========================================================================


class TestGenerateHappyPath:
    """generate returns AudioResult with sample_rate from sampleRateHertz."""

    def test_sample_rate_matches_response(self):
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 22050)
        b64 = base64.b64encode(chunk).decode("ascii")
        ndjson = (_ndjson_line(b64, sample_rate=22050) + "\n").encode("utf-8")

        client, _ = _make_client(ndjson)
        result = client.generate(TTSRequest(text="hi"))
        assert result.sample_rate == 22050

    def test_speaker_overrides_default_voice_id(self):
        """request.speaker overrides config.default_voice_id in payload."""
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        ndjson = (_ndjson_line(b64) + "\n").encode("utf-8")

        client, recorded = _make_client(ndjson, default_voice_id="Sarah")
        client.generate(TTSRequest(text="hi", speaker="Dennis"))

        payload = recorded["payload"]
        assert payload["voiceId"] == "Dennis"

    def test_default_voice_id_used_when_no_speaker(self):
        """No speaker -> payload voiceId == config.default_voice_id."""
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        ndjson = (_ndjson_line(b64) + "\n").encode("utf-8")

        client, recorded = _make_client(ndjson, default_voice_id="Sarah")
        client.generate(TTSRequest(text="hi"))
        assert recorded["payload"]["voiceId"] == "Sarah"


class TestTextLength:
    """Text length validated before any network call."""

    def test_text_over_2000_raises_before_post(self):
        client, _ = _make_client(b"")  # empty -> _post would yield no lines
        long_text = "a" * 2001
        with pytest.raises(TTSError, match="2000"):
            client.generate(TTSRequest(text=long_text))

    def test_text_exactly_2000_is_allowed(self):
        """Boundary: 2000 chars is permitted (no raise from length check)."""
        pcm = b"\x00\x00" * 100
        chunk = _make_wav_bytes(pcm, 24000)
        b64 = base64.b64encode(chunk).decode("ascii")
        ndjson = (_ndjson_line(b64) + "\n").encode("utf-8")

        client, _ = _make_client(ndjson)
        result = client.generate(TTSRequest(text="a" * 2000))
        assert isinstance(result, AudioResult)


# ===========================================================================
# 4.5 — exception wrapping (via _post override)
# ===========================================================================


class TestExceptionWrapping:
    """All urllib/socket exceptions -> TTSError subclass; parse errors wrapped."""

    def test_http_error_wrapped(self):
        url = "https://api.inworld.ai/tts/v1/voice:stream"
        err = urllib.error.HTTPError(
            url, 500, "Internal", email.message.Message(), io.BytesIO(b"server boom")
        )
        client = _make_raising_client(err)
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="hi"))

    def test_url_error_wrapped(self):
        err = urllib.error.URLError("name resolution failed")
        client = _make_raising_client(err)
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="hi"))

    def test_socket_timeout_wrapped(self):
        err = TimeoutError("read timed out")
        client = _make_raising_client(err)
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="hi"))

    def test_ssl_error_wrapped(self):
        err = ssl.SSLError("certificate verify failed")
        client = _make_raising_client(err)
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="hi"))

    def test_os_error_wrapped(self):
        err = OSError("network is unreachable")
        client = _make_raising_client(err)
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="hi"))

    def test_corrupt_base64_wrapped_to_tts_error(self):
        """binascii.Error from corrupt base64 -> TTSError, not raw binascii."""
        # result.audioContent is not valid base64 -> binascii.Error inside loop.
        line = json.dumps(
            {"result": {"sampleRateHertz": 24000, "audioContent": "!!!not b64!!!"}}
        )
        ndjson = (line + "\n").encode("utf-8")
        client, _ = _make_client(ndjson)
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="hi"))


# ===========================================================================
# 4.5b — _wrap_urllib_error PURE helper (no urllib monkey-patch)
# ===========================================================================


class TestUrllibWrapHelper:
    """Pure helper _wrap_urllib_error maps each exception to the right subclass."""

    def test_http_error_maps_to_inworld_api_error(self):
        from tts_lab.infrastructure.inworld_client import (
            InworldAPIError,
            _wrap_urllib_error,
        )

        url = "https://api.inworld.ai/tts/v1/voice:stream"
        err = urllib.error.HTTPError(
            url, 503, "Unavailable", email.message.Message(), io.BytesIO(b"down")
        )
        wrapped = _wrap_urllib_error(err)
        assert isinstance(wrapped, InworldAPIError)
        assert isinstance(wrapped, TTSError)
        assert wrapped.status == 503

    def test_url_error_maps_to_inworld_connection_error(self):
        from tts_lab.infrastructure.inworld_client import (
            InworldConnectionError,
            _wrap_urllib_error,
        )

        wrapped = _wrap_urllib_error(urllib.error.URLError("dns"))
        assert isinstance(wrapped, InworldConnectionError)
        assert isinstance(wrapped, TTSError)

    def test_socket_timeout_maps_to_inworld_connection_error(self):
        from tts_lab.infrastructure.inworld_client import (
            InworldConnectionError,
            _wrap_urllib_error,
        )

        wrapped = _wrap_urllib_error(TimeoutError("timed out"))
        assert isinstance(wrapped, InworldConnectionError)

    def test_ssl_error_maps_to_inworld_connection_error(self):
        from tts_lab.infrastructure.inworld_client import (
            InworldConnectionError,
            _wrap_urllib_error,
        )

        wrapped = _wrap_urllib_error(ssl.SSLError("cert"))
        assert isinstance(wrapped, InworldConnectionError)

    def test_os_error_maps_to_inworld_connection_error(self):
        from tts_lab.infrastructure.inworld_client import (
            InworldConnectionError,
            _wrap_urllib_error,
        )

        wrapped = _wrap_urllib_error(OSError("unreachable"))
        assert isinstance(wrapped, InworldConnectionError)

    def test_unknown_exception_wrapped_as_connection_error(self):
        """An unexpected exception type is still wrapped (defensive)."""
        from tts_lab.infrastructure.inworld_client import (
            _wrap_urllib_error,
        )

        wrapped = _wrap_urllib_error(RuntimeError("unexpected"))
        assert isinstance(wrapped, TTSError)


# ===========================================================================
# 4.6 — sanitization
# ===========================================================================


class TestSanitization:
    """HTTP non-2xx body with key + Authorization: Basic -> sanitized TTSError."""

    def test_no_key_no_basic_no_body_in_error_message(self):
        """Error message contains none of {api_key, 'Basic', request body}."""
        fake_key = "U0VDUkVULWZha2Uta2V5LWlkOmZha2Utc2VjcmV0"  # base64-shaped
        # The "request body" the leaky server echoes back IS the text we sent.
        request_text = "secret-request-body-marker"
        # Body contains the key, a Basic header, and the echoed request text.
        leaky_body = (
            f"error: key={fake_key} Authorization: Basic {fake_key} "
            f"req={request_text}"
        ).encode()
        url = "https://api.inworld.ai/tts/v1/voice:stream"
        err = urllib.error.HTTPError(
            url, 500, "Internal", email.message.Message(), io.BytesIO(leaky_body)
        )

        client = _make_raising_client(err, api_key=fake_key)
        with pytest.raises(TTSError) as excinfo:
            client.generate(TTSRequest(text=request_text))

        msg = str(excinfo.value)
        assert fake_key not in msg
        assert "Basic" not in msg
        assert request_text not in msg

    def test_body_truncated_to_at_most_512_chars(self):
        """Sanitized body in the error message is <= 512 chars."""
        huge_body = ("X" * 5000).encode("utf-8")
        url = "https://api.inworld.ai/tts/v1/voice:stream"
        err = urllib.error.HTTPError(
            url, 500, "Internal", email.message.Message(), io.BytesIO(huge_body)
        )
        client = _make_raising_client(err, api_key="fake")
        with pytest.raises(TTSError) as excinfo:
            client.generate(TTSRequest(text="hi"))

        msg = str(excinfo.value)
        # The truncated body chunk itself should be <= 512 chars.
        # Find the longest run of 'X' in the message (the body excerpt).
        import re
        x_runs = re.findall(r"X+", msg)
        longest = max((len(r) for r in x_runs), default=0)
        assert longest <= 512


# ===========================================================================
# 4.7 — clone refusal, no-op CM, duration approximate
# ===========================================================================


class TestCloneRefusal:
    """clone_voice raises UnsupportedOperationError on Inworld."""

    def test_clone_voice_raises_unsupported(self):
        from tts_lab.infrastructure import inworld_client

        config = InworldConfig(api_key="fake")
        client = inworld_client.InworldTTSClient(config)
        profile = VoiceProfile(
            name="x", reference_audio_path="/no.wav", reference_text="hi"
        )
        with pytest.raises(UnsupportedOperationError) as excinfo:
            client.clone_voice(profile, "hello")
        assert excinfo.value.operation == "clone_voice"
        assert excinfo.value.provider == "inworld"


class TestNoOpContextManager:
    """InworldTTSClient is a no-op context manager (no resources to manage)."""

    def test_enter_returns_self(self):
        from tts_lab.infrastructure import inworld_client

        config = InworldConfig(api_key="fake")
        client = inworld_client.InworldTTSClient(config)
        with client as cm:
            assert cm is client

    def test_exit_returns_none(self):
        from tts_lab.infrastructure import inworld_client

        config = InworldConfig(api_key="fake")
        client = inworld_client.InworldTTSClient(config)
        # __exit__ is a no-op returning None; ensure it runs without error.
        client.__exit__(None, None, None)


class TestDurationApproximate:
    """LINEAR16 duration ~ len(pcm)/sample_rate; MP3 == 0.0."""

    def test_linear16_duration_approximate(self):
        sample_rate = 24000
        # 0.5s of PCM int16 samples.
        pcm = b"\x00\x00" * (sample_rate // 2)
        chunk = _make_wav_bytes(pcm, sample_rate)
        b64 = base64.b64encode(chunk).decode("ascii")
        ndjson = (_ndjson_line(b64, sample_rate=sample_rate) + "\n").encode("utf-8")

        client, _ = _make_client(ndjson)
        result = client.generate(TTSRequest(text="hi"))
        # Allow generous tolerance: N concatenated WAV headers inflate bytes.
        assert result.duration_seconds == pytest.approx(0.5, abs=0.05)

    def test_mp3_duration_is_zero(self):
        """MP3 audio encoding -> duration 0.0 (no parser)."""
        # MP3 path: raw bytes are not WAV; just feed arbitrary bytes.
        mp3_like = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" + b"\x00" * 200
        b64 = base64.b64encode(mp3_like).decode("ascii")
        line = json.dumps(
            {"result": {"sampleRateHertz": 24000, "audioContent": b64}}
        )
        ndjson = (line + "\n").encode("utf-8")

        client, _ = _make_client(ndjson, audio_encoding="MP3")
        result = client.generate(TTSRequest(text="hi"))
        assert result.duration_seconds == pytest.approx(0.0)
