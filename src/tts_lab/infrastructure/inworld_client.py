"""Infrastructure - Inworld Cloud TTS Client.

Implements :class:`tts_lab.domain.protocols.TTSClient` against the Inworld
``/tts/v1/voice:stream`` NDJSON streaming endpoint. Pure stdlib only
(``urllib.request``, ``json``, ``base64``, ``ssl``, ``socket``, ``binascii``,
``re``) — no new direct dependencies.

Design notes
------------
* Domain stays pure: this module owns the Inworld-specific exception
  subclasses (each subclassing the domain :class:`TTSError`) and the
  concrete :class:`UnsupportedOperationError` is raised for ``clone_voice``.
* An HTTP injection seam (``_post``) lets tests feed canned NDJSON bytes
  without monkey-patching ``urllib.request.urlopen``.
* A pure module-level helper (:func:`_wrap_urllib_error`) maps the exhaustive
  urllib/socket exception set to :class:`TTSError` subclasses; it is
  unit-tested directly.
* Multi-chunk LINEAR16 responses concatenate N full WAV headers, which
  :func:`strip_intermediate_wav_headers` collapses into one RIFF wrapper so
  ``soundfile.read`` returns the full duration rather than truncating to the
  first chunk.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import re
import socket
import ssl
import struct
import urllib.error
import urllib.request
from types import TracebackType
from typing import Any

from tts_lab.domain.entities import AudioResult, TTSRequest, VoiceProfile
from tts_lab.domain.exceptions import TTSError, UnsupportedOperationError
from tts_lab.infrastructure.config import InworldConfig

logger = logging.getLogger(__name__)

#: Maximum text length accepted before issuing any HTTP request.
MAX_TEXT_LENGTH: int = 2000

#: Inworld preset voices are sent as JSON; cap error-body excerpts at this size.
_MAX_BODY_EXCERPT: int = 512

#: The default sample rate requested from Inworld (Hz).
_DEFAULT_SAMPLE_RATE_HERTZ: int = 24000

#: Minimum byte length of a PCM ``fmt `` chunk body (``<HHIIHH`` == 16).
_FMT_MIN_BYTES: int = struct.calcsize("<HHIIHH")


# ---------------------------------------------------------------------------
# Infrastructure-only exception subclasses (each subclasses domain TTSError).
# ---------------------------------------------------------------------------


class InworldAPIError(TTSError):
    """Non-2xx HTTP response from Inworld.

    Attributes:
        status: HTTP status code.
    """

    status: int

    def __init__(self, message: str, *, status: int) -> None:
        super().__init__(message)
        self.status = status


class InworldConnectionError(TTSError):
    """Transport-level failure reaching Inworld (DNS, TLS, timeout, etc.)."""

    pass


class InworldParseError(TTSError):
    """Malformed NDJSON or corrupt base64 audioContent from Inworld."""

    pass


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


# Matches a base64-shaped token (Inworld keys are base64 keyId:keySecret).
_B64_TOKEN_RE = re.compile(rb"[A-Za-z0-9+/=]{16,}")
# Matches an Authorization: Basic <value> header line/value.
_AUTH_BASIC_RE = re.compile(rb"Authorization:\s*Basic\s+[A-Za-z0-9+/=]+", re.I)
# Matches the bare word "Basic" (defensive; redact even outside header form).
_BASIC_LITERAL_RE = re.compile(rb"Basic")


def _ascii_only(payload: bytes) -> bytes:
    """Drop non-ASCII bytes so error messages stay printable/safe."""
    return payload.decode("ascii", errors="ignore").encode("ascii")


def sanitize_error_body(body: bytes, api_key: bytes) -> bytes:
    """Strip secrets from an HTTP error body and truncate it.

    Redacts any base64-shaped token matching the API key, the
    ``Authorization: Basic ...`` header value, and the literal word ``Basic``;
    drops non-ASCII bytes; truncates to at most :data:`_MAX_BODY_EXCERPT` bytes.

    Args:
        body: Raw HTTP error response body.
        api_key: The API key bytes to redact if present.

    Returns:
        Sanitized, ASCII-only, length-capped body bytes.
    """
    sanitized = body
    if api_key:
        sanitized = sanitized.replace(api_key, b"[REDACTED]")
    sanitized = _AUTH_BASIC_RE.sub(b"[REDACTED]", sanitized)
    sanitized = _BASIC_LITERAL_RE.sub(b"[REDACTED]", sanitized)
    # Catch any other base64-shaped tokens (rotated keys, etc.).
    sanitized = _B64_TOKEN_RE.sub(b"[REDACTED]", sanitized)
    sanitized = _ascii_only(sanitized)
    if len(sanitized) > _MAX_BODY_EXCERPT:
        sanitized = sanitized[:_MAX_BODY_EXCERPT]
    return sanitized


def _wrap_urllib_error(exc: BaseException) -> TTSError:
    """Map a urllib/socket exception to a :class:`TTSError` subclass.

    This is a PURE helper (no I/O) and is unit-tested directly so the
    default ``_post`` urllib branch does not depend on monkey-patching
    ``urllib.request.urlopen`` for coverage.

    Args:
        exc: The exception raised inside the urllib/socket call path.

    Returns:
        * :class:`InworldAPIError` for ``urllib.error.HTTPError`` (carries status).
        * :class:`InworldConnectionError` for ``URLError``, ``socket.timeout``,
          ``ssl.SSLError``, and generic ``OSError``.
        * :class:`InworldConnectionError` for any other unexpected exception
          (defensive — never let a raw non-``TTSError`` escape the client).
    """
    if isinstance(exc, urllib.error.HTTPError):
        return InworldAPIError(
            f"Inworld HTTP {exc.code}: {exc.reason}", status=exc.code
        )
    if isinstance(
        exc,
        (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError),
    ):
        return InworldConnectionError(f"Inworld connection failed: {exc}")
    # Defensive: unknown exception type -> still a TTSError, never leaks.
    return InworldConnectionError(f"Inworld connection failed: {exc!r}")


def _parse_riff_chunk(chunk: bytes) -> tuple[int, int, int, int]:
    """Parse the RIFF/WAVE header of ``chunk``.

    Returns ``(sample_rate, num_channels, bits_per_sample, data_offset)`` where
    ``data_offset`` is the byte index immediately after the ``data`` chunk
    header (i.e. the start of the PCM payload).
    """
    if chunk[0:4] != b"RIFF" or chunk[8:12] != b"WAVE":
        raise InworldParseError("LINEAR16 chunk is not a valid RIFF/WAVE blob")
    pos = 12
    sample_rate = num_channels = bits_per_sample = data_offset = 0
    while pos + 8 <= len(chunk):
        chunk_id = chunk[pos : pos + 4]
        chunk_size = struct.unpack("<I", chunk[pos + 4 : pos + 8])[0]
        body_start = pos + 8
        body_end = body_start + chunk_size
        if chunk_id == b"fmt ":
            # Length pre-check using ACTUAL buffer length (NOT declared
            # chunk_size). The bug triggers when the fmt header LIES:
            # declared chunk_size >= 16 but the buffer ends early so the slice
            # is shorter than 16 bytes. struct.unpack('<HHIIHH', ...) then
            # raises a raw struct.error that escapes the _post_safe boundary as
            # a non-TTSError. Verify the ACTUAL bytes available are >= 16.
            actual_available = len(chunk) - body_start
            if actual_available < _FMT_MIN_BYTES:
                raise InworldParseError(
                    f"truncated fmt chunk: declared {chunk_size} bytes but "
                    f"only {max(0, actual_available)} present"
                )
            # intentionally discarded; _build_wav hardcodes PCM
            (
                _audio_format,
                num_channels,
                sample_rate,
                _byte_rate,
                _block_align,
                bits_per_sample,
            ) = struct.unpack("<HHIIHH", chunk[body_start : body_start + 16])
        elif chunk_id == b"data":
            data_offset = body_start
            # We don't break: keep scanning in case fmt came after data
            # (non-standard but defensive). data_size = chunk_size.
        pos = body_end + (chunk_size & 1)  # word-align
    if sample_rate == 0 or data_offset == 0:
        raise InworldParseError("RIFF/WAVE chunk missing fmt or data payload")
    return sample_rate, num_channels, bits_per_sample, data_offset


def _build_wav(pcm: bytes, sample_rate: int, num_channels: int,
               bits_per_sample: int) -> bytes:
    """Wrap PCM bytes in a single RIFF/WAVE container."""
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    fmt_chunk = struct.pack(
        "<HHIIHH",
        1,  # PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    )
    riff_size = 4 + (8 + len(fmt_chunk)) + (8 + len(pcm))
    return (
        b"RIFF"
        + struct.pack("<I", riff_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt_chunk))
        + fmt_chunk
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )


def strip_intermediate_wav_headers(chunks: list[bytes]) -> tuple[bytes, int]:
    """Collapse N concatenated WAV chunks into a single RIFF/WAVE blob.

    Each LINEAR16 chunk from Inworld carries its own full WAV header. Naively
    concatenating N of them yields N RIFF blocks, and ``soundfile.read`` only
    reads the first — truncating playback to chunk 1. This helper parses the
    first chunk for sample-rate/format info, strips the RIFF wrappers from
    chunks 2..N, and rebuilds a single WAV container around the full PCM
    payload.

    Args:
        chunks: One or more complete WAV byte blobs.

    Returns:
        Tuple of ``(single_wav_bytes, sample_rate)``.

    Raises:
        InworldParseError: If the first chunk is not a valid RIFF/WAVE blob.
    """
    if not chunks:
        raise InworldParseError("strip_intermediate_wav_headers: empty chunks")
    sample_rate, num_channels, bits_per_sample, data_offset = _parse_riff_chunk(
        chunks[0]
    )
    # First chunk PCM = bytes after the data header to end of chunk.
    # (We do not strictly need the data chunk size; everything from the data
    # offset to the end of the blob is PCM in our hand-crafted test blobs and
    # in Inworld's single-data-chunk WAVs.)
    pcm_parts = [chunks[0][data_offset:]]
    for chunk in chunks[1:]:
        _sr, _nc, _bps, off = _parse_riff_chunk(chunk)
        pcm_parts.append(chunk[off:])
    pcm = b"".join(pcm_parts)
    return _build_wav(pcm, sample_rate, num_channels, bits_per_sample), sample_rate


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class InworldTTSClient:
    """Infrastructure adapter for the Inworld cloud TTS provider.

    Implements :class:`tts_lab.domain.protocols.TTSClient` over the Inworld
    NDJSON streaming endpoint. Voice cloning is unsupported and raises a typed
    :class:`UnsupportedOperationError`. The context-manager protocol is a
    no-op (no resources to manage) so the CLI's ``with`` block works unchanged.
    """

    def __init__(self, config: InworldConfig) -> None:
        """Initialize with an :class:`InworldConfig`.

        Args:
            config: Inworld connection + voice configuration.
        """
        self._config = config

    # -- TTSClient protocol -----------------------------------------------

    def generate(self, request: TTSRequest) -> AudioResult:
        """Generate speech via Inworld's NDJSON streaming endpoint.

        Args:
            request: TTS request (text, language, optional speaker).

        Returns:
            AudioResult with synthesized audio.

        Raises:
            TTSError: On text-too-long, HTTP non-2xx, transport failure,
                malformed NDJSON, or corrupt base64 audioContent.
        """
        text = request.text
        if len(text) > MAX_TEXT_LENGTH:
            raise TTSError(
                f"Inworld text length {len(text)} exceeds {MAX_TEXT_LENGTH} chars"
            )

        voice_id = request.speaker or self._config.default_voice_id
        payload: dict[str, Any] = {
            "text": text,
            "voiceId": voice_id,
            "modelId": "inworld-tts-1",
            "audioConfig": {
                "audioEncoding": self._config.audio_encoding,
                "sampleRateHertz": _DEFAULT_SAMPLE_RATE_HERTZ,
            },
        }

        response = self._post_safe(payload)
        # Defensive outer wrap: _read_ndjson runs OUTSIDE the _post_safe try
        # boundary. Even with the in-parser narrowing (type + length checks),
        # an unexpected exception class from base64/struct/json internals
        # could escape as a non-TTSError, violating the contract that no
        # non-TTSError ever escapes the client. This is the narrowest correct
        # fix: catch any non-TTSError, wrap it as InworldParseError, and let
        # already-correct TTSError subclasses propagate unchanged.
        try:
            audio_bytes, sample_rate = self._read_ndjson(response, payload)
        except TTSError:
            raise
        except Exception as e:
            raise InworldParseError(
                f"failed to parse Inworld response: {e}"
            ) from e

        return AudioResult(
            audio_data=audio_bytes,
            sample_rate=sample_rate,
            duration_seconds=self._approx_duration(audio_bytes, sample_rate),
        )

    def clone_voice(self, profile: VoiceProfile, text: str) -> AudioResult:
        """Refuse voice cloning — Inworld is a preset-voice-only provider.

        Raises:
            UnsupportedOperationError: Always.
        """
        raise UnsupportedOperationError(
            "Inworld does not support voice cloning; use the Qwen provider.",
            operation="clone_voice",
            provider="inworld",
        )

    # -- Context manager (no-op) ------------------------------------------

    def __enter__(self) -> InworldTTSClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    # -- HTTP seam --------------------------------------------------------

    def _post_safe(self, payload: dict[str, Any]) -> io.BytesIO:
        """Call :meth:`_post` and wrap any exception into a ``TTSError``.

        Centralizes the exhaustive urllib/socket/HTTP wrapping so it applies
        whether ``_post`` is the default urllib implementation or a test
        override. ``HTTPError`` is handled specially: its body is read and
        sanitized so no API key / Authorization header / request body leaks.
        """
        try:
            return self._post(payload)
        except urllib.error.HTTPError as e:
            raw_body = b""
            try:
                raw_body = e.read()
            except Exception:  # body read is best-effort
                raw_body = b""
            # Log the raw body (server-side detail) BEFORE sanitization strips
            # secrets. Honors "log detailed context server-side": the raw body
            # never reaches the user-facing exception message; only the
            # sanitized excerpt does.
            logger.debug(
                "Inworld HTTP %d raw body (pre-sanitization): %r",
                e.code,
                raw_body,
            )
            sanitized = sanitize_error_body(raw_body, self._config.api_key.encode())
            # Also redact the raw request payload substring (server may echo it).
            payload_bytes = json.dumps(payload).encode("utf-8")
            if payload_bytes:
                sanitized = sanitized.replace(payload_bytes, b"[REDACTED]")
                # Redact the inner text/value fragments too (defensive).
                for field in ("text", "voiceId"):
                    val = payload.get(field)
                    if isinstance(val, str) and val:
                        sanitized = sanitized.replace(
                            val.encode("utf-8", "ignore"), b"[REDACTED]"
                        )
            raise InworldAPIError(
                f"Inworld HTTP {e.code}: {sanitized.decode('ascii', 'ignore')}",
                status=e.code,
            ) from e
        except TTSError:
            # Already a TTSError subclass — let it through unchanged.
            raise
        except Exception as e:
            raise _wrap_urllib_error(e) from e

    def _post(self, payload: dict[str, Any]) -> io.BytesIO:
        """POST ``payload`` to Inworld and return the raw response body.

        Default implementation uses stdlib :mod:`urllib.request` with HTTP
        Basic auth. Tests override this method to feed canned NDJSON bytes.

        Raises:
            urllib.error.HTTPError: On non-2xx responses (wrapped by
                :meth:`_post_safe` into :class:`InworldAPIError`).
            Exception: Any other urllib/socket failure (wrapped by
                :meth:`_post_safe` via :func:`_wrap_urllib_error`).
        """
        url = f"{self._config.base_url}/tts/v1/voice:stream"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
        )
        req.add_header("Authorization", f"Basic {self._config.api_key}")
        req.add_header("Content-Type", "application/json")
        # NOTE: exceptions are allowed to bubble; :meth:`_post_safe` wraps them.
        # A finite timeout keeps Inworld from hanging us forever: a slow/dead
        # endpoint surfaces as socket.timeout -> _wrap_urllib_error ->
        # InworldConnectionError, all inside the _post_safe boundary.
        with urllib.request.urlopen(
            req, timeout=self._config.http_timeout_seconds
        ) as resp:  # provider URL from config
            return io.BytesIO(resp.read())

    # -- NDJSON parsing ---------------------------------------------------

    def _read_ndjson(
        self, response: io.BytesIO, payload: dict[str, Any]
    ) -> tuple[bytes, int]:
        """Parse the NDJSON response into ``(audio_bytes, sample_rate)``.

        Handles all seven edge cases enumerated in the spec: BOM strip,
        ``\\r\\n`` tolerance, error objects, non-JSON lines, empty/missing
        audioContent (skipped), and truncated/partial final lines.

        Args:
            response: BytesIO of the raw response body.
            payload: The request payload (used for sanitization context only).

        Returns:
            Tuple of ``(audio_bytes, sample_rate)``.

        Raises:
            TTSError subclass: On any parse/network-mapped failure.
        """
        raw = response.read()
        text = raw.decode("utf-8-sig", errors="replace")  # strips BOM if present
        # Normalize line endings and split.
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        encoding = self._config.audio_encoding
        sample_rate = _DEFAULT_SAMPLE_RATE_HERTZ
        chunks: list[bytes] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                # Distinguish a truncated final line (looks like it started as
                # JSON — begins with '{' or '[') from a genuinely non-JSON line.
                looks_started = stripped[:1] in ("{", "[")
                if looks_started:
                    # Truncated/partial: end-of-stream after last valid line.
                    # Surface this real-world recovery path at WARNING so
                    # operators can spot truncation without raising.
                    logger.warning(
                        "NDJSON stream truncated; partial audio returned"
                    )
                    break
                # Genuinely malformed -> never silently skip.
                raise InworldParseError("malformed NDJSON line") from None
            except Exception as e:
                raise InworldParseError(f"malformed NDJSON line: {e}") from e

            if not isinstance(obj, dict):
                raise InworldParseError("malformed NDJSON line")

            if "error" in obj:
                err_obj = obj["error"]
                msg = json.dumps(err_obj).encode("utf-8")
                sanitized = sanitize_error_body(
                    msg, self._config.api_key.encode()
                )
                # Also redact the request payload body substring.
                payload_bytes = json.dumps(payload).encode("utf-8")
                err_msg = sanitized.decode("ascii", "ignore")
                if payload_bytes and payload_bytes.decode("utf-8", "ignore") in err_msg:
                    err_msg = err_msg.replace(
                        payload_bytes.decode("utf-8", "ignore"), "[REDACTED]"
                    )
                raise TTSError(f"Inworld error response: {err_msg}")

            result = obj.get("result")
            if not isinstance(result, dict):
                # No result object at all -> treat as malformed.
                raise InworldParseError("malformed NDJSON line")

            sr = result.get("sampleRateHertz")
            if isinstance(sr, int) and not isinstance(sr, bool):
                sample_rate = sr

            audio_b64 = result.get("audioContent")
            # Narrow the type at source BEFORE b64decode. ``not audio_b64`` only
            # filtered falsy values (None, "", [], 0, False); a *truthy non-str*
            # (e.g. ``12345``, ``{"k":"v"}``, ``[1,2]``) slipped through and
            # base64.b64decode raised a raw ``TypeError`` that escaped the
            # _post_safe boundary as a non-TTSError. ``isinstance(..., str)``
            # is the correct check: the contract guarantees audioContent is a
            # base64 STRING; anything else is a parse error.
            if audio_b64 is None or audio_b64 == "":
                # Missing/empty audioContent -> skip silently.
                continue
            if not isinstance(audio_b64, str):
                raise InworldParseError(
                    "audioContent must be a base64 string"
                )

            try:
                chunk = base64.b64decode(audio_b64, validate=True)
            except (binascii.Error, ValueError) as e:
                raise InworldParseError("corrupt audioContent base64") from e

            chunks.append(chunk)

        if not chunks:
            raise TTSError("Inworld empty/truncated response")

        if encoding == "LINEAR16":
            audio_bytes, sample_rate = strip_intermediate_wav_headers(chunks)
        else:
            # MP3 (or any non-LINEAR16): join raw bytes, duration unknown.
            audio_bytes = b"".join(chunks)

        return audio_bytes, sample_rate

    def _approx_duration(self, audio_bytes: bytes, sample_rate: int) -> float:
        """Approximate duration: LINEAR16 PCM bytes/sr; MP3 (non-WAV) = 0.0."""
        if self._config.audio_encoding != "LINEAR16":
            return 0.0
        if sample_rate <= 0:
            return 0.0
        # The single RIFF wrapper built by strip_intermediate_wav_headers has
        # a 44-byte header; the rest is 16-bit (2 bytes) mono PCM.
        try:
            _sr, _nc, _bps, data_offset = _parse_riff_chunk(audio_bytes)
            pcm_len = len(audio_bytes) - data_offset
        except InworldParseError:
            pcm_len = max(0, len(audio_bytes) - 44)
        return pcm_len / (sample_rate * 2)  # 16-bit mono = 2 bytes/sample


__all__ = [
    "InworldAPIError",
    "InworldConnectionError",
    "InworldParseError",
    "InworldTTSClient",
    "sanitize_error_body",
    "strip_intermediate_wav_headers",
]
