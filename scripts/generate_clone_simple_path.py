#!/usr/bin/env python3
"""
Test 1c: use the OFFICIAL single-inference path from the README.

Prior test (generate_clone_fixed.py) used the voice_clone_prompt pre-built
path (create_voice_clone_prompt + voice_clone_prompt=...), which the README
documents as "for reuse only". The model cited the REF_TEXT instead of
generating the TARGET_TEXT and collapsed into loops.

This script uses the path the README recommends for single inference:
  generate_voice_clone(text, language, ref_audio=..., ref_text=...)

The model builds the prompt internally. Same anti-loop sampling kwargs and
fixed seed as the prior test, so any difference in output is attributable to
the call-path change, not to sampling.

Run with: .venv/bin/python scripts/generate_clone_simple_path.py
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

# --- Config -----------------------------------------------------------------
MODEL_PATH = "comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"
REF_AUDIO = "voice_profiles/felipe/reference_v2_fixed.wav"
REF_TEXT = (
    "La tecnología de inteligencia artificial ha revolucionado la forma en que "
    "interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones "
    "que facilitan nuestras tareas diarias."
)
TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."
LANGUAGE = "spanish"
SEED = 42
OUTPUT_PATH = Path("output/experiments/clone_simple_path.wav")

# --- Same anti-loop sampling kwargs as generate_clone_fixed.py --------------
GENERATE_KWARGS = {
    "repetition_penalty": 1.2,
    "top_p": 0.9,
    "top_k": 50,
    "temperature": 0.7,
    "max_new_tokens": 512,
}


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not Path(REF_AUDIO).exists():
        raise SystemExit(f"Reference audio not found: {REF_AUDIO}")

    print(f"Loading model {MODEL_PATH} on mps...", flush=True)
    t0 = time.time()
    model = Qwen3TTSModel.from_pretrained(MODEL_PATH, device_map="mps")
    print(f"Model loaded in {time.time() - t0:.1f}s", flush=True)

    print(f"Reference: {REF_AUDIO}", flush=True)
    print(f"Target text: {TARGET_TEXT}", flush=True)
    print(f"Seed: {SEED}", flush=True)
    print("Path: OFFICIAL single-inference (ref_audio + ref_text direct)", flush=True)
    print(f"Sampling kwargs: {GENERATE_KWARGS}", flush=True)

    # Seed RNGs BEFORE generation for reproducibility (CPU + MPS).
    torch.manual_seed(SEED)
    mps = getattr(torch, "mps", None)
    mps_manual_seed = getattr(mps, "manual_seed", None)
    if callable(mps_manual_seed):
        mps_manual_seed(SEED)

    print("Generating via simple path (this takes a few minutes)...", flush=True)
    t = time.time()
    # Path change: pass ref_audio + ref_text directly (no voice_clone_prompt=...).
    # generate_voice_clone will build the prompt internally per the README.
    # Pyright cannot resolve the loose **kwargs signature; treat as Any.
    generate = cast(Any, model.generate_voice_clone)
    wavs, sr = generate(
        TARGET_TEXT,
        LANGUAGE,
        ref_audio=REF_AUDIO,
        ref_text=REF_TEXT,
        **GENERATE_KWARGS,
    )
    elapsed = time.time() - t

    sf.write(OUTPUT_PATH, wavs[0], sr)
    duration_seconds = len(wavs[0]) / sr
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  duration: {duration_seconds:.2f}s")
    print(f"  sample_rate: {sr}")
    print("\nNext: transcribe with Whisper to verify coherence.")


if __name__ == "__main__":
    main()
