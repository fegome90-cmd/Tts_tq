# TTS Lab - Voice Cloning Laboratory

Claude Code context for the TTS Lab project.

## Project Overview

Python service for Text-to-Speech with voice cloning using Qwen3-TTS models. Supports multilingual speech generation with custom voice profiles.

## Key Technologies

- **Python**: 3.12+
- **Package Manager**: uv
- **ML Framework**: PyTorch (MPS/CUDA)
- **TTS Model**: Qwen3-TTS-12Hz-1.7B-CustomVoice
- **Transcription**: OpenAI Whisper

## Architecture

This project follows **Clean Architecture** with Pure Core/Impure Edge pattern:

```
src/tts_lab/
├── domain/           # PURE - No external dependencies
│   ├── entities.py   # TTSRequest, AudioResult, VoiceProfile
│   ├── protocols.py  # TTSClient, AudioRepository
│   └── exceptions.py # Domain exceptions
│
├── application/      # Orchestration
│   ├── use_cases.py  # GenerateSpeechUseCase
│   └── dto.py        # Request/Response DTOs
│
└── infrastructure/   # IMPURE - Side effects
    ├── qwen_client.py    # Qwen TTS client
    ├── file_storage.py   # Audio file storage
    └── config.py         # Settings
```

**Rule**: Domain layer must have zero external dependencies. Infrastructure implements domain protocols.

## Development Commands

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest tests/unit/ -v --cov=src --cov-report=term-missing

# Run integration tests (slow, requires model)
uv run pytest tests/integration/ -v -m slow

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/

# CLI commands
uv run tts-generate speech "Hello world!" -l English -s Serena -o output.wav
uv run tts-clone voice reference.wav "Transcription." "Text to speak" -o cloned.wav
```

## Testing Standards

- **Framework**: pytest with pytest-asyncio, pytest-cov
- **Coverage Target**: 80%+
- **Markers**: `@pytest.mark.slow` for tests requiring model download
- **Test Organization**: `tests/unit/` (fast) and `tests/integration/` (slow)

## Code Quality

- **Linting**: ruff
- **Type Checking**: mypy (strict mode)
- **Formatting**: Follow PEP 8 conventions
- **Type Annotations**: Required on all function signatures

## Key Files

| File | Purpose |
|------|---------|
| `src/tts_lab/domain/entities.py` | Core domain models |
| `src/tts_lab/domain/protocols.py` | Abstract interfaces |
| `src/tts_lab/infrastructure/qwen_client.py` | TTS client implementation |
| `src/tts_lab/infrastructure/config.py` | Settings (frozen dataclass + `os.getenv`) |
| `scripts/prepare_reference.py` | Normalize and slice reference audio |
| `scripts/transcribe_reference.py` | Generate transcription bundles |
| `scripts/compare_reference_configs.py` | Compare voice cloning configurations |

## Configuration

Environment variables (see `src/tts_lab/infrastructure/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_MODEL_PATH` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | Model ID or path |
| `TTS_DEVICE` | `mps` | Device (mps, cuda, cpu) |
| `TTS_OUTPUT_DIR` | `output` | Output directory |
| `TTS_VOICES_DIR` | `voice_profiles` | Voice profiles directory |

## Voice Cloning Workflow

1. **Prepare reference**: `scripts/prepare_reference.py` - normalize and slice audio
2. **Transcribe**: `scripts/transcribe_reference.py` - generate bundle.json
3. **Compare configs**: `scripts/compare_reference_configs.py` - test different configurations

## Important Patterns

- Use context managers for TTS client (`with QwenTTSClient(...) as client:`)
- Voice profiles stored in `voice_profiles/<speaker>/refs/<input>/`
- Transcription bundles contain: recommended segment, reference text, validation flag

## Project-Specific Rules

- Never commit audio files to git (see `.gitignore`)
- Model downloads are cached by Hugging Face
- Integration tests require `--model-download` or pre-downloaded models
