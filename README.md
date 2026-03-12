# TTS Lab - Voice Cloning Laboratory

A Python service for Text-to-Speech with voice cloning using Qwen3-TTS models.

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

## Setup

### Requirements

- Python 3.14+
- uv package manager
- Apple Silicon Mac (MPS) or CUDA GPU

### Installation

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest tests/unit/ -v --cov=src --cov-report=term-missing
```

## Usage

### CLI Commands

```bash
# Generate speech with preset voice
uv run tts-generate speech "Hello world!" -l English -s Serena -o output.wav

# Clone voice from reference audio
uv run tts-clone voice reference.wav "Reference text transcription." "Text to speak" -o cloned.wav
```

### Python API

```python
from tts_lab.infrastructure.qwen_client import QwenTTSClient
from tts_lab.infrastructure.file_storage import FileAudioRepository
from tts_lab.application.use_cases import GenerateSpeechUseCase
from tts_lab.application.dto import GenerateSpeechRequest

# Initialize with context manager for automatic cleanup
with QwenTTSClient(
    model_path="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    device="mps"
) as client:
    repo = FileAudioRepository(output_dir="output")
    use_case = GenerateSpeechUseCase(tts_client=client, audio_repo=repo)

    request = GenerateSpeechRequest(
        text="Hola mundo",
        language="Spanish"
    )

    response = use_case.execute(request)
    print(f"Audio saved to: {response.audio_path}")
```

### Voice Cloning

```python
from tts_lab.domain.entities import VoiceProfile

profile = VoiceProfile(
    name="my_voice",
    reference_audio_path="voice_profiles/my_voice/reference.wav",
    reference_text="This is a recording of my voice for cloning."
)

with QwenTTSClient(model_path="...", device="mps") as client:
    audio = client.clone_voice(profile, "This text will be spoken in my voice!")
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_MODEL_PATH` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | Model ID or path |
| `TTS_DEVICE` | `mps` | Device (mps, cuda, cpu) |
| `TTS_OUTPUT_DIR` | `output` | Output directory |
| `TTS_VOICES_DIR` | `voice_profiles` | Voice profiles directory |

## Testing

```bash
# Run unit tests (fast, no model required)
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/unit/ --cov=src --cov-report=html

# Run integration tests (slow, requires model download)
uv run pytest tests/integration/ -v -m slow
```

## ComfyUI Integration

For visual exploration of models, see `comfyui/` directory:

```bash
# Start ComfyUI
cd comfyui
source venv/bin/activate
python main.py --listen 0.0.0.0 --port 8188
```

## Project Structure

```
Tts_tq/
├── src/tts_lab/          # Source code
├── tests/                # Test suite
│   ├── unit/             # Fast unit tests
│   └── integration/      # Slow integration tests
├── scripts/              # CLI entry points
├── voice_profiles/       # Saved voice profiles
├── output/               # Generated audio
├── comfyui/              # ComfyUI integration
└── pyproject.toml        # Project config
```

## Models

- [Qwen3-TTS-12Hz-1.7B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) - Voice cloning
- [Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) - Base model

## License

MIT
