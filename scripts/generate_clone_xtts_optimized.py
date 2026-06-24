#!/usr/bin/env python3
"""
O-3c: XTTS-v2 con param tuning + multi-ref para eliminar artifacts.

Baseline O-3b: cosine 0.555, humano dice "parecido pero con artifacts al final".
Hipótesis: temperature baja + multi-ref eliminan artifacts y suben cosine.

Mejoras:
1. Multi-referencia: pasar 3 segmentos de Felipe (estabilidad del embedding).
2. temperature=0.1 (más determinístico, menos drift al final).
3. length_penalty=1.0 (default, evitar truncado).
4. repetition_penalty=2.0 (default XTTS, anti-artifact).

Run with: COQUI_TOS_AGREED=1 .venv/bin/python scripts/generate_clone_xtts_optimized.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("COQUI_TOS_AGREED", "1")

# Multi-referencia: 3 segmentos de Felipe (estabilidad embedding).
REF_AUDIOS = [
    "voice_profiles/felipe/xtts_ref_optimal.wav",  # 11s presentación
    "voice_profiles/felipe/pitch_segment_15s_fixed.wav",  # 15s otro segmento
    "voice_profiles/felipe/reference_v2_fixed.wav",  # 14s referencia previa
]

TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."
LANGUAGE = "es"
OUTPUT_PATH = Path("output/experiments/clone_xtts_v2_optimized.wav")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    for ref in REF_AUDIOS:
        if not Path(ref).exists():
            raise SystemExit(f"Reference audio not found: {ref}")

    print("[O-3c] XTTS-v2 optimized (multi-ref + low temp)", flush=True)
    print(f"  REFS      : {len(REF_AUDIOS)} audios", flush=True)
    for r in REF_AUDIOS:
        print(f"    - {r}", flush=True)
    print(f"  TARGET    : {TARGET_TEXT}", flush=True)
    print("  PARAMS    : temperature=0.1, length_penalty=1.0, repetition_penalty=2.0", flush=True)

    print("\nLoading XTTS-v2...", flush=True)
    t0 = time.time()
    # Patch torchaudio.load (torchcodec conflict bypass).
    import soundfile as sf
    import torch
    import torchaudio
    from TTS.api import TTS

    def _sf_load(path: str, **kwargs: Any) -> tuple[torch.Tensor, int]:
        wav, sr = sf.read(str(path), dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        return torch.from_numpy(wav).unsqueeze(0), sr

    torchaudio.load = _sf_load

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"  device: {device}", flush=True)

    tts: Any = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    print(f"  model loaded in {time.time() - t0:.1f}s", flush=True)

    print("\nGenerating (multi-ref + low temp)...", flush=True)
    t = time.time()
    tts.tts_to_file(
        text=TARGET_TEXT,
        speaker_wav=REF_AUDIOS,
        language=LANGUAGE,
        file_path=str(OUTPUT_PATH),
        temperature=0.1,
        length_penalty=1.0,
        repetition_penalty=2.0,
    )
    elapsed = time.time() - t

    info = sf.info(str(OUTPUT_PATH))
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  duration: {info.duration:.2f}s  (O-3b was 5.74s)")
    print(f"  sample_rate: {info.samplerate}")
    print(f"\nListen: afplay {OUTPUT_PATH}")
    print("Measure: .venv/bin/python scripts/measure_speaker_similarity.py")


if __name__ == "__main__":
    main()
