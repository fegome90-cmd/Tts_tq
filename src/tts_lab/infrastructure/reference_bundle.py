"""Reference bundle helpers for ICL cloning workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReferenceBundle:
    """Serializable bundle for a prepared cloning reference."""

    speaker: str
    segment_path: str
    source_audio_path: str
    reference_text: str
    transcription_source: str
    transcription_validated: bool
    score: float
    recommended_segment_index: int
    mode_recommendation: str
    language: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize bundle to a JSON-friendly mapping."""
        return {
            "speaker": self.speaker,
            "segment_path": self.segment_path,
            "source_audio_path": self.source_audio_path,
            "reference_text": self.reference_text,
            "transcription_source": self.transcription_source,
            "transcription_validated": self.transcription_validated,
            "score": self.score,
            "recommended_segment_index": self.recommended_segment_index,
            "mode_recommendation": self.mode_recommendation,
            "language": self.language,
            "warnings": list(self.warnings),
        }


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"metadata field '{key}' is required")
    return value


def _require_existing_file(path: str, *, key: str) -> str:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"metadata field '{key}' must point to an existing file")
    return str(resolved)


def _recommended_segment(metadata: dict[str, Any]) -> dict[str, Any]:
    segments = metadata.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("metadata field 'segments' must be a non-empty list")

    recommended_path = metadata.get("recommended_segment_path")
    recommended_index = metadata.get("recommended_segment_index")
    if not isinstance(recommended_path, str) or not recommended_path.strip():
        raise ValueError("metadata field 'recommended_segment_path' is required")
    if not isinstance(recommended_index, int):
        raise ValueError("metadata field 'recommended_segment_index' is required")

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        if segment.get("index") == recommended_index and segment.get("path") == recommended_path:
            return segment
    raise ValueError("recommended segment was not found inside metadata 'segments'")


def build_reference_bundle(
    metadata: dict[str, Any],
    reference_text: str,
    *,
    transcription_source: str,
    transcription_validated: bool,
    language: str = "es",
) -> ReferenceBundle:
    """Build a validated reference bundle from prepared metadata + transcript."""
    if not reference_text.strip():
        raise ValueError("reference_text cannot be empty")
    if not transcription_source.strip():
        raise ValueError("transcription_source cannot be empty")

    speaker = _require_string(metadata, "speaker")
    normalized_path = _require_existing_file(_require_string(metadata, "normalized_path"), key="normalized_path")
    recommended = _recommended_segment(metadata)

    score = recommended.get("metrics", {}).get("score")
    if not isinstance(score, float | int):
        raise ValueError("recommended segment metrics.score is required")

    warnings: list[str] = []
    if not transcription_validated:
        warnings.append("transcription_not_manually_validated")
    if float(score) < 0.6:
        warnings.append("recommended_segment_low_score")

    recommended_segment_path = _require_existing_file(str(recommended["path"]), key="recommended segment file")

    mode_recommendation = "icl"
    return ReferenceBundle(
        speaker=speaker,
        segment_path=recommended_segment_path,
        source_audio_path=normalized_path,
        reference_text=reference_text.strip(),
        transcription_source=transcription_source.strip(),
        transcription_validated=transcription_validated,
        score=float(score),
        recommended_segment_index=int(metadata["recommended_segment_index"]),
        mode_recommendation=mode_recommendation,
        language=language,
        warnings=tuple(warnings),
    )
