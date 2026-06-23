"""Unit tests for reference bundle helpers."""

from pathlib import Path

import pytest

from tts_lab.infrastructure.reference_bundle import build_reference_bundle


@pytest.fixture
def sample_metadata(tmp_path: Path) -> dict[str, object]:
    source_path = tmp_path / "source.wav"
    segment_path = tmp_path / "segment_01.wav"
    source_path.write_bytes(b"wav")
    segment_path.write_bytes(b"wav")
    return {
        "speaker": "felipe",
        "normalized_path": str(source_path),
        "recommended_segment_index": 1,
        "recommended_segment_path": str(segment_path),
        "segments": [
            {
                "index": 1,
                "path": str(segment_path),
                "metrics": {
                    "score": 0.72,
                },
            }
        ],
    }


class TestBuildReferenceBundle:
    """Tests for bundle construction and validation."""

    def test_build_reference_bundle_success(self, sample_metadata: dict[str, object]) -> None:
        bundle = build_reference_bundle(
            sample_metadata,
            "Hola, esta es una referencia.",
            transcription_source="whisper:small",
            transcription_validated=False,
        )

        assert bundle.speaker == "felipe"
        assert bundle.mode_recommendation == "icl"
        assert bundle.score == pytest.approx(0.72)
        assert "transcription_not_manually_validated" in bundle.warnings

    def test_build_reference_bundle_rejects_empty_reference_text(
        self,
        sample_metadata: dict[str, object],
    ) -> None:
        with pytest.raises(ValueError, match="reference_text"):
            build_reference_bundle(
                sample_metadata,
                "",
                transcription_source="whisper:small",
                transcription_validated=False,
            )

    def test_build_reference_bundle_requires_recommended_segment(
        self,
        sample_metadata: dict[str, object],
    ) -> None:
        sample_metadata["segments"] = []
        with pytest.raises(ValueError, match="segments"):
            build_reference_bundle(
                sample_metadata,
                "hola",
                transcription_source="whisper:small",
                transcription_validated=False,
            )

    def test_build_reference_bundle_rejects_missing_source_audio_path(
        self,
        sample_metadata: dict[str, object],
        tmp_path: Path,
    ) -> None:
        sample_metadata["normalized_path"] = str(tmp_path / "missing-source.wav")
        with pytest.raises(ValueError, match="normalized_path"):
            build_reference_bundle(
                sample_metadata,
                "hola",
                transcription_source="whisper:small",
                transcription_validated=True,
            )

    def test_build_reference_bundle_rejects_missing_recommended_segment_file(
        self,
        sample_metadata: dict[str, object],
        tmp_path: Path,
    ) -> None:
        missing_segment = tmp_path / "missing-segment.wav"
        sample_metadata["recommended_segment_path"] = str(missing_segment)
        sample_metadata["segments"] = [
            {
                "index": 1,
                "path": str(missing_segment),
                "metrics": {"score": 0.72},
            }
        ]
        with pytest.raises(ValueError, match="recommended segment file"):
            build_reference_bundle(
                sample_metadata,
                "hola",
                transcription_source="whisper:small",
                transcription_validated=True,
            )

    def test_build_reference_bundle_warns_on_low_score(
        self,
        sample_metadata: dict[str, object],
    ) -> None:
        segments = sample_metadata["segments"]
        assert isinstance(segments, list)
        first_segment = segments[0]
        assert isinstance(first_segment, dict)
        metrics = first_segment["metrics"]
        assert isinstance(metrics, dict)
        metrics["score"] = 0.4
        bundle = build_reference_bundle(
            sample_metadata,
            "hola",
            transcription_source="whisper:small",
            transcription_validated=True,
        )

        assert "recommended_segment_low_score" in bundle.warnings
        assert bundle.transcription_validated is True
