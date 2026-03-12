#!/usr/bin/env python3
"""Prepare local reference audio for cloning experiments.

This command converts an input recording to a standard WAV format, slices it into
short candidate segments, computes simple quality metrics, and writes metadata
including the recommended segment.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import soundfile as sf

from tts_lab.infrastructure.reference_preparation import (
    build_reference_segments,
    pick_best_segment,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare reference audio for voice cloning")
    parser.add_argument("--input", required=True, help="Path to input audio file")
    parser.add_argument("--speaker", required=True, help="Speaker/profile name")
    parser.add_argument(
        "--output-root",
        default="voice_profiles",
        help="Root directory for local speaker assets",
    )
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=12.0,
        help="Target segment size in seconds (recommended 8-15)",
    )
    parser.add_argument(
        "--step-seconds",
        type=float,
        default=12.0,
        help="Step size between segment starts in seconds",
    )
    parser.add_argument(
        "--min-segment-seconds",
        type=float,
        default=8.0,
        help="Minimum accepted segment size in seconds",
    )
    parser.add_argument(
        "--max-segments",
        type=int,
        default=6,
        help="Maximum number of segments to write",
    )
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> Path:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input audio not found: {input_path}")
    if not args.speaker.strip():
        raise SystemExit("speaker cannot be empty")
    if args.segment_seconds <= 0:
        raise SystemExit("segment-seconds must be positive")
    if args.step_seconds <= 0:
        raise SystemExit("step-seconds must be positive")
    if args.min_segment_seconds <= 0:
        raise SystemExit("min-segment-seconds must be positive")
    if args.max_segments <= 0:
        raise SystemExit("max-segments must be positive")
    return input_path


def _convert_to_wav(input_path: Path, output_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ar",
        "24000",
        "-ac",
        "1",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg conversion failed: {result.stderr.strip()}")


def main() -> None:
    args = _parse_args()
    input_path = _validate_args(args)

    output_root = Path(args.output_root).expanduser().resolve()
    speaker_dir = output_root / args.speaker / "refs" / input_path.stem
    speaker_dir.mkdir(parents=True, exist_ok=True)

    normalized_path = speaker_dir / "source.wav"
    _convert_to_wav(input_path, normalized_path)

    audio, sample_rate = sf.read(normalized_path)
    segments = build_reference_segments(
        audio,
        sample_rate,
        segment_seconds=args.segment_seconds,
        step_seconds=args.step_seconds,
        min_segment_seconds=args.min_segment_seconds,
        max_segments=args.max_segments,
    )
    if not segments:
        raise SystemExit(
            "No valid segments were produced; try a longer recording or lower min-segment-seconds"
        )

    best_segment = pick_best_segment(segments)
    if best_segment is None:
        raise SystemExit("Failed to choose a recommended segment")

    written_segments: list[dict[str, object]] = []
    for segment in segments:
        segment_audio, _ = sf.read(normalized_path, start=int(segment.start_seconds * sample_rate), stop=int(segment.end_seconds * sample_rate))
        segment_path = speaker_dir / f"segment_{segment.index:02d}.wav"
        sf.write(segment_path, segment_audio, sample_rate)
        segment_payload = segment.to_dict()
        segment_payload["path"] = str(segment_path)
        segment_payload["recommended"] = segment.index == best_segment.index
        written_segments.append(segment_payload)

    metadata = {
        "speaker": args.speaker,
        "input_path": str(input_path),
        "normalized_path": str(normalized_path),
        "sample_rate": sample_rate,
        "segment_seconds": args.segment_seconds,
        "step_seconds": args.step_seconds,
        "min_segment_seconds": args.min_segment_seconds,
        "max_segments": args.max_segments,
        "recommended_segment_index": best_segment.index,
        "recommended_segment_path": str(speaker_dir / f"segment_{best_segment.index:02d}.wav"),
        "segments": written_segments,
        "cleaning_applied": False,
    }

    metadata_path = speaker_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    print(f"Prepared reference assets at: {speaker_dir}")
    print(f"Recommended segment: segment_{best_segment.index:02d}.wav")
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
