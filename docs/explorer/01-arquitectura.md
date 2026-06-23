# 01 — Arquitectura actual

## Resumen

TTS Lab es un laboratorio de voice cloning en Python que usa modelos **Qwen3-TTS**. Sigue **Clean Architecture** con el patrón **Pure Core / Impure Edge**, verificado en el código: el dominio no tiene dependencias externas y la infraestructura implementa los protocols del dominio.

Lo primero que tenés que saber: **el flujo activo vive en `scripts/`, no en el CLI**. El CLI (`tts`/`tts-clone`/`tts-generate`) es legacy y está pendiente de refactor (ver `03-log-errores.md` ISSUE-005). Los scripts sí usan los módulos de infraestructura (`reference_preparation`, `reference_bundle`, `comparison_manifest`).

## Capas

### `domain/` — PURA, sin dependencias externas

| Archivo | Responsabilidad |
|---------|-----------------|
| `domain/entities.py` | Entidades inmutables: `TTSRequest` (text/language/speaker/instruct), `AudioResult` (bytes/sample_rate/duration), `VoiceProfile` (name/reference_audio_path/reference_text). |
| `domain/protocols.py` | Protocols (interfaces puras): `TTSClient` (`generate`, `clone_voice`) y `AudioRepository` (`save`, `save_with_hash`, `load`). |
| `domain/exceptions.py` | Jerarquía de excepciones: `TTSError` (base) → `VoiceProfileError`, `ModelLoadError`, `AudioFormatError`. |

Regla cumplida: ningún módulo de `domain/` importa algo fuera de su propio paquete.

### `application/` — Orquestación

| Archivo | Responsabilidad |
|---------|-----------------|
| `application/use_cases.py` | `GenerateSpeechUseCase`: arma un `TTSRequest`, llama `TTSClient.generate`, guarda con `AudioRepository.save_with_hash`. Orquestación pura. |
| `application/dto.py` | DTOs `GenerateSpeechRequest`/`GenerateSpeechResponse` + alias `Language = Literal["Spanish","English","Auto"]`. |

### `infrastructure/` — IMPURA, side effects

| Archivo | Responsabilidad |
|---------|-----------------|
| `infrastructure/qwen_client.py` | `QwenTTSClient`: carga lazy del modelo, `generate()` y `clone_voice()`, context manager, validación de `VoiceProfile`. |
| `infrastructure/file_storage.py` | `FileAudioRepository`: guarda/carga WAV, filenames con hash de contenido. |
| `infrastructure/config.py` | `TTSConfig` (dataclass plano con `os.getenv`, `from_env()`). |
| `infrastructure/reference_preparation.py` | `build_reference_segments`, `pick_best_segment`, `ReferenceSegment` con métricas. Usado por `scripts/prepare_reference.py`. |
| `infrastructure/reference_bundle.py` | `ReferenceBundle` + `build_reference_bundle()`. Serializa el bundle reutilizable para ICL. |
| `infrastructure/comparison_manifest.py` | `ComparisonCase`, `ComparisonResult`, `build_default_cases()`, `build_manifest()`, `slugify()`. Usado por `scripts/compare_reference_configs.py`. |

## Entry points

Definidos en `pyproject.toml` (`[project.scripts]`):

| Comando | Función | Comportamiento real |
|---------|---------|---------------------|
| `tts` | `tts_lab.cli:run_app` | App Typer con subcomandos `clone` y `generate`. |
| `tts-clone` | `tts_lab.cli:run_clone` | `typer.run(clone_voice)` — **un solo comando, sin subcomando**. |
| `tts-generate` | `tts_lab.cli:run_generate` | `typer.run(generate_speech)` — **un solo comando, sin subcomando**. |

> Ojo: el README y AGENTS.md muestran `tts-generate speech ...` y `tts-clone voice ...` como si tuvieran subcomando, pero los entry points `tts-clone`/`tts-generate` usan `typer.run`. Eso es ISSUE-003.

## Diagramas de flujo

### Flujo CLI (legacy)

```
                  ┌───────────── CLI (typer) ─────────────┐
                  │  tts clone   |   tts-clone             │
                  │  tts generate|   tts-generate          │
                  └──────────────┬─────────────────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            │                                         │
   generate_speech (cli.py)                clone_voice (cli.py)
            │                                         │
   GenerateSpeechUseCase            [bypass del application layer]
   (use_cases.py)                   client.clone_voice() + repo.save()
            │                       ← ISSUE-005
   TTSClient.generate                        │
   AudioRepository.save_with_hash            ▼
            │                       QwenTTSClient.clone_voice
            ▼                       (qwen_client.py) → language="Auto"
   QwenTTSClient.generate                  ISSUE-006
   (qwen_client.py)
```

### Flujo scripts (ACTIVO — pipeline de voice cloning)

```
recording (audio crudo)
   │
   ▼
scripts/prepare_reference.py
   │  ffmpeg → WAV 24kHz mono  +  build_reference_segments  +  pick_best_segment
   │
   ├── voice_profiles/<speaker>/refs/<stem>/source.wav
   ├── voice_profiles/<speaker>/refs/<stem>/segment_01.wav ... segment_NN.wav
   └── voice_profiles/<speaker>/refs/<stem>/metadata.json   ← score + recommended
   │
   ▼
scripts/transcribe_reference.py
   │  Whisper (o --reference-text-file manual)  +  build_reference_bundle
   │
   ├── .../transcription.auto.txt   (si fue por Whisper)
   └── .../bundle.json              ← referencia reutilizable
   │
   ▼
scripts/compare_reference_configs.py
   │  Qwen3TTSModel  +  build_default_cases (auto+icl, auto+embedding)
   │
   ├── output/voice_compare/<text-label>/<case_id>.wav
   └── output/voice_compare/<text-label>/manifest.json
```

## Speaker

Hay un único speaker: `voice_profiles/felipe/`. La carpeta `voice_profiles/` está fuera de Git (`.gitignore`), así que los assets de audio son locales y no versionados.

## ComfyUI

`comfyui/` existe como integración alternativa de inferencia (ver `README.md`). No es parte del flujo activo documentado acá.
