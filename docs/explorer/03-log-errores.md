# 03 — Log de errores / backlog

Registro de inconsistencias y bugs detectados en el snapshot del 2026-06-23. Ordenado por severidad. Cuando arregles uno, cambiale el **Estado** de `Pendiente` a `Resuelto` y dejá la fecha.

## Tabla maestra

### Alta

| ID | Título | Severidad | Ubicación | Descripción | Impacto | Acción sugerida | Estado |
|----|--------|-----------|-----------|-------------|---------|-----------------|--------|
| ISSUE-004 | `generate` y `clone` no comparten default de modelo ni de path | Alta | `src/tts_lab/cli.py:41` (`clone` → `-Base`); `src/tts_lab/cli.py:134` (`generate` → `-CustomVoice`); `src/tts_lab/infrastructure/config.py:34` (`from_env` → `-CustomVoice`); `scripts/compare_reference_configs.py:45` (`-Base`); `.pi/plan/baseline-reference.md:22` (`-Base`) | Los dos subcomandos del CLI defaultean modelos **distintos**: `clone` a `-Base` (verificado en `cli.py:41`, el help string lo declara explícitamente y `tests/unit/test_cli.py:27` lo asserta), `generate` a `-CustomVoice`. El comparador y el baseline oficial usan `-Base`. Además `generate()` hardcodea `speaker or "Serena"` (`qwen_client.py:85`), que solo aplica a `-CustomVoice` — así que `generate` sobre `-Base` tiene un mismatch latente. | No hay una fuente de verdad del default, y los dos paths del CLI apuntan a modelos distintos sin que se documente. El baseline (`-Base`) solo es reproducible por `clone` y el comparador, no por `generate`. | Centralizar los defaults en `config.py` con dos constantes (`BASE_MODEL` / `CUSTOM_VOICE_MODEL`) y que CLI y scripts lean de ahí. Decidir y documentar el modelo oficial por workflow. | Pendiente |
| ISSUE-005 | `clone` se saltea el application layer | Alta | `src/tts_lab/cli.py` (`clone_voice`) | `clone_voice` (CLI) instancia `QwenTTSClient` y `FileAudioRepository` y llama `client.clone_voice()` + `repo.save()` directamente, sin pasar por ningún use case. `generate` sí enruta por `GenerateSpeechUseCase`. | Clean Architecture se cumple en un solo camino. El path de clonado no es testeable ni orquestable de forma uniforme; cualquier lógica de clonado queda atrapada en el CLI. | Crear `CloneVoiceUseCase` (o extender el existente) con su DTO y hacer que `clone` lo use, igualando a `generate`. | Pendiente |

### Media

| ID | Título | Severidad | Ubicación | Descripción | Impacto | Acción sugerida | Estado |
|----|--------|-----------|-----------|-------------|---------|-----------------|--------|
| ISSUE-001 | Drift de versión de Python | Media | `pyproject.toml:4` (`requires-python`); `pyproject.toml:71` (mypy `python_version`); `.python-version`; `README.md:33`, `AGENTS.md:12`, `CLAUDE.md:12`; venv en 3.14.2 | `requires-python` dice `>=3.12`, mypy valida contra 3.12, y las tres docs (README/AGENTS/CLAUDE) dicen `3.12+`. Pero `.python-version` y el venv real están en 3.14. | Triple fuente de verdad. Quien arme el entorno siguiendo el README queda en 3.12+, pero `.python-version`/venv son 3.14. mypy no detecta usos de APIs de 3.14. | Fijar 3.14 como objetivo: `requires-python = ">=3.14"`, mypy `python_version = "3.14"`, y unificar las tres docs a `3.14+`. | Pendiente |
| ISSUE-002 | `pydantic-settings` es dependencia fantasma | Media | `pyproject.toml:15`; `AGENTS.md:84`; `src/tts_lab/infrastructure/config.py:6,10,33-37` | La dependencia está en `pyproject.toml`, `AGENTS.md` la nombra como implementación de settings, pero `config.py` es un `@dataclass` plano que usa `os.getenv`. grep de `pydantic`/`BaseSettings` en `src/` no da matches. | Doc falsa; peso innecesario del lockfile; induce a pensar que hay validación de settings cuando no la hay. | Quitar `pydantic-settings` de deps y corregir la tabla en `AGENTS.md`; o, si se quiere validación real, migrar `TTSConfig` a `BaseSettings`. | Pendiente |
| ISSUE-003 | Ejemplos de CLI del README están stale | Media | `README.md:53-56`; `AGENTS.md:59-60` (y `CLAUDE.md:59-60`); `src/tts_lab/cli.py:27-29,130-137` | El README/AGENTS muestran `tts-generate speech "Hello"` y `tts-clone voice ref.wav "ref" "text"`, pero `tts-clone`/`tts-generate` usan `typer.run` (sin subcomando) y `clone` toma `-r`/`-t` como options, no texto posicional. | Onboarding engañoso: los comandos del README fallan o se interpretan mal al copiarlos. | Reescribir los ejemplos con la firma real (`uv run tts-clone <ref> -r "..." -t "..." -o ...`, `uv run tts-generate "..." -l English ...`). | Pendiente |
| ISSUE-006 | Campos DTO muertos (mentira arquitectónica) | Media | `src/tts_lab/application/dto.py:23`; `src/tts_lab/application/use_cases.py:37-40`; `src/tts_lab/domain/entities.py:23-24`; `src/tts_lab/cli.py:82-85,113-116`; `src/tts_lab/infrastructure/qwen_client.py:103` | `GenerateSpeechRequest` declara `voice_profile_name`; `TTSRequest` declara `speaker`/`instruct`; el CLI `generate` acepta `--speaker`/`--instruct`. Pero `use_cases.execute` solo reenvía `text`+`language`, y el CLI nunca los pasa al DTO. Además `clone_voice` hardcodea `language="Auto"`. | Los campos existen en la API pública pero se ignoran: pasar `--speaker` no hace nada. Promesa de interfaz que no se cumple. | O conectar los campos de punta a punta (CLI → DTO → TTSRequest → client), o eliminarlos hasta que tengan implementación. | Pendiente |
| ISSUE-007 | Casing de `language` inconsistente entre capas | Media | `src/tts_lab/domain/entities.py:22` y `src/tts_lab/application/dto.py:9` (`"Spanish"/"English"/"Auto"`); `src/tts_lab/infrastructure/comparison_manifest.py:71` (`"auto"`); `scripts/compare_reference_configs.py:165` (`"spanish"`); `src/tts_lab/infrastructure/reference_bundle.py:76` y `scripts/transcribe_reference.py:20` (`"es"`) | No hay un punto único de normalización: el dominio usa Title, el comparador usa lowercase, Whisper/bundle usan código ISO (`es`). | Bug latente: si la API del modelo es sensible a casing, algunos caminos generan con un lenguaje distinto al declarado. Mezclar datos entre capas rompe por casing. | Definir un único enum/normalizador de lenguaje y usarlo en todos los bordes (dominio, comparador, bundle, whisper). | Pendiente |
| ISSUE-008 | Paths absolutos stale en el baseline | Media | `.pi/plan/baseline-reference.md:32,37` | Las referencias A/B apuntan a `/Users/felipe_gonzalez/Developer/Tts_tq/...` pero el repo actual es `Tts_tq_backup` (renombrado). Además usa `felix/` en vez de `felipe/` (typo secundario). | Las referencias baseline apuntan a un path que no existe en esta máquina; clonarlas directo falla. | Actualizar a `Tts_tq_backup` y `felipe/`, o reemplazar por paths relativos al workspace. | Pendiente |
| ISSUE-010 | Gate de calidad `transcription_validated` fácil de saltear | Media | `src/tts_lab/infrastructure/reference_bundle.py:93-94`; `scripts/transcribe_reference.py:65,75`; `src/tts_lab/infrastructure/comparison_manifest.py:73,84` | Los bundles vía Whisper emiten `transcription_validated=false` + warning `transcription_not_manually_validated`, pero nada bloquea correr comparaciones sobre un bundle no validado. La calidad del ICL depende del `reference_text`. | Comparaciones ICL sobre transcripciones automáticas sin corregir pueden parecer válidas en el manifest cuando la entrada era ruidosa. | Documentar el flujo de corrección como obligatorio antes de ICL y/o marcar como `needs-review` los casos derivados de bundles no validados en el manifest. | Pendiente |

### Baja

| ID | Título | Severidad | Ubicación | Descripción | Impacto | Acción sugerida | Estado |
|----|--------|-----------|-----------|-------------|---------|-----------------|--------|
| ISSUE-009 | Rama muerta `mode_recommendation` | Baja | `src/tts_lab/infrastructure/reference_bundle.py:98` | `mode_recommendation = "icl"` se asigna incondicionalmente; el campo existe pero nunca se deriva de verdad. | Campo que siempre vale lo mismo; ruido en el bundle. (El worktree en curso ya está tocando este módulo.) | Derivar el valor desde reglas reales (score, validated, duración) o eliminar el campo. | Pendiente |
| ISSUE-011 | `tests/integration/` vacío | Baja | `tests/integration/__init__.py`; `README.md:189`, `AGENTS.md:50`, `CLAUDE.md:50`; `pyproject.toml:61-64` (markers) | La carpeta de integración solo tiene `__init__.py`, pero README/AGENTS/CLAUDE documentan correr `pytest tests/integration/ -m slow` y los markers `slow`/`integration` están definidos. | Doc aspiracional: los comandos documentados no corren nada. | O agregar al menos un test de integración real (marcado `slow`), o aclarar en la doc que no existen todavía. | Pendiente |
| ISSUE-012 | Scripts `generate_*.py` muertos | Baja | `scripts/generate_improved_clone.py:9-10`, `generate_pitch_clones.py`, `generate_voice_case.py`, `generate_voice_from_pitch.py`, `generate_voice_matrix.py:10-11,152-153` | Cinco scripts experimentales con paths hardcoded y ejecución top-level, superseded por el pipeline de workorders (prepare/transcribe/compare). | Mantienen ruido en `scripts/`; riesgo de que alguien los corra pensando que son activos. | Moverlos a `scripts/legacy/` o borrarlos una vez confirmado que no aportan nada. | Pendiente |

## Notas detalladas (severidad Alta)

### ISSUE-004 — Defaults de modelo fragmentados entre paths

Hay tres defaults en juego, divididos por path:

- **`-Base`** — `clone` (`cli.py:41`, el help string lo declara y `test_cli.py:27` lo asserta), el comparador (`compare_reference_configs.py:45`), y el baseline oficial (`baseline-reference.md:22`).
- **`-CustomVoice`** — `generate` (`cli.py:134`) y `config.from_env` (`config.py:34`).
- Mismatch latente: `generate()` en `qwen_client.py:85` hace `speaker or "Serena"`, concepto que solo existe en `-CustomVoice`. Si corrés `generate` con `-Base` (cambiando el flag), el `speaker` se pasa igual pero el modelo lo ignora o rompe.

El problema no es que `-Base` esté mal para clonar (es lo correcto: el baseline oficial lo declara así). El problema es que **no hay una sola fuente de verdad** y los dos subcomandos del CLI divergen silenciosamente. Una corrida `generate` y una `clone` sobre el mismo texto no son comparables.

### ISSUE-005 — `clone` se saltea el application layer

`generate_speech` (CLI) construye `GenerateSpeechUseCase` y lo ejecuta. En cambio `clone_voice` (CLI) hace:

```python
with QwenTTSClient(...) as client:
    profile = VoiceProfile(...)
    audio = client.clone_voice(profile, text)   # directo al client
    repo = FileAudioRepository(...)
    repo.save(audio, output.name)               # directo al repo
```

No existe un use case de clonado. Eso rompe la simetría arquitectónica y deja al path de clonado sin el punto de orquestación que sí tiene el path de generación. Cualquier lógica futura (logging, normalización de lenguaje, reintentos) terminaría duplicada o metida en el CLI. Crear `CloneVoiceUseCase` con su DTO/request lo alinea con `GenerateSpeechUseCase` y desbloquea testear el clonado sin Typer.
