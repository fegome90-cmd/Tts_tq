#!/usr/bin/env python3
"""Transcribe a prepared reference segment and emit a reusable bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import whisper  # type: ignore[import-untyped]

from tts_lab.infrastructure.reference_bundle import build_reference_bundle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe prepared reference audio")
    parser.add_argument("--metadata", required=True, help="Path to metadata.json from prepare_reference")
    parser.add_argument("--model", default="small", help="Whisper model name")
    parser.add_argument("--language", default="es", help="Language hint for whisper")
    parser.add_argument(
        "--reference-text-file",
        help="Optional path to manually corrected transcription text file",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Metadata file not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid metadata JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Metadata root must be a JSON object")
    return data


def _transcribe(segment_path: Path, model_name: str, language: str) -> str:
    model = whisper.load_model(model_name)
    result = model.transcribe(str(segment_path), language=language)
    text = result.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise SystemExit("Whisper returned an empty transcription")
    return text.strip()


def main() -> None:
    args = _parse_args()
    metadata_path = Path(args.metadata).expanduser().resolve()
    metadata = _load_json(metadata_path)

    recommended_segment_path = metadata.get("recommended_segment_path")
    if not isinstance(recommended_segment_path, str) or not recommended_segment_path.strip():
        raise SystemExit("metadata is missing 'recommended_segment_path'")
    segment_path = Path(recommended_segment_path)
    if not segment_path.exists():
        raise SystemExit(f"Recommended segment not found: {segment_path}")

    output_dir = metadata_path.parent
    auto_text_path = output_dir / "transcription.auto.txt"
    bundle_path = output_dir / "bundle.json"

    transcription_validated = False
    transcription_source = f"whisper:{args.model}"

    if args.reference_text_file:
        reference_text_path = Path(args.reference_text_file).expanduser().resolve()
        if not reference_text_path.exists():
            raise SystemExit(f"Reference text file not found: {reference_text_path}")
        reference_text = reference_text_path.read_text().strip()
        if not reference_text:
            raise SystemExit("Reference text file is empty")
        transcription_validated = True
        transcription_source = "manual_file"
    else:
        reference_text = _transcribe(segment_path, args.model, args.language)
        auto_text_path.write_text(reference_text + "\n")

    bundle = build_reference_bundle(
        metadata,
        reference_text,
        transcription_source=transcription_source,
        transcription_validated=transcription_validated,
        language=args.language,
    )
    bundle_path.write_text(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False))

    print(f"Recommended segment: {segment_path}")
    if not transcription_validated:
        print(f"Auto transcription: {auto_text_path}")
    print(f"Bundle: {bundle_path}")
    if not transcription_validated:
        print(
            "Tip: edit transcription.auto.txt and rerun with --reference-text-file to mark it as validated."
        )


if __name__ == "__main__":
    main()
