#!/usr/bin/env python3
"""Run a small reproducible comparison matrix from one or more bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import soundfile as sf
from qwen_tts import Qwen3TTSModel  # type: ignore[import-not-found]

from tts_lab.infrastructure.comparison_manifest import (
    ComparisonCase,
    ComparisonResult,
    build_case_prefix,
    build_default_cases,
    build_manifest,
    slugify,
)
from tts_lab.infrastructure.reference_bundle import ReferenceBundle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare small cloning configurations")
    parser.add_argument(
        "--bundle",
        action="append",
        required=True,
        help="Path to bundle.json (repeatable)",
    )
    parser.add_argument("--text", required=True, help="Target text for comparison")
    parser.add_argument(
        "--text-label",
        default="custom",
        help="Stable label for the target text in output naming",
    )
    parser.add_argument(
        "--output-dir",
        default="output/voice_compare",
        help="Directory for generated audio and manifest",
    )
    parser.add_argument(
        "--model-path",
        default="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        help="Model path or model id",
    )
    parser.add_argument("--device", default="mps", help="Inference device")
    parser.add_argument(
        "--include-spanish-icl",
        action="store_true",
        help="Add optional spanish+icl cases for each bundle",
    )
    return parser.parse_args()


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"Bundle field '{key}' must be a non-empty string")
    return value.strip()


def _require_boolean(payload: dict[str, object], key: str) -> bool:
    value = payload[key]
    if not isinstance(value, bool):
        raise SystemExit(f"Bundle field '{key}' must be a boolean")
    return value


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise SystemExit(f"Bundle field '{key}' must be an integer")
    return value


def _require_float(payload: dict[str, object], key: str) -> float:
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise SystemExit(f"Bundle field '{key}' must be a number")
    return float(value)


def _require_string_list(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SystemExit(f"Bundle field '{key}' must be a list of strings")
    return tuple(value)


def _require_existing_path(payload: dict[str, object], key: str) -> str:
    raw_path = _require_string(payload, key)
    resolved = Path(raw_path).expanduser().resolve()
    if not resolved.exists():
        raise SystemExit(f"Bundle field '{key}' points to a missing file: {resolved}")
    if not resolved.is_file():
        raise SystemExit(f"Bundle field '{key}' must point to a file: {resolved}")
    return str(resolved)


def _load_bundle(path: Path) -> ReferenceBundle:
    if not path.exists():
        raise SystemExit(f"Bundle not found: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid bundle JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Bundle root must be a JSON object")
    try:
        return ReferenceBundle(
            speaker=_require_string(payload, "speaker"),
            segment_path=_require_existing_path(payload, "segment_path"),
            source_audio_path=_require_existing_path(payload, "source_audio_path"),
            reference_text=_require_string(payload, "reference_text"),
            transcription_source=_require_string(payload, "transcription_source"),
            transcription_validated=_require_boolean(payload, "transcription_validated"),
            score=_require_float(payload, "score"),
            recommended_segment_index=_require_int(payload, "recommended_segment_index"),
            mode_recommendation=_require_string(payload, "mode_recommendation"),
            language=_require_string(payload, "language"),
            warnings=_require_string_list(payload, "warnings"),
        )
    except KeyError as exc:
        raise SystemExit(f"Bundle is missing required field: {exc}") from exc


def _run_case(
    *,
    model: Qwen3TTSModel,
    case: ComparisonCase,
    bundle: ReferenceBundle,
    output_dir: Path,
) -> ComparisonResult:
    output_path = output_dir / f"{case.case_id}.wav"
    try:
        prompt = model.create_voice_clone_prompt(
            bundle.segment_path,
            bundle.reference_text,
            x_vector_only_mode=(case.mode == "embedding"),
        )
        wavs, sample_rate = model.generate_voice_clone(
            case.target_text,
            case.language,
            voice_clone_prompt=prompt,
        )
        if not wavs:
            raise ValueError("Model returned empty audio")
        if sample_rate <= 0:
            raise ValueError("Model returned a non-positive sample rate")
        sf.write(output_path, wavs[0], sample_rate)
        duration_seconds = len(wavs[0]) / sample_rate
        return ComparisonResult(
            case=case,
            status="success",
            output_path=str(output_path),
            duration_seconds=round(duration_seconds, 2),
            error_message=None,
        )
    except Exception as exc:
        return ComparisonResult(
            case=case,
            status="failed",
            output_path=None,
            duration_seconds=None,
            error_message=f"{type(exc).__name__}: {exc}",
        )


def main() -> None:
    args = _parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve() / slugify(args.text_label)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_paths = [Path(item).expanduser().resolve() for item in args.bundle]
    bundles = [(path, _load_bundle(path)) for path in bundle_paths]

    model = Qwen3TTSModel.from_pretrained(args.model_path, device_map=args.device)
    results: list[ComparisonResult] = []

    for bundle_path, bundle in bundles:
        cases = build_default_cases(
            bundle,
            bundle_path=str(bundle_path),
            target_text=args.text,
            text_label=args.text_label,
        )
        if args.include_spanish_icl:
            case_prefix = build_case_prefix(bundle, bundle_path=str(bundle_path))
            cases.append(
                ComparisonCase(
                    case_id=f"{case_prefix}-spanish-icl",
                    bundle_path=cases[0].bundle_path,
                    segment_path=cases[0].segment_path,
                    text_label=cases[0].text_label,
                    target_text=cases[0].target_text,
                    language="spanish",
                    mode="icl",
                    transcription_validated=cases[0].transcription_validated,
                    warnings=cases[0].warnings,
                )
            )
        for case in cases:
            result = _run_case(model=model, case=case, bundle=bundle, output_dir=output_dir)
            results.append(result)
            print(f"{case.case_id}: {result.status}")

    manifest = build_manifest(
        model_path=args.model_path,
        cases=results,
        output_dir=output_dir,
        target_text=args.text,
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    success_count = sum(1 for result in results if result.status == "success")
    failure_count = sum(1 for result in results if result.status == "failed")

    print(f"Manifest: {manifest_path}")
    print(f"Summary: {success_count} succeeded, {failure_count} failed")

    if failure_count > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
