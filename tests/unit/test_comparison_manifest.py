"""Unit tests for comparison manifest helpers."""

from pathlib import Path

from tts_lab.infrastructure.comparison_manifest import (
    ComparisonResult,
    build_default_cases,
    build_manifest,
    slugify,
)
from tts_lab.infrastructure.reference_bundle import ReferenceBundle


def _bundle() -> ReferenceBundle:
    return ReferenceBundle(
        speaker="felipe",
        segment_path="/tmp/pitch_seg1.wav",
        source_audio_path="/tmp/source.wav",
        reference_text="Hola, esta es mi referencia.",
        transcription_source="manual_file",
        transcription_validated=True,
        score=0.81,
        recommended_segment_index=1,
        mode_recommendation="icl",
        language="es",
        warnings=(),
    )


def _bundle_json_path() -> str:
    return "/tmp/bundle.json"


def test_slugify_produces_stable_case_id():
    assert slugify("Text 1 / Neutral") == "text-1-neutral"


def test_build_default_cases_returns_small_matrix():
    bundle = _bundle()
    cases = build_default_cases(
        bundle,
        bundle_path=_bundle_json_path(),
        target_text="hola",
        text_label="neutral",
    )

    assert len(cases) == 2
    assert cases[0].mode == "icl"
    assert cases[1].mode == "embedding"
    assert all(case.language == "auto" for case in cases)
    assert all(case.bundle_path == _bundle_json_path() for case in cases)


def test_build_manifest_serializes_cases():
    bundle = _bundle()
    case = build_default_cases(
        bundle,
        bundle_path=_bundle_json_path(),
        target_text="hola",
        text_label="neutral",
    )[0]
    result = ComparisonResult(
        case=case,
        status="success",
        output_path="/tmp/output.wav",
        duration_seconds=3.2,
        error_message=None,
    )

    manifest = build_manifest(
        model_path="model",
        cases=[result],
        output_dir=Path("output/voice_compare"),
        target_text="hola",
    )

    assert manifest["model_path"] == "model"
    assert manifest["target_text"] == "hola"
    assert manifest["cases"][0]["status"] == "success"
    assert manifest["cases"][0]["case"]["mode"] == "icl"
    assert manifest["cases"][0]["case"]["bundle_path"] == _bundle_json_path()
