#!/usr/bin/env python3
"""
H1b experiment — reference trimming ONLY (triangulation control for H1a).

Isolates the SECOND variable that H1 originally bundled: trim reference to
<=5s while keeping the ORIGINAL mismatched REF_TEXT. Everything else
identical to baseline.

Purpose: H1a PASSED with real ref_text + full 14s ref. H1b tests whether
trimming alone (without ref_text fix) would have also worked. Expected:
H1b FAILS (LOOP) — confirming ref_text fidelity was the real cause, not
reference length. This triangulates the root cause.

Run with: .venv/bin/python scripts/generate_clone_h1b.py
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

# --- Config (only REF_AUDIO differs: trimmed to 5s) ------------------------
MODEL_PATH = "comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"

# Trim reference_v2_fixed.wav to first 5s, save to temp file.
REF_AUDIO_FULL = "voice_profiles/felipe/reference_v2_fixed.wav"
REF_AUDIO_TRIMMED = "/tmp/ref_trimmed_5s.wav"
TRIM_SECONDS = 5.0

# H1b: KEEP the original (mismatched) REF_TEXT from baseline scripts.
REF_TEXT = (
    "La tecnología de inteligencia artificial ha revolucionado la forma en que "
    "interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones "
    "que facilitan nuestras tareas diarias."
)
TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."
LANGUAGE = "spanish"
SEED = 42
OUTPUT_PATH = Path("output/experiments/clone_h1b_trim_only.wav")

GENERATE_KWARGS = {
    "repetition_penalty": 1.2,
    "top_p": 0.9,
    "top_k": 50,
    "temperature": 0.7,
    "max_new_tokens": 512,
}


def trim_reference() -> None:
    """Trim REF_AUDIO_FULL to first TRIM_SECONDS, save to REF_AUDIO_TRIMMED."""
    wav, sr = sf.read(REF_AUDIO_FULL)
    n_samples = int(TRIM_SECONDS * sr)
    trimmed = wav[:n_samples]
    sf.write(REF_AUDIO_TRIMMED, trimmed, sr)
    print(f"Trimmed {REF_AUDIO_FULL} to first {TRIM_SECONDS}s -> {REF_AUDIO_TRIMMED}", flush=True)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not Path(REF_AUDIO_FULL).exists():
        raise SystemExit(f"Reference audio not found: {REF_AUDIO_FULL}")

    trim_reference()

    print(f"Loading model {MODEL_PATH} on mps...", flush=True)
    t0 = time.time()
    model = Qwen3TTSModel.from_pretrained(MODEL_PATH, device_map="mps")
    print(f"Model loaded in {time.time() - t0:.1f}s", flush=True)

    print(f"\n[H1b] ONLY change vs baseline: REF_AUDIO trimmed to {TRIM_SECONDS}s")
    print(f"  REF_AUDIO : {REF_AUDIO_TRIMMED}")
    print(f"  REF_TEXT  : (ORIGINAL mismatched) {REF_TEXT[:60]}...")
    print(f"  TARGET    : {TARGET_TEXT}")
    print(f"  seed=42, sampling={GENERATE_KWARGS}", flush=True)

    torch.manual_seed(SEED)
    mps = getattr(torch, "mps", None)
    mps_manual_seed = getattr(mps, "manual_seed", None)
    if callable(mps_manual_seed):
        mps_manual_seed(SEED)

    print("\nGenerating (triangulation control)...", flush=True)
    t = time.time()
    generate = cast(Any, model.generate_voice_clone)
    wavs, sr = generate(
        TARGET_TEXT,
        LANGUAGE,
        ref_audio=REF_AUDIO_TRIMMED,
        ref_text=REF_TEXT,
        **GENERATE_KWARGS,
    )
    elapsed = time.time() - t

    sf.write(OUTPUT_PATH, wavs[0], sr)
    duration_seconds = len(wavs[0]) / sr
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  duration: {duration_seconds:.2f}s  (baseline 40.88s, H1a was 10.16s)")


if __name__ == "__main__":
    main()
