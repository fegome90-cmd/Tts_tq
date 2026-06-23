# TTS Lab Project Context

## Stack

- Python 3.12+
- uv
- Typer and Rich for CLI
- qwen-tts, PyTorch, soundfile, Whisper, librosa, noisereduce

## Architecture

The project follows Clean Architecture with a pure domain and impure infrastructure edge.

- `src/tts_lab/domain/`: pure entities, protocols, exceptions.
- `src/tts_lab/application/`: orchestration and DTOs.
- `src/tts_lab/infrastructure/`: Qwen model loading, filesystem/audio side effects, reference processing.
- `scripts/`: experiment and workflow entry points.

Domain code must not import Qwen, torch, soundfile, filesystem IO, or CLI packages.

## Verification

- Unit tests: `uv run pytest tests/unit/ -v`
- Coverage command: `uv run pytest tests/unit/ -v --cov=src --cov-report=term-missing`
- Type check: `uv run mypy src/`
- Lint: `uv run ruff check src/`

## Current SDD Defaults

- Execution mode: automatic
- Artifact store: hybrid
- Delivery strategy: ask-on-risk

