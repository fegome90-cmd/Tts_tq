# O-3a: Zero-shot cloning alternatives research (autoresearch output)

## Context

- Hardware constraint: **MPS only** (no CUDA). Qwen3-TTS-Base zero-shot cloning
  FAILED (O-2a: cosine 0.1-0.2 vs self 1.0). Need alternative.
- Goal: clone Felipe's Chilean Spanish voice preserving speaker identity.
- Baseline: Qwen3-TTS-Base, MPS ✅, Spanish ✅, cloning quality ❌ (cosine ~0.15).

## Decision Matrix

| Candidate | MPS | Spanish | Zero-shot clone | Quality (lit) | Maintenance | License | Total |
|-----------|-----|---------|-----------------|---------------|-------------|---------|-------|
| **XTTS-v2 (idiap fork)** | ✅ prebuilt macOS wheels | ✅ (es is official 1 of 17 langs) | ✅ 6s clip | ★★★★ Coqui Studio-grade | ✅ active fork (v0.27.5 Jan 2026) | CPML (non-commercial weights) | **5/5** ✅ |
| **F5-TTS** | ✅ (Apple Silicon install path documented) | ⚠️ base is zh+en only; needs finetune (vdaular/f5-tts-es exists) | ✅ ref+text | ★★★★★ SOTA paper, WER 1.83 en | ✅ active (v1.1.20 Apr 2026) | CC-BY-NC (weights) | **3/5** ⚠️ |
| **GPT-SoVITS** | ✅ (Apple silicon tested, install.sh --device MPS) | ⚠️ base supports zh/ja/en/ko/yue only; Spanish needs finetune | ✅ 5s clip | ★★★★ few-shot strong | ✅ very active (v4/v2Pro 2026) | MIT | **3/5** ⚠️ |
| Qwen3-TTS-Base (baseline) | ✅ | ✅ | ✅ | ❌ clone fails | ✅ | Apache-2 | 2/5 ❌ |

## Recommendation

**XTTS-v2 (idiap fork, `coqui-tts` PyPI) is the clear winner for O-3b spike.**

### Why XTTS-v2 wins

1. **Spanish is officially supported** (one of 17 languages) — no finetune needed.
2. **Prebuilt macOS wheels** (`coqui-tts` 0.27.4+) — installs cleanly on Apple Silicon.
3. **Battle-tested zero-shot cloning** — 6s reference, Coqui Studio-grade quality.
4. **Active maintenance** — idiap fork actively developed (original coqui-ai abandoned).
5. **Clean Python API**: `tts.tts_to_file(text=..., speaker_wav=ref.wav, language="es")`.

### Why F5-TTS / GPT-SoVITS lose for THIS use case

- Both need **finetuning for Spanish** (base models are zh+en or zh/ja/en/ko/yue).
- Finetuning is compute-heavy and F5-TTS shows Spanish accent bleed in cross-lingual.
- XTTS-v2 supports Spanish out of the box — strictly better for a first spike.

### Viability score

- **XTTS-v2: 5/5** (all 6 criteria green: MPS, Spanish, zero-shot, quality, maintenance, license-OK-for-research)
- F5-TTS: 3/5 (Spanish needs work)
- GPT-SoVITS: 3/5 (Spanish needs work)
- Qwen3-TTS-Base: 2/5 (clone fails — O-2a evidence)

**H-O3a-1 PASS**: at least one candidate (XTTS-v2) scores viability 5/5 on all criteria.

## Decision

**PROCEED to O-3b: XTTS-v2 spike.** Install `coqui-tts`, clone Felipe's voice
with `reference_v2_fixed.wav`, measure speaker cosine via `measure_speaker_similarity.py`,
compare vs Qwen3-TTS-Base baseline (0.1-0.2).

## Falsifier for O-3b

If XTTS-v2 cosine(reference, xtts_output) < 0.60, XTTS-v2 also fails cloning
Felipe → escalate to O-5 (cloud GPU + Qwen3 fine-tune) or accept that Felipe's
reference audio is the problem (not the model).

## Risks for O-3b (documented, not blocking)

- License: CPML restricts commercial use. OK for research/evaluation.
- First-run downloads ~2GB model + license prompt (COQUI_TOS_AGREED=1 to bypass).
- numpy<2.0 pin may be needed (documented trap).
- Reference audio format matters: PCM mono 22050Hz 16-bit recommended.
  Felipe's reference is 24000Hz mono — needs resample for optimal results.

## Deferred candidates (out of scope)

- Parler-TTS, OpenVoice: not researched — XTTS-v2 already meets all criteria.
  If O-3b fails, reconsider.
