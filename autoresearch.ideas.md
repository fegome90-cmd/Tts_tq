# Autoresearch: Qwen3-TTS Chilean voice clone — root cause of repetition collapse

> Adapted to development mode (no strict quantitative metric). The "metric"
> is a categorical coherence score derived from Whisper transcription of the
> generated audio. Judgment Day guards against biased rubrics.

## Opportunity

O-1: Generate a coherent voice-cloned output in Spanish from Felipe's
reference audio. Baseline: every clone attempt so far degenerates into a
repetition loop ("ligente ligente..." / "hola hola..."). Goal: produce at
least ONE output whose Whisper transcription matches the TARGET_TEXT
semantically (not a loop).

## Primary metric

`output_coherence` — categorical, derived from Whisper-medium transcription
of the generated audio:

| Value | Criterion |
|-------|-----------|
| `LOOP` | Transcription contains a token repeated ≥10 times in sequence |
| `DEGENERATE` | Transcription is non-empty but unintelligible / unrelated to target |
| `PARTIAL` | Transcription contains target keywords but with heavy corruption |
| `COHERENT` | Transcription is semantically equivalent to TARGET_TEXT |

PASS threshold: `COHERENT` or `PARTIAL`. Anything else is FAIL.

## Baseline (already collected)

| Exp | Path | Output_coherence | Evidence |
|-----|------|------------------|----------|
| EXP_1_icl_completo | #2 (voice_clone_prompt) | LOOP | "hola" ×113 |
| EXP_3_temp_baja | #2 | LOOP | "hola" ×118 |
| EXP_4_temp_alta | #2 | LOOP | "hola" ×113 |
| clone_fixed_icl | #2 + sampling fix | LOOP/DEGENERATE | "ligente" ×70 + "la" ×124 |
| clone_simple_path | simple path + sampling fix | LOOP/DEGENERATE | identical to clone_fixed_icl |

baseline_value: output_coherence = LOOP (5/5 experiments collapsed)

## Hypotheses under test (one per experiment cycle)

### H1 — ref_text fidelity (TEST B from prior turn)

HYPOTHESIS: If the REF_TEXT passed to generate_voice_clone exactly matches
  the actual speech in reference_v2_fixed.wav (transcribed by Whisper),
  AND the reference is trimmed to ≤5s, then the ICL mode will generate the
  TARGET_TEXT instead of citing/collapsing the reference.
PREDICTION: output_coherence will change from LOOP to PARTIAL or COHERENT.

### H1a — ref_text fidelity ONLY (v2, post-Judgment-Day-redesign)

HYPOTHESIS: If the REF_TEXT passed to generate_voice_clone is replaced with
  the EXACT Whisper transcription of reference_v2_fixed.wav (keeping the
  same 14s reference audio, no trimming), then ICL mode will generate the
  TARGET_TEXT instead of collapsing.
PREDICTION: output_coherence will change from LOOP to PARTIAL or COHERENT.
EVIDENCE (anchors prediction, resolves JG-003):

- Current REF_TEXT in scripts: "La tecnología de inteligencia artificial
    ha revolucionado la forma en que interactuamos con los dispositivos..."
- Whisper transcription of reference_v2_fixed.wav: "La revolución
    artificial ha revolucionado la forma en que interactuamos con los
    distintos días. Cada día descubrimos nuevas habitaciones..."
- MISMATCH CONFIRMED: script passes a politically-correct sentence that
    the audio never says. ICL mode conditions on ref_text + ref_code; when
    they don't align, the model degenerates.
EXPERIMENT: scripts/generate_clone_h1a.py (real ref_text, full 14s ref,
  same anti-loop sampling kwargs, seed=42) → transcribe → score.
FALSIFIER: if output is still LOOP or DEGENERATE, ref_text mismatch is NOT
  the (sole) cause; escalate to H1b (trim) or H2 (embedding).

### H1b — reference trimming ONLY (v2, runs only if H1a fails)

HYPOTHESIS: If the reference audio is trimmed to ≤5s (closer to README's
  "3-second rapid clone" guidance) keeping the original (mismatched) ref_text,
  the model generates TARGET_TEXT.
PREDICTION: output_coherence will change from LOOP to PARTIAL or COHERENT.
EXPERIMENT: scripts/generate_clone_h1b.py (first 5s of ref, original
  ref_text, same sampling) → transcribe → score.
FALSIFIER: if output is still LOOP, trim alone doesn't fix it.

### H2 — embedding mode (fallback if H1a+H1b fail)

HYPOTHESIS: If x_vector_only_mode=True (ignores ref_text entirely), the
  model generates TARGET_TEXT using only the speaker embedding, bypassing
  ICL confusion.
PREDICTION: output_coherence will change from LOOP to PARTIAL or COHERENT.
EXPERIMENT: scripts/generate_clone_embedding.py → transcribe → score.
FALSIFIER: if output is still LOOP, ICL is not the cause; problem is deeper.

### H3 — model capability control (only if H1+H2 fail)

HYPOTHESIS: If the model can clone an ENGLISH reference (official README
  example) coherently, then the collapse with Felipe's voice is specific to
  Spanish/reference quality, not a model-wide bug.
PREDICTION: english_control_coherence = COHERENT.
EXPERIMENT: run README's English voice-clone example → transcribe → score.
FALSIFIER: if even English collapses, the model itself is broken in this env.

## Opportunity O-2a (rediseñado tras BLOCK O-2 v1)

Speaker identity verification via speechbrain ECAPA — honest auto metric,
NOT accent. Accent evaluation deferred to O-2b (human, one-shot manual).

### Metric

`speaker_cosine_similarity` (continuous float [-1, 1], higher = same speaker)

- Calibration anchors:
  - upper bound: cosine(reference, reference) ≈ 1.0 (self)
  - threshold: cosine >= 0.75 = same speaker (ECAPA-VoxCeleb literature)
  - lower bound: cosine(reference, random_other_speaker) < 0.5

### Hypothesis H-O2a-1

HYPOTHESIS: If the embedding-mode clone (H2) preserves Felipe's speaker
  identity, speaker_cosine_similarity(reference, clone_h2) >= 0.75.
PREDICTION: cosine will be in range [0.75, 0.95] (same speaker, cloned).
FALSIFIER: cosine < 0.60 (different speaker — clone failed identity).

### Experiment

1. Install speechbrain + ECAPA model (`speechbrain/spkrec-ecapa-voxceleb`).
2. Extract embedding for: reference_v2_fixed.wav, clone_h1a, clone_h1b,
   clone_h2 (N=3 COHERENT outputs + 1 reference = 4 embeddings).
3. Compute cosine similarity matrix.
4. Add negative control: cosine(reference, preset_speaker_serena.wav) —
   should be < 0.5 if the tool discriminates.

### Scope

N=3 COHERENT outputs (H1a, H1b, H2) — not just H2.

## Opportunity O-2b (human, deferred — NOT autoresearch loop)

Accent preservation: VOS escuchás los 3 COHERENT outputs + reference, los
puntuás en escala 0-3 (0=foreign, 1=iberian, 2=latam, 3=chilean). Esto es
evaluación humana, no se puede automatizar honestamente.

## Opportunity O-4 (BLOCKED v1 — Judgment Gate)

Generate Felipe's voice via Qwen3-TTS-CustomVoice custom speaker training.
Status: BLOCKED (4 FAIL + 3 SUSPECT in judgment gate v1).

### Blockers to resolve in v2

- JG-001: train.py hardcodes CUDA — needs MPS patch or cloud GPU
- JG-004: .txt naming mismatch (pitch_full_transcription.txt vs expected pitch_full.txt) — ZERO usable pairs
- JG-002: Falsifier creates ambiguous zone — redefine as range
- JG-003: No relative improvement metric for intermediate cosine values

### Additional improvements for v2

- JG-005: No Spanish in language dropdown — use Auto + validate
- JG-006: 5 min training data vs 30 min best practice — recover 5 missing transcriptions via Whisper
- JG-007: Add English control experiment first to prove CustomVoice pipeline works

### Design v2 plan

1. Rename/symlink .txt files to match train.py naming convention
2. Recover 5 missing transcriptions (pitch_seg1/2/3, reference_clean, reference_v2)
3. Patch train.py for MPS or plan cloud GPU (Colab T4)
4. Add English control: train on English reference first
5. Redefine falsifier: cosine < 0.40 (2× baseline 0.20) = FAIL, 0.40-0.74 = PARTIAL, >= 0.75 = PASS
6. Add relative improvement metric: (custom - baseline) / (self - baseline) × 100%
7. Re-run judgment gate v2 after all FAILs resolved
