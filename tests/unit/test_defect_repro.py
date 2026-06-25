"""Phase-4 regression tests for the three fixed defects in
``InworldTTSClient`` (change ``inworld-tts-provider``).

Phase 1 used these tests as REPROS: a PASSING test meant the defect was
CONFIRMED (wrong exception type / missing kwarg observed). Phase 4 FLIPS each
test into a regression: a PASSING test now means the fix holds (correct
TTSError subclass / finite timeout observed). Run:

    uv run pytest tests/unit/test_defect_repro.py -v
"""

from __future__ import annotations

import io
import struct
import urllib.request
from typing import Any

import pytest

from tts_lab.domain.entities import TTSRequest
from tts_lab.domain.exceptions import TTSError
from tts_lab.infrastructure.config import InworldConfig
from tts_lab.infrastructure.inworld_client import (
    InworldTTSClient,
    strip_intermediate_wav_headers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(overrides: dict[str, Any] | None = None) -> InworldTTSClient:
    """Build a client with a valid-ish LINEAR16 config (no network used)."""
    cfg = InworldConfig(
        api_key="dGVzdDp0ZXN0",  # base64("test:test")
        base_url="https://example.invalid",
        default_voice_id="Sarah",
        audio_encoding="LINEAR16",
    )
    return InworldTTSClient(cfg)


# ===========================================================================
# DEFECT 1 — urlopen called with NO timeout kwarg (hang risk + dead path)
# ===========================================================================


def test_defect1_urlopen_receives_no_timeout_kwarg():
    """Regression: call ``generate`` and capture the kwargs passed to ``urlopen``.

    Originally the defect was CONFIRMED (no ``timeout`` kwarg). Now FIXED: the
    real ``_post`` threads ``config.http_timeout_seconds`` (a finite, positive
    float) into ``urllib.request.urlopen``.

    This test exercises the *real* ``_post`` (not a hand-rolled mirror) by
    monkey-patching ``urllib.request.urlopen`` with a recorder, then calling
    ``generate``. The recorder returns a canned NDJSON body so the rest of the
    pipeline runs without network. We assert that ``timeout`` is present and
    is a finite, positive number (not None, not missing).
    """
    captured: dict[str, Any] = {}

    client = _make_client()

    # Recorder: remembers the kwargs, returns a dummy context manager.
    class _DummyCtx:
        def __enter__(self):
            return io.BytesIO(b'{"result":{"audioContent":""}}\n')

        def __exit__(self, *exc):
            return False

    def recording_urlopen(req, **kwargs):
        captured["kwargs"] = dict(kwargs)
        return _DummyCtx()

    # Patch urlopen BEFORE calling generate so the real _post hits the recorder.
    monkeypatch_urlopen = pytest.MonkeyPatch()
    monkeypatch_urlopen.setattr(
        urllib.request, "urlopen", recording_urlopen
    )
    try:
        # We expect generate to raise TTSError (empty audio), but we only care
        # about the captured kwargs at the urlopen boundary.
        with pytest.raises(TTSError):
            client.generate(TTSRequest(text="x"))
    finally:
        monkeypatch_urlopen.undo()

    kwargs = captured.get("kwargs", {})
    timeout = kwargs.get("timeout", "__MISSING__")

    # FIXED: timeout must be present AND a finite, positive number.
    assert timeout != "__MISSING__", "timeout kwarg missing from urlopen call"
    assert timeout is not None, "timeout is None (block-forever default)"
    assert isinstance(timeout, (int, float)), (
        f"timeout must be numeric, got {type(timeout).__name__}"
    )
    assert timeout > 0, f"timeout must be positive, got {timeout!r}"


# ===========================================================================
# DEFECT 2 — non-string audioContent escapes as TypeError (not TTSError)
# ===========================================================================


@pytest.mark.parametrize(
    "audio_content_value",
    [
        12345,            # truthy int  -> not 12345 == False -> reaches b64decode
        [1, 2],           # non-empty list
        {"k": "v"},       # dict
        True,             # bool (truthy)
    ],
    ids=["int", "nonempty_list", "dict", "bool_true"],
)
def test_defect2_nonstring_audiocontent_raises_typeerror_not_ttserror(audio_content_value):
    """Regression: a non-string ``audioContent`` MUST raise an
    ``InworldParseError`` (a :class:`TTSError` subclass), NOT a raw
    ``TypeError``. Originally the defect was CONFIRMED — a truthy non-str
    slipped past ``not audio_b64`` and ``base64.b64decode`` raised a raw
    ``TypeError`` that escaped the ``_post_safe`` boundary. Now FIXED by an
    ``isinstance(audio_b64, str)`` narrowing at source.
    """
    import json

    line = json.dumps({"result": {"audioContent": audio_content_value}})
    ndjson = (line + "\n").encode("utf-8")

    client = _make_client()
    # Intentional monkey-patch of a private method to inject canned NDJSON.
    client._post = lambda payload: io.BytesIO(ndjson)  # type: ignore[method-assign]

    with pytest.raises(TTSError) as excinfo:
        client.generate(TTSRequest(text="x"))

    raised = excinfo.value
    # FIXED: a TTSError subclass is raised (never a raw TypeError).
    assert isinstance(raised, TTSError), (
        f"Expected TTSError subclass, got {type(raised).__name__}: {raised}"
    )
    assert not isinstance(raised, TypeError), (
        f"Expected NON-TypeError TTSError, but raw TypeError escaped: "
        f"{type(raised).__name__}"
    )


def test_defect2_empty_list_audiocontent_is_skipped_not_typeerror():
    """Regression: ``[]`` is a non-string -> MUST raise a ``TTSError`` (not a
    raw ``TypeError``, and not silently skipped). Originally ``not []`` was
    truthy-falsiness shortcut, but the narrowing fix treats ANY non-string as
    a parse error — ``[]`` included. The raised error must be a TTSError
    subclass (InworldParseError).
    """
    import json

    line = json.dumps({"result": {"audioContent": []}})
    ndjson = (line + "\n").encode("utf-8")

    client = _make_client()
    # Intentional monkey-patch of a private method to inject canned NDJSON.
    client._post = lambda payload: io.BytesIO(ndjson)  # type: ignore[method-assign]

    with pytest.raises(TTSError) as excinfo:
        client.generate(TTSRequest(text="x"))
    # A non-string audioContent -> InworldParseError (a TTSError subclass).
    assert isinstance(excinfo.value, TTSError)
    assert not isinstance(excinfo.value, TypeError)


# ===========================================================================
# DEFECT 3 — truncated WAV fmt body raises struct.error (escape from generate)
# ===========================================================================


def _build_wav_with_truncated_fmt(declared_fmt_size: int, actual_body_len: int) -> bytes:
    """Build a malformed WAV blob that triggers ``struct.error`` in
    ``_parse_riff_chunk``.

    The ``fmt `` chunk HEADER declares ``declared_fmt_size`` bytes (the loop
    trusts this), but only ``actual_body_len`` bytes of fmt body actually
    exist before the blob ends. When ``declared_fmt_size >= 16`` but
    ``actual_body_len < 16``, the slice ``chunk[body_start : body_start + 16]``
    is shorter than 16 bytes and ``struct.unpack('<HHIIHH', ...)`` raises
    ``struct.error: unpack requires a buffer of 16 bytes``.

    NOTE: a *consistent* truncation (declared == actual, both < 16) does NOT
    trigger the bug — the unpack then slices into the following chunk and
    succeeds with garbage values, hitting the ``sample_rate == 0`` guard
    instead. The defect requires the header to LIE about its size.
    """
    if declared_fmt_size < 0 or actual_body_len < 0:
        raise ValueError("sizes must be >= 0")
    fmt_body = b"\x00" * actual_body_len
    # RIFF size only accounts for bytes actually present.
    riff_size = 4 + (8 + actual_body_len)
    return (
        b"RIFF"
        + struct.pack("<I", riff_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", declared_fmt_size)
        + fmt_body
        # Deliberately NO data chunk — blob ends here, short.
    )


def test_defect3a_helper_raises_struct_error_on_truncated_fmt():
    """Regression A: ``strip_intermediate_wav_headers`` on a single WAV chunk
    whose ``fmt `` body is 8 bytes (< 16) with a LYING header (declared=16)
    MUST raise ``InworldParseError`` (a TTSError), NOT a raw ``struct.error``.

    Originally the defect was CONFIRMED — ``struct.error`` escaped the helper
    because the length check used the DECLARED chunk_size (which the lying
    header had set to 16) instead of the ACTUAL buffer length. Now FIXED by
    a pre-check against the actual bytes available.
    """
    truncated = _build_wav_with_truncated_fmt(declared_fmt_size=16, actual_body_len=8)
    with pytest.raises(TTSError) as excinfo:
        strip_intermediate_wav_headers([truncated])
    raised = excinfo.value
    # FIXED: an InworldParseError (TTSError subclass) is raised, never a raw
    # struct.error.
    assert isinstance(raised, TTSError), (
        f"Expected TTSError subclass, got {type(raised).__name__}: {raised}"
    )
    assert not isinstance(raised, struct.error), (
        f"Expected NON-struct.error, but raw struct.error escaped: "
        f"{type(raised).__name__}"
    )


def test_defect3b_struct_error_escapes_generate_outside_post_safe_boundary():
    """Regression B: ``generate()`` calls ``_read_ndjson`` OUTSIDE the
    ``_post_safe`` try/except. A truncated-fmt WAV MUST surface as
    ``InworldParseError`` (TTSError), NOT as a raw ``struct.error``.

    Originally the defect was CONFIRMED — the struct.error escaped
    ``generate()`` because the parser boundary was unguarded. Now FIXED by
    (a) the in-parser length pre-check and (b) a defensive outer wrap at the
    ``_read_ndjson`` call site that converts any non-TTSError into
    ``InworldParseError``.
    """
    import base64

    truncated_wav = _build_wav_with_truncated_fmt(declared_fmt_size=16, actual_body_len=8)
    audio_b64 = base64.b64encode(truncated_wav).decode("ascii")
    line = '{"result":{"audioContent":"' + audio_b64 + '"}}'
    ndjson = (line + "\n").encode("utf-8")

    client = _make_client()
    # Intentional monkey-patch of a private method to inject canned NDJSON.
    client._post = lambda payload: io.BytesIO(ndjson)  # type: ignore[method-assign]

    with pytest.raises(TTSError) as excinfo:
        client.generate(TTSRequest(text="x"))
    raised = excinfo.value
    # FIXED: a TTSError subclass (InworldParseError) escapes generate(), never
    # a raw struct.error.
    assert isinstance(raised, TTSError), (
        f"Expected TTSError subclass, got {type(raised).__name__}: {raised}"
    )
    assert not isinstance(raised, struct.error), (
        f"Expected NON-struct.error TTSError, but raw struct.error escaped: "
        f"{type(raised).__name__}"
    )
