#!/usr/bin/env python3
"""
O-2a experiment: speaker identity verification via speechbrain ECAPA.

Measures cosine similarity between Felipe's reference audio and each COHERENT
clone output (H1a, H1b, H2). Honest auto metric: speaker identity, NOT accent.

Calibration:
  - self-similarity (reference vs reference) ≈ 1.0 upper bound
  - negative control (reference vs preset Serena) should be < 0.5

Threshold (ECAPA-VoxCeleb literature): cosine >= 0.75 = same speaker.

Run with: .venv/bin/python scripts/measure_speaker_similarity.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from speechbrain.inference.speaker import EncoderClassifier

# --- Inputs -----------------------------------------------------------------
REFERENCE = "voice_profiles/felipe/xtts_ref_optimal.wav"
OUTPUTS = {
    "qwen3_h1a_ref_text": "output/experiments/clone_h1a_ref_text_real.wav",
    "qwen3_h1b_trim": "output/experiments/clone_h1b_trim_only.wav",
    "qwen3_h2_embedding": "output/experiments/clone_h2_embedding.wav",
    "xtts_v2_zero_shot": "output/experiments/clone_xtts_v2.wav",
    "xtts_v2_optimized": "output/experiments/clone_xtts_v2_optimized.wav",
}
REPORT_PATH = Path("output/speaker_similarity_report.json")

# Preset speaker for negative control (must be a different speaker).
NEGATIVE_CONTROL_CANDIDATES = [
    "output/experiments/voice_designed.wav",
    "output/experiments/ejemplo_6_voz_disenada.wav",
]


def load_embedding(model: EncoderClassifier, wav_path: str) -> np.ndarray:
    """Load wav at 16kHz mono and extract ECAPA embedding (1, 192)."""
    wav, sr = sf.read(wav_path, dtype="float32")
    # Mono: average channels if stereo.
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    # ECAPA expects 16kHz; resample with simple linear if needed.
    if sr != 16000:
        n_out = round(len(wav) * 16000 / sr)
        indices = np.linspace(0, len(wav) - 1, n_out)
        wav = np.interp(indices, np.arange(len(wav)), wav).astype("float32")
    # speechbrain ECAPA expects shape (batch, time) for 1D conv input.
    signal = torch.from_numpy(wav).unsqueeze(0)
    emb = model.encode_batch(signal)
    # emb shape: (batch=1, time=1, feat=192)
    arr: np.ndarray = emb.squeeze().detach().cpu().numpy()
    return arr


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Loading ECAPA EncoderClassifier...", flush=True)
    model = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="tmp/ecapa",
        run_opts={"device": "cpu"},
    )

    print(f"\nExtracting reference embedding: {REFERENCE}", flush=True)
    ref_emb = load_embedding(model, REFERENCE)

    # Self-similarity upper bound.
    self_sim = cosine(ref_emb, ref_emb)
    print(f"  self-similarity (upper bound): {self_sim:.4f}")

    # Negative control.
    negative_path = next((p for p in NEGATIVE_CONTROL_CANDIDATES if Path(p).exists()), None)
    negative_sim = None
    if negative_path:
        print(f"\nNegative control: {negative_path}", flush=True)
        neg_emb = load_embedding(model, negative_path)
        negative_sim = cosine(ref_emb, neg_emb)
        print(f"  cosine(reference, negative_control): {negative_sim:.4f}  (should be < 0.5)")

    # Clones.
    results = {}
    print("\nClone outputs:", flush=True)
    for name, path in OUTPUTS.items():
        if not Path(path).exists():
            print(f"  [SKIP] {name}: {path} missing")
            continue
        emb = load_embedding(model, path)
        sim = cosine(ref_emb, emb)
        verdict = (
            "SAME-SPEAKER" if sim >= 0.75 else ("AMBIGUOUS" if sim >= 0.60 else "DIFFERENT-SPEAKER")
        )
        results[name] = {"path": path, "cosine_similarity": sim, "verdict": verdict}
        print(f"  {name:30s} cosine={sim:.4f}  {verdict}")

    # Decision summary.
    passing = [n for n, r in results.items() if r["verdict"] == "SAME-SPEAKER"]
    print("\n=== O-2a H-O2a-1 result ===")
    print(f"PASS clones (cosine >= 0.75): {len(passing)}/{len(results)} -> {passing}")
    if passing:
        print("Decision: H-O2a-1 PASS — at least one clone preserves speaker identity")
    else:
        print("Decision: H-O2a-1 FAIL — no clone preserves Felipe's identity")

    report = {
        "reference": REFERENCE,
        "self_similarity_upper_bound": self_sim,
        "negative_control": {"path": negative_path, "cosine_similarity": negative_sim},
        "threshold_same_speaker": 0.75,
        "clones": results,
        "passing": passing,
        "hypothesis": "H-O2a-1 PASS" if passing else "H-O2a-1 FAIL",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
