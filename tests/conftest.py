"""Shared pytest fixtures for TTS Lab tests."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for audio output."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_audio_data():
    """Provide sample audio data for testing (1 second of silence at 24kHz)."""
    import io

    import numpy as np
    import soundfile as sf

    # Generate 1 second of silence at 24kHz
    sample_rate = 24000
    duration = 1.0
    samples = int(sample_rate * duration)
    silence = np.zeros(samples, dtype=np.float32)

    buffer = io.BytesIO()
    sf.write(buffer, silence, sample_rate, format="WAV")
    return buffer.getvalue()
