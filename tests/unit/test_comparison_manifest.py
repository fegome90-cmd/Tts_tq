"""Unit tests for comparison manifest helpers."""

from pathlib import Path
from typing import Any, cast

from tts_lab.infrastructure.comparison_manifest import (
    ComparisonResult,
    build_default_cases,
    build_manifest,
    slugify,
)
from tts_lab.infrastructure.reference_bundle import ReferenceBundle


def _bundle(*, speaker: str = "felipe") -> ReferenceBundle:
    return ReferenceBundle(
        speaker=speaker,
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


def _bundle_json_path(name: str = "bundle") -> str:
    return f"/tmp/{name}.json"


def test_slugify_produces_stable_case_id() -> None:
    assert slugify("Text 1 / Neutral") == "text-1-neutral"


def test_build_default_cases_returns_small_matrix() -> None:
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


def test_build_default_cases_uses_bundle_path_to_avoid_case_id_collisions() -> None:
    bundle = _bundle(speaker="shared-speaker")
    first_cases = build_default_cases(
        bundle,
        bundle_path=_bundle_json_path("first-bundle"),
        target_text="hola",
        text_label="neutral",
    )
    second_cases = build_default_cases(
        bundle,
        bundle_path=_bundle_json_path("second-bundle"),
        target_text="hola",
        text_label="neutral",
    )

    assert first_cases[0].case_id != second_cases[0].case_id
    assert first_cases[1].case_id != second_cases[1].case_id


def test_build_manifest_serializes_cases() -> None:
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
    # build_manifest returns dict[str, object]; cases is a nested list[dict],
    # narrowed via cast so mypy allows indexing the nested structure.
    cases = cast(list[dict[str, Any]], manifest["cases"])
    assert cases[0]["status"] == "success"
    assert cases[0]["case"]["mode"] == "icl"
    assert cases[0]["case"]["bundle_path"] == _bundle_json_path()
