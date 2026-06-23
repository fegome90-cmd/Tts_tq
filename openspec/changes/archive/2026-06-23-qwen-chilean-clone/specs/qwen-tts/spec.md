# Spec: Qwen TTS Clone Controls

## Requirements

### Requirement: Explicit clone language

The voice clone path SHALL allow callers to provide the Qwen language used for `generate_voice_clone`.

#### Scenario: Default clone language

- WHEN a clone request does not specify language
- THEN the system SHALL use `Spanish` by default for the clone path.

### Requirement: Base model default for cloning

The CLI clone command SHALL default to `Qwen/Qwen3-TTS-12Hz-1.7B-Base`.

#### Scenario: Clone command default model

- WHEN a user runs the clone command without `--model`
- THEN the command SHALL use the Qwen3-TTS Base model rather than CustomVoice.

### Requirement: ICL mode remains default

The clone path SHALL default to ICL behavior, equivalent to `x_vector_only_mode=False`.

#### Scenario: Default clone mode

- WHEN a user does not request embedding-only mode
- THEN reference text and reference audio SHALL be used to build the voice clone prompt.

### Requirement: Reproducible experiment parameters

Clone and experiment tooling SHOULD expose seed, sampling, max token, and mode parameters.

#### Scenario: Manifest records parameters

- WHEN an experiment generates an output
- THEN the manifest SHOULD record model path, language, reference id/path, transcript validation state, mode, seed, sampling parameters, max token limit, and output path.

