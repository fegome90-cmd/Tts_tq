# TTS Lab Baseline Reference

## Purpose
This document defines the official baseline for short voice-cloning comparisons in TTS Lab.

It is intentionally small and stable so later WorkOrders can reuse the same model, references, texts, and scoring criteria without re-deciding them.

## Scope
This baseline is valid for:
- short single-sentence cloning comparisons;
- ICL vs embedding comparisons;
- manual listening evaluation.

This baseline is not intended for:
- long-form generation;
- emotional prompting;
- fine-tuning;
- ComfyUI-first workflows.

## Official baseline model
- **Model:** `Qwen3-TTS-12Hz-1.7B-Base`
- **Primary language mode for cloning comparisons:** `auto`
- **Comparison modes:**
  - `ICL` (`x_vector_only_mode=False`)
  - `embedding` (`x_vector_only_mode=True`)

## Official reference candidates
Audio assets are currently local, non-versioned artifacts because `voice_profiles/` is excluded from Git.

### Reference A — primary
- **Path:** `/Users/felipe_gonzalez/Developer/Tts_tq/voice_profiles/felipe/pitch_seg1.wav`
- **Reason:** real speech, cleaner identity cues, best current candidate for accent and natural rhythm.
- **Expected use:** first option for ICL comparisons.

### Reference B — secondary
- **Path:** `/Users/felipe_gonzalez/Developer/Tts_tq/voice_profiles/felipe/reference_v2.wav`
- **Reason:** controlled short recording, useful as a comparison baseline against real speech.
- **Expected use:** secondary option for A/B comparisons.

## Canonical short comparison texts
Use one sentence per generation.

### Text 1 — neutral
> Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones.

### Text 2 — conversational
> Hola, quería contarte algo rápido para escuchar si esta voz suena natural y cercana.

### Text 3 — light Chilean cue
> Ya po, conversemos un momento para ver cómo suena realmente esta voz.

## Minimal subjective rubric (1 to 5)
Score each generated sample in four dimensions.

### 1. Timbre
- **1:** does not sound like Felipe
- **3:** partially resembles Felipe
- **5:** clearly sounds like Felipe

### 2. Accent
- **1:** accent is lost or replaced by generic model accent
- **3:** accent appears in parts but drifts
- **5:** accent is maintained consistently

### 3. Intonation
- **1:** flat or clearly unnatural phrasing
- **3:** partially natural but unstable
- **5:** natural phrasing consistent with Felipe's style

### 4. Drift
- **1:** starts wrong and stays wrong
- **3:** starts well but drifts noticeably
- **5:** remains stable through the full sentence

## Recommended comparison order
For each reference, compare in this order:
1. `auto + ICL`
2. `auto + embedding`
3. optional: `spanish + ICL` only if a targeted language comparison is required

## WO handoff note
WO-002 should treat this document as the source of truth for:
- baseline model;
- reference A/B naming;
- canonical short texts;
- subjective evaluation rubric.

## Known limitations
- References are local, not versioned in Git.
- This baseline is optimized for short samples only.
- Subjective scoring depends on Felipe's listening validation.
