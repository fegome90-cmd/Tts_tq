#!/usr/bin/env python3
"""
Generate a single valid voice-cloned output with sampling params fixed.

Context: prior experiments collapsed into "hola hola..." loops because they
called generate_voice_clone() without sampling kwargs, triggering qwen_tts
hard_defaults (repetition_penalty=1.05, top_p=1.0, temperature=0.9,
max_new_tokens=2048) — a combination that does not prevent repetition collapse.

This script passes explicit anti-loop sampling params and a fixed seed for
reproducibility. Output is transcribed afterward with Whisper medium to
verify the clone is coherent (not a loop) before committing to a full batch.

Run with: .venv/bin/python scripts/generate_clone_fixed.py
"""

from __future__ import annotations

import time
from pathlib import Path

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
OUTPUT_PATH = Path("output/experiments/clone_fixed_icl.wav")

# --- Anti-loop sampling params (override qwen_tts hard_defaults) ------------
# repetition_penalty 1.2 (was 1.05) — strong enough to break loops.
# top_p 0.9 (was 1.0) — nucleus sampling reduces noise.
# top_k 50 — unchanged from default.
# temperature 0.7 (was 0.9) — less randomness.
# max_new_tokens 512 (was 2048) — sane cap for a short sentence (~10s audio).
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
    print(f"Sampling kwargs: {GENERATE_KWARGS}", flush=True)

    # Seed RNGs BEFORE generation for reproducibility (CPU + MPS).
    # torch.mps is a runtime-only attribute (not in stubs); guard defensively.
    torch.manual_seed(SEED)
    mps = getattr(torch, "mps", None)
    mps_manual_seed = getattr(mps, "manual_seed", None)
    if callable(mps_manual_seed):
        mps_manual_seed(SEED)

    print("Creating ICL voice clone prompt...", flush=True)
    prompt = model.create_voice_clone_prompt(
        REF_AUDIO,
        REF_TEXT,
        x_vector_only_mode=False,  # full ICL mode
    )

    print("Generating (this takes a few minutes)...", flush=True)
    t = time.time()
    # generate_voice_clone forwards sampling kwargs via **kwargs to the
    # underlying transformers generate(); Pyright cannot resolve the
    # dict-spread against the loose **kwargs signature and reports spurious
    # type mismatches. Treat the call as Any to bypass the stub limitation.
    from typing import Any, cast

    untyped_generate = cast(Any, model.generate_voice_clone)
    wavs, sr = untyped_generate(
        TARGET_TEXT,
        LANGUAGE,
        voice_clone_prompt=prompt,
        **GENERATE_KWARGS,
    )
    elapsed = time.time() - t

    sf.write(OUTPUT_PATH, wavs[0], sr)
    duration_seconds = len(wavs[0]) / sr
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  duration: {duration_seconds:.2f}s")
    print(f"  sample_rate: {sr}")
    print("\nNext: transcribe with Whisper to verify coherence:")
    print("  .venv/bin/python scripts/transcribe_experiments.py")


if __name__ == "__main__":
    main()
