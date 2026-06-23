# Design: Chilean Spanish Clone Control Improvements

## Approach

Keep production-oriented clone behavior inside `QwenTTSClient` and CLI options. Keep matrix experimentation in scripts and manifest-building utilities. Do not add Qwen dependencies to the domain layer.

## Key Decisions

- Use `Spanish` as the default clone language because the target language is known and Qwen does not expose a documented Chilean Spanish identifier.
- Use the Base model as the clone default because `generate_voice_clone` rejects CustomVoice models.
- Keep `x_vector_only_mode=False` as default because ICL carries reference text and acoustic codes, not only speaker identity.
- Treat sampling controls as experiment variables, not accent guarantees.
- Preserve compatibility by adding optional parameters rather than replacing existing public function shapes unless tests require a cleaner DTO.

## Implementation Notes

- Add optional clone parameters to `QwenTTSClient.clone_voice`.
- Update CLI clone options and defaults.
- Reuse `create_voice_clone_prompt` where practical so ICL and embedding-only modes are explicit.
- Extend or add tests using mocks; do not load real Qwen models in unit tests.
- Update README only where it currently misstates clone model behavior.

## Risks

- Unit tests cannot validate Chilean accent quality.
- Integration generation is slow and may require cached models.
- Too many sampling options can confuse users; defaults must remain sane.

