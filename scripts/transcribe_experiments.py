#!/usr/bin/env python3
"""
Transcribe experiment outputs with Whisper (medium) to detect phonetic drift
in Qwen3-TTS cloned voice (es-CL target).

Outputs a JSON report + prints a human-readable comparison table.
Run with: .venv/bin/python scripts/transcribe_experiments.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import whisper

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
REPORT_PATH = OUTPUT_DIR / "experiments_transcription_report.json"

# (label, path) — reference first for context, then experiments chronologically
TARGETS: list[tuple[str, Path]] = [
    ("REF_reference", ROOT / "voice_profiles/felipe/reference.wav"),
    ("REF_pitch_15s", ROOT / "voice_profiles/felipe/pitch_segment_15s_fixed.wav"),
    ("EXP_test", OUTPUT_DIR / "experiments/test.wav"),
    ("EXP_1_icl_completo", OUTPUT_DIR / "experiments/ejemplo_1_icl_completo.wav"),
    ("EXP_2_embedding_neutral", OUTPUT_DIR / "experiments/ejemplo_2_embedding_neutral.wav"),
    ("EXP_3_temp_baja", OUTPUT_DIR / "experiments/ejemplo_3_temp_baja.wav"),
    ("EXP_4_temp_alta", OUTPUT_DIR / "experiments/ejemplo_4_temp_alta.wav"),
    ("EXP_6_voz_disenada", OUTPUT_DIR / "experiments/ejemplo_6_voz_disenada.wav"),
    ("EXP_voice_designed", OUTPUT_DIR / "experiments/voice_designed.wav"),
]

MODEL_NAME = "medium"
LANGUAGE = "es"  # force Spanish decoding — we want to see what the model "heard"


def main() -> None:
    print(f"Loading Whisper {MODEL_NAME!r} (forced language={LANGUAGE!r})...", flush=True)
    t0 = time.time()
    model = whisper.load_model(MODEL_NAME)
    print(f"Model loaded in {time.time() - t0:.1f}s", flush=True)

    results: list[dict[str, Any]] = []
    for label, path in TARGETS:
        if not path.exists():
            print(f"  [SKIP] {label}: {path} not found")
            results.append({"label": label, "path": str(path), "error": "not_found"})
            continue

        print(f"  Transcribing {label} ({path.name})...", flush=True)
        t = time.time()
        result = model.transcribe(
            str(path),
            language=LANGUAGE,
            task="transcribe",
            temperature=0.0,  # deterministic — better for drift comparison
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
        )
        elapsed = time.time() - t
        result_typed: dict[str, Any] = result
        text = result_typed.get("text", "").strip()
        segments: list[dict[str, Any]] = result_typed.get("segments", [])

        entry = {
            "label": label,
            "path": str(path.relative_to(ROOT)),
            "elapsed_s": round(elapsed, 2),
            "language": result.get("language"),
            "text": text,
            "n_segments": len(segments),
            "avg_logprob": round(
                sum(s.get("avg_logprob", 0.0) for s in segments) / max(len(segments), 1), 3
            ),
            "no_speech_prob_avg": round(
                sum(s.get("no_speech_prob", 0.0) for s in segments) / max(len(segments), 1), 4
            ),
            "segments": [
                {
                    "id": s.get("id"),
                    "start": round(s.get("start", 0.0), 2),
                    "end": round(s.get("end", 0.0), 2),
                    "text": s.get("text", "").strip(),
                }
                for s in segments
            ],
        }
        results.append(entry)
        print(
            f"    [{elapsed:.1f}s] logprob={entry['avg_logprob']} no_speech={entry['no_speech_prob_avg']}"
        )
        print(f"    TEXT: {text}")

    REPORT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nReport saved: {REPORT_PATH}")

    # Human-readable table
    print("\n" + "=" * 80)
    print("TRANSCRIPTION SUMMARY (Whisper medium, language=es, temp=0.0)")
    print("=" * 80)
    for r in results:
        if "error" in r:
            print(f"\n[{r['label']}] ERROR: {r['error']}")
            continue
        print(f"\n[{r['label']}] ({r['path']})")
        print(f"  confidence: logprob={r['avg_logprob']}  no_speech={r['no_speech_prob_avg']}")
        print(f"  text: {r['text']}")


if __name__ == "__main__":
    main()
