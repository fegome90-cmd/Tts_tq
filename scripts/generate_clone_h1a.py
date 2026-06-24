#!/usr/bin/env python3
"""
H1a experiment — ref_text fidelity ONLY (Judgment Gate v2 PASS by convergence).

Isolates a single variable: replace the politically-correct REF_TEXT that
prior scripts passed with the EXACT Whisper-medium transcription of the
reference audio. Everything else unchanged from baseline:
  - same reference audio (reference_v2_fixed.wav, 14s, NO trimming)
  - same anti-loop sampling kwargs
  - same seed=42
  - same official single-inference API path

If output_coherence improves to PARTIAL/COHERENT, ref_text mismatch was the
root cause. If still LOOP/DEGENERATE, escalate to H1b (trim) or H2 (embedding).

Evidence (JG-003 resolved): script's REF_TEXT said "inteligencia artificial
... dispositivos ... aplicaciones" but Whisper transcribes the audio as
"revolución artificial ... distintos días ... habitaciones". ICL mode
conditions on ref_text+ref_code; mismatched pairs degenerate.

Run with: .venv/bin/python scripts/generate_clone_h1a.py
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

# --- Config (only REF_TEXT differs from baseline) --------------------------
MODEL_PATH = "comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"
REF_AUDIO = "voice_profiles/felipe/reference_v2_fixed.wav"

# H1a intervention: REF_TEXT = exact Whisper-medium transcription of REF_AUDIO.
# (Prior scripts passed a fabricated sentence the audio never says.)
REF_TEXT = (
    "La revolución artificial ha revolucionado la forma en que interactuamos "
    "con los distintos días. Cada día descubrimos nuevas habitaciones que se "
    "presentan en nuestra realidad diaria."
)
TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."
LANGUAGE = "spanish"
SEED = 42
OUTPUT_PATH = Path("output/experiments/clone_h1a_ref_text_real.wav")

# --- Identical to baseline (no other changes) ------------------------------
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

    print("\n[H1a] ONLY change vs baseline: REF_TEXT = real Whisper transcription")
    print(f"  REF_AUDIO: {REF_AUDIO}")
    print(f"  REF_TEXT : {REF_TEXT}")
    print(f"  TARGET   : {TARGET_TEXT}")
    print(f"  seed=42, sampling={GENERATE_KWARGS}", flush=True)

    torch.manual_seed(SEED)
    mps = getattr(torch, "mps", None)
    mps_manual_seed = getattr(mps, "manual_seed", None)
    if callable(mps_manual_seed):
        mps_manual_seed(SEED)

    print("\nGenerating (this takes ~90s)...", flush=True)
    t = time.time()
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
    print(f"  duration: {duration_seconds:.2f}s  (baseline was 40.88s)")
    print(f"  sample_rate: {sr}")


if __name__ == "__main__":
    main()
