"""Reference preparation helpers for voice cloning.

This module provides small, deterministic helpers for preparing local
reference audio files before transcription and voice-cloning experiments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class SegmentMetrics:
    """Basic quality metrics for a reference segment."""

    duration_seconds: float
    speech_ratio: float
    silence_ratio: float
    clipping_ratio: float
    rms: float
    score: float


@dataclass(frozen=True)
class ReferenceSegment:
    """Prepared reference segment with metadata."""

    index: int
    start_seconds: float
    end_seconds: float
    metrics: SegmentMetrics

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-friendly mapping."""
        return {
            "index": self.index,
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "metrics": asdict(self.metrics),
        }


AudioArray = npt.NDArray[np.float32]


def _as_mono_float32(audio: npt.NDArray[np.float32] | npt.NDArray[np.float64]) -> AudioArray:
    """Normalize audio to mono float32."""
    mono = audio
    if audio.ndim == 2:
        mono = audio.mean(axis=1)
    return mono.astype(np.float32, copy=False)


def compute_segment_metrics(
    audio: npt.NDArray[np.float32] | npt.NDArray[np.float64],
    sample_rate: int,
    *,
    silence_threshold: float = 0.01,
    clipping_threshold: float = 0.98,
) -> SegmentMetrics:
    """Compute simple quality metrics for a segment.

    The goal is not studio-grade scoring; it is only to produce a consistent,
    explainable heuristic for short cloning references.
    """
    mono = _as_mono_float32(audio)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if mono.size == 0:
        raise ValueError("audio segment cannot be empty")

    abs_audio = np.abs(mono)
    duration_seconds = mono.size / sample_rate
    speech_ratio = float(np.mean(abs_audio > silence_threshold))
    silence_ratio = 1.0 - speech_ratio
    clipping_ratio = float(np.mean(abs_audio >= clipping_threshold))
    rms = float(np.sqrt(np.mean(np.square(mono))))

    duration_score = 1.0 if 8.0 <= duration_seconds <= 15.0 else 0.5
    score = max(
        0.0,
        (duration_score * 0.35)
        + (speech_ratio * 0.45)
        + (min(rms / 0.2, 1.0) * 0.20)
        - (clipping_ratio * 0.75),
    )

    return SegmentMetrics(
        duration_seconds=duration_seconds,
        speech_ratio=speech_ratio,
        silence_ratio=silence_ratio,
        clipping_ratio=clipping_ratio,
        rms=rms,
        score=score,
    )


def segment_audio(
    audio: npt.NDArray[np.float32] | npt.NDArray[np.float64],
    sample_rate: int,
    *,
    segment_seconds: float = 12.0,
    step_seconds: float | None = None,
    min_segment_seconds: float = 8.0,
    max_segments: int | None = None,
) -> list[tuple[float, AudioArray]]:
    """Slice audio into fixed windows suitable for cloning references."""
    mono = _as_mono_float32(audio)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if segment_seconds <= 0:
        raise ValueError("segment_seconds must be positive")
    if min_segment_seconds <= 0:
        raise ValueError("min_segment_seconds must be positive")
    if step_seconds is not None and step_seconds <= 0:
        raise ValueError("step_seconds must be positive when provided")
    if max_segments is not None and max_segments <= 0:
        raise ValueError("max_segments must be positive when provided")

    window = int(segment_seconds * sample_rate)
    step = int((step_seconds or segment_seconds) * sample_rate)
    min_size = int(min_segment_seconds * sample_rate)

    if mono.size < min_size:
        return []

    segments: list[tuple[float, AudioArray]] = []
    start = 0
    index = 0

    while start < mono.size:
        end = min(start + window, mono.size)
        chunk = mono[start:end]
        if chunk.size >= min_size:
            segments.append((start / sample_rate, chunk))
            index += 1
            if max_segments is not None and index >= max_segments:
                break
        start += step

    return segments


def build_reference_segments(
    audio: npt.NDArray[np.float32] | npt.NDArray[np.float64],
    sample_rate: int,
    *,
    segment_seconds: float = 12.0,
    step_seconds: float | None = None,
    min_segment_seconds: float = 8.0,
    max_segments: int | None = None,
) -> list[ReferenceSegment]:
    """Build scored segment objects for a full recording."""
    raw_segments = segment_audio(
        audio,
        sample_rate,
        segment_seconds=segment_seconds,
        step_seconds=step_seconds,
        min_segment_seconds=min_segment_seconds,
        max_segments=max_segments,
    )
    segments: list[ReferenceSegment] = []
    for index, (start_seconds, chunk) in enumerate(raw_segments, start=1):
        metrics = compute_segment_metrics(chunk, sample_rate)
        segments.append(
            ReferenceSegment(
                index=index,
                start_seconds=start_seconds,
                end_seconds=start_seconds + metrics.duration_seconds,
                metrics=metrics,
            )
        )
    return segments


def pick_best_segment(segments: list[ReferenceSegment]) -> ReferenceSegment | None:
    """Pick the highest-scoring reference segment."""
    if not segments:
        return None
    return max(
        segments,
        key=lambda segment: (
            segment.metrics.score,
            segment.metrics.speech_ratio,
            -segment.metrics.clipping_ratio,
        ),
    )
