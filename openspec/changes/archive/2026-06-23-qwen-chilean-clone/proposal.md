# Proposal: Improve Qwen3-TTS Chilean Spanish Voice Cloning Controls

## Problem

The current voice-cloning path can preserve Felipe's timbre, but it may drift toward generic Latin American or Mexican-sounding Spanish. The implementation currently hard-codes `language="Auto"` for cloning and the CLI clone command defaults to the CustomVoice model, even though Qwen reference cloning requires the Base model.

## Goals

- Make clone generation use explicit `Spanish` by default instead of `Auto`.
- Default clone commands to `Qwen/Qwen3-TTS-12Hz-1.7B-Base`.
- Preserve ICL mode as the default by keeping `x_vector_only_mode=False`.
- Expose generation parameters needed for reproducible A/B experiments.
- Log experiment metadata in manifests so perceptual evaluation is not reduced to memory or vibes.
- Keep the domain layer pure and Qwen-specific behavior in infrastructure/scripts.

## Non-goals

- Do not implement fine-tuning or LoRA yet.
- Do not invent unsupported dialect identifiers such as `es-CL`.
- Do not commit generated audio artifacts.
- Do not guarantee Chilean accent preservation; this change improves controls and measurement.

## Delivery Strategy

Ask-on-risk. If the diff grows too large or touches risky model execution paths beyond CLI/script controls, split follow-up work.

