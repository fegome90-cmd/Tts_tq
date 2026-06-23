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

- Python 3.12+
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
# Generate speech with a CustomVoice preset voice
uv run tts generate "Hello world!" -l English -s Serena -o output.wav

# Clone voice from reference audio with the Base model (Spanish + ICL by default)
uv run tts clone reference.wav --ref-text "Reference text transcription." --text "Text to speak" -o cloned.wav
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

Voice cloning uses `Qwen/Qwen3-TTS-12Hz-1.7B-Base` by default. The clone path defaults to Spanish and ICL mode (`x_vector_only_mode=False`). Use `--embedding-only` when you explicitly want embedding-only cloning. Preset speaker generation remains on `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`.

```python
from tts_lab.domain.entities import VoiceProfile

profile = VoiceProfile(
    name="my_voice",
    reference_audio_path="voice_profiles/my_voice/reference.wav",
    reference_text="This is a recording of my voice for cloning."
)

with QwenTTSClient(model_path="Qwen/Qwen3-TTS-12Hz-1.7B-Base", device="mps") as client:
    audio = client.clone_voice(
        profile,
        "This text will be spoken in my voice!",
        language="Spanish",
        x_vector_only_mode=False,
    )
```

### Prepare Reference Audio

Use the helper script to normalize a local recording, slice it into candidate
segments, and generate metadata with a recommended segment:

```bash
uv run python scripts/prepare_reference.py \
  --input /path/to/audio.mp3 \
  --speaker felipe \
  --max-segments 3
```

Expected output:
- normalized WAV under `voice_profiles/<speaker>/refs/<input-stem>/source.wav`
- short candidate segments (`segment_01.wav`, etc.)
- `metadata.json` with scores and recommended segment

### Transcribe Prepared Reference

Once a prepared reference exists, generate an initial transcript and reusable
bundle for ICL workflows:

```bash
uv run python scripts/transcribe_reference.py \
  --metadata voice_profiles/felipe/refs/pitch/metadata.json \
  --model small \
  --language es
```

Expected output:
- `transcription.auto.txt` with the automatic transcript
- `bundle.json` with:
  - recommended segment path
  - reference text
  - transcription source
  - validation flag
  - score
  - mode recommendation

To manually correct the transcript, edit the generated text file and rerun with:

```bash
uv run python scripts/transcribe_reference.py \
  --metadata voice_profiles/felipe/refs/pitch/metadata.json \
  --reference-text-file /path/to/corrected.txt
```

### Compare Reference Configurations

Run a small reproducible matrix from one or more bundles:

```bash
uv run python scripts/compare_reference_configs.py \
  --bundle voice_profiles/felipe/refs/pitch/bundle.json \
  --text "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones." \
  --text-label neutral
```

Default comparison matrix per bundle:
- `auto + icl`
- `auto + embedding`

Optional targeted case:
- `--include-spanish-icl`

Expected output:
- generated WAV files under `output/voice_compare/<text-label>/`
- `manifest.json` with per-case status, output path, duration, and errors if any

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

## Baseline for Voice Cloning Comparisons

The official baseline for short cloning comparisons is documented in:

- `.pi/plan/baseline-reference.md`

It defines:
- baseline model;
- reference A/B candidates;
- canonical short texts;
- subjective scoring rubric for timbre, accent, intonation, and drift.

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

- [Qwen3-TTS-12Hz-1.7B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) - Preset/custom voice speech generation
- [Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) - Reference-audio voice cloning

## License

MIT
