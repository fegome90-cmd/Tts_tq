#!/usr/bin/env python3
"""
H2 experiment — embedding mode (x_vector_only_mode=True).

Triangulation step: ignores ref_text entirely (uses only speaker embedding
extracted from ref_audio). If H2 PASSES with the full 14s reference, then:
  - embedding mode tolerates long refs
  - the LOOP problem is specific to ICL mode conditioning on long ref_text+code
If H2 FAILS, the collapse affects embedding too (deeper model issue).

H1a (real ref_text, 14s, ICL) PASSED.
H1b (mismatched ref_text, 5s, ICL) PASSED.
H2 (embedding mode, 14s, no ref_text) — isolates ICL vs embedding.

Run with: .venv/bin/python scripts/generate_clone_h2.py
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

MODEL_PATH = "comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"
REF_AUDIO = "voice_profiles/felipe/reference_v2_fixed.wav"  # full 14s, no trim
# H2: ref_text not needed in embedding mode (ignored).
TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."
LANGUAGE = "spanish"
SEED = 42
OUTPUT_PATH = Path("output/experiments/clone_h2_embedding.wav")

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

    print("\n[H2] x_vector_only_mode=True (embedding, ignores ref_text)")
    print(f"  REF_AUDIO : {REF_AUDIO} (full 14s)")
    print("  ref_text  : NOT USED (embedding mode)")
    print(f"  TARGET    : {TARGET_TEXT}")
    print(f"  seed=42, sampling={GENERATE_KWARGS}", flush=True)

    torch.manual_seed(SEED)
    mps = getattr(torch, "mps", None)
    mps_manual_seed = getattr(mps, "manual_seed", None)
    if callable(mps_manual_seed):
        mps_manual_seed(SEED)

    print("\nGenerating (embedding mode)...", flush=True)
    t = time.time()
    # Embedding mode: pass ref_audio + x_vector_only_mode=True.
    # generate_voice_clone forwards via loose **kwargs; cast to Any for stub.
    generate = cast(Any, model.generate_voice_clone)
    wavs, sr = generate(
        TARGET_TEXT,
        LANGUAGE,
        ref_audio=REF_AUDIO,
        x_vector_only_mode=True,
        **GENERATE_KWARGS,
    )
    elapsed = time.time() - t

    sf.write(OUTPUT_PATH, wavs[0], sr)
    duration_seconds = len(wavs[0]) / sr
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  duration: {duration_seconds:.2f}s  (H1a 10.16s, H1b 16.80s, baseline 40.88s)")


if __name__ == "__main__":
    main()
