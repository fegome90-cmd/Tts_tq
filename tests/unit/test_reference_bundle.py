"""Unit tests for reference bundle helpers."""

import pytest

from tts_lab.infrastructure.reference_bundle import build_reference_bundle


@pytest.fixture
def sample_metadata(tmp_path):
    segment_path = tmp_path / "segment_01.wav"
    segment_path.write_bytes(b"wav")
    return {
        "speaker": "felipe",
        "normalized_path": str(tmp_path / "source.wav"),
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

    def test_build_reference_bundle_success(self, sample_metadata):
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

    def test_build_reference_bundle_rejects_empty_reference_text(self, sample_metadata):
        with pytest.raises(ValueError, match="reference_text"):
            build_reference_bundle(
                sample_metadata,
                "",
                transcription_source="whisper:small",
                transcription_validated=False,
            )

    def test_build_reference_bundle_requires_recommended_segment(self, sample_metadata):
        sample_metadata["segments"] = []
        with pytest.raises(ValueError, match="segments"):
            build_reference_bundle(
                sample_metadata,
                "hola",
                transcription_source="whisper:small",
                transcription_validated=False,
            )

    def test_build_reference_bundle_warns_on_low_score(self, sample_metadata):
        sample_metadata["segments"][0]["metrics"]["score"] = 0.4
        bundle = build_reference_bundle(
            sample_metadata,
            "hola",
            transcription_source="whisper:small",
            transcription_validated=True,
        )

        assert "recommended_segment_low_score" in bundle.warnings
        assert bundle.transcription_validated is True
