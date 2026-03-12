"""Unit tests for reference preparation helpers."""

import numpy as np
import pytest

from tts_lab.infrastructure.reference_preparation import (
    build_reference_segments,
    compute_segment_metrics,
    pick_best_segment,
    segment_audio,
)


class TestComputeSegmentMetrics:
    """Tests for basic audio quality metrics."""

    def test_compute_segment_metrics_rejects_empty_audio(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            compute_segment_metrics(np.array([], dtype=np.float32), 24000)

    def test_compute_segment_metrics_rejects_invalid_sample_rate(self):
        audio = np.ones(24000, dtype=np.float32) * 0.1
        with pytest.raises(ValueError, match="must be positive"):
            compute_segment_metrics(audio, 0)

    def test_compute_segment_metrics_detects_silence(self):
        audio = np.zeros(24000, dtype=np.float32)
        metrics = compute_segment_metrics(audio, 24000)

        assert metrics.duration_seconds == pytest.approx(1.0)
        assert metrics.speech_ratio == pytest.approx(0.0)
        assert metrics.silence_ratio == pytest.approx(1.0)
        assert metrics.clipping_ratio == pytest.approx(0.0)

    def test_compute_segment_metrics_detects_clipping(self):
        audio = np.ones(24000, dtype=np.float32)
        metrics = compute_segment_metrics(audio, 24000)

        assert metrics.clipping_ratio == pytest.approx(1.0)
        assert metrics.speech_ratio == pytest.approx(1.0)


class TestSegmentAudio:
    """Tests for fixed-window segmentation."""

    def test_segment_audio_returns_empty_when_audio_too_short(self):
        audio = np.ones(24000 * 4, dtype=np.float32) * 0.1
        segments = segment_audio(audio, 24000, segment_seconds=12.0, min_segment_seconds=8.0)
        assert segments == []

    def test_segment_audio_splits_into_expected_windows(self):
        audio = np.ones(24000 * 24, dtype=np.float32) * 0.1
        segments = segment_audio(
            audio,
            24000,
            segment_seconds=12.0,
            step_seconds=12.0,
            min_segment_seconds=8.0,
        )

        assert len(segments) == 2
        assert segments[0][0] == pytest.approx(0.0)
        assert segments[1][0] == pytest.approx(12.0)
        assert len(segments[0][1]) == 24000 * 12

    def test_segment_audio_rejects_invalid_parameters(self):
        audio = np.ones(24000 * 12, dtype=np.float32) * 0.1
        with pytest.raises(ValueError, match="segment_seconds"):
            segment_audio(audio, 24000, segment_seconds=0)
        with pytest.raises(ValueError, match="step_seconds"):
            segment_audio(audio, 24000, step_seconds=0)
        with pytest.raises(ValueError, match="max_segments"):
            segment_audio(audio, 24000, max_segments=0)


class TestReferenceSegments:
    """Tests for scored reference segment selection."""

    def test_build_reference_segments_creates_scored_segments(self):
        first = np.ones(24000 * 12, dtype=np.float32) * 0.05
        second = np.zeros(24000 * 12, dtype=np.float32)
        audio = np.concatenate([first, second]).astype(np.float32)

        segments = build_reference_segments(
            audio,
            24000,
            segment_seconds=12.0,
            step_seconds=12.0,
            min_segment_seconds=8.0,
        )

        assert len(segments) == 2
        assert segments[0].index == 1
        assert segments[0].metrics.score > segments[1].metrics.score

    def test_pick_best_segment_returns_highest_score(self):
        first = np.ones(24000 * 12, dtype=np.float32) * 0.05
        second = np.zeros(24000 * 12, dtype=np.float32)
        audio = np.concatenate([first, second]).astype(np.float32)

        segments = build_reference_segments(
            audio,
            24000,
            segment_seconds=12.0,
            step_seconds=12.0,
            min_segment_seconds=8.0,
        )
        best = pick_best_segment(segments)

        assert best is not None
        assert best.index == 1

    def test_pick_best_segment_returns_none_for_empty_list(self):
        assert pick_best_segment([]) is None
