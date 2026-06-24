#!/usr/bin/env python3
"""
O-3b spike: XTTS-v2 zero-shot cloning of Felipe's voice.

Uses the optimal reference (xtts_ref_optimal.wav, 11s mono 22050Hz 16-bit PCM)
prepared from pitch_from_email.mp3. Generates the same TARGET_TEXT used in
O-1 experiments for direct comparison.

Output is measured via scripts/measure_speaker_similarity.py (ECAPA cosine).

Run with: COQUI_TOS_AGREED=1 .venv/bin/python scripts/generate_clone_xtts.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("COQUI_TOS_AGREED", "1")

REF_AUDIO = "voice_profiles/felipe/xtts_ref_optimal.wav"
TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."
LANGUAGE = "es"
OUTPUT_PATH = Path("output/experiments/clone_xtts_v2.wav")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not Path(REF_AUDIO).exists():
        raise SystemExit(f"Reference audio not found: {REF_AUDIO}")

    print("[O-3b] XTTS-v2 zero-shot cloning spike", flush=True)
    print(f"  REF_AUDIO : {REF_AUDIO}", flush=True)
    print(f"  TARGET    : {TARGET_TEXT}", flush=True)
    print(f"  LANGUAGE  : {LANGUAGE}", flush=True)

    print("\nLoading XTTS-v2 model (first run downloads ~2GB)...", flush=True)
    t0 = time.time()
    # Patch torchaudio.load to bypass torchcodec (FFmpeg/PyTorch version conflict).
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

    print("\nGenerating (zero-shot clone)...", flush=True)
    t = time.time()
    tts.tts_to_file(
        text=TARGET_TEXT,
        speaker_wav=REF_AUDIO,
        language=LANGUAGE,
        file_path=str(OUTPUT_PATH),
    )
    elapsed = time.time() - t

    info = sf.info(str(OUTPUT_PATH))
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  output: {OUTPUT_PATH}")
    print(f"  duration: {info.duration:.2f}s")
    print(f"  sample_rate: {info.samplerate}")

    print("\nNext: measure speaker similarity:")
    print("  .venv/bin/python scripts/measure_speaker_similarity.py")


if __name__ == "__main__":
    main()
