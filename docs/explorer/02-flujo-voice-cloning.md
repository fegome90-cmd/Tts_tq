# 02 — Flujo de voice cloning (pipeline activo)

Este es el flujo que **de verdad se usa hoy**. Tres etapas, cada una con artefactos serializables en JSON. El contrato entre etapas son esos JSONs: `metadata.json` → `bundle.json` → `manifest.json`.

> **⚠️ ESTADO EN DISCO (snapshot 2026-06-23): el pipeline NUNCA se corrió end-to-end en este repo.** No existe ningún `refs/<stem>/`, ningún `bundle.json`, ningún `manifest.json` de comparación. El único `voice_profiles/felipe/metadata.json` que existe usa el **schema legacy** (`name`/`description`/`reference_audio`/`notes`), incompatible con lo que `build_reference_bundle` espera (requiere `speaker` + `segments[]`). Los `.wav` sueltos en `voice_profiles/felipe/` (`reference.wav`, `pitch_seg*.wav`, etc.) son assets pre-WO-002 generados manualmente. Esto significa que este doc describe el **contrato aspiracional del código**, no un estado que hayas podido reproducir leyendo del disco. Para verificarlo, hay que correr el pipeline sobre esos assets.

## Etapa 1 — `scripts/prepare_reference.py`

**Qué hace**: toma una grabación cruda, la normaliza a WAV 24 kHz mono, la corta en segmentos candidatos, calcula métricas simples de calidad y elige un segmento recomendado.

**Inputs** (`scripts/prepare_reference.py` argparse):
- `--input` (requerido): audio crudo (mp3/wav/…).
- `--speaker` (requerido): nombre del perfil.
- `--output-root` (default `voice_profiles`).
- `--segment-seconds` / `--step-seconds` (default `12.0`), `--min-segment-seconds` (default `8.0`), `--max-segments` (default `6`).

**Procesamiento**:
1. `_convert_to_wav()`: `ffmpeg -ar 24000 -ac 1 -acodec pcm_s16le`.
2. `build_reference_segments()` desde `infrastructure/reference_preparation.py`.
3. `pick_best_segment()` elige el recomendado por score.

**Outputs** (bajo `voice_profiles/<speaker>/refs/<input-stem>/`):
- `source.wav` — audio normalizado.
- `segment_01.wav` … `segment_NN.wav` — candidatos.
- `metadata.json` — incluye `speaker`, `normalized_path`, `sample_rate`, parámetros usados, `recommended_segment_index`, `recommended_segment_path` y la lista `segments` con métricas y flag `recommended`.

### Internos de scoring — `compute_segment_metrics` (`reference_preparation.py:57-98`)

El "elige el mejor segmento" no es magia, es una heurística explicables. Las cuatro métricas crudas por segmento:

| Métrica | Cálculo | Significado |
|---------|---------|-------------|
| `speech_ratio` | `mean(|x| > 0.01)` | Fracción de samples por encima del umbral de silencio. |
| `silence_ratio` | `1 − speech_ratio` | Complemento. |
| `clipping_ratio` | `mean(|x| ≥ 0.98)` | Fracción de samples saturados. |
| `rms` | `sqrt(mean(x²))` | Energía media (volumen). |

**La fórmula de score** (`reference_preparation.py:82-89`):

```
score = max(0.0,
    (duration_score · 0.35)      # peso 0.35
  + (speech_ratio  · 0.45)       # peso 0.45 — el más alto
  + (min(rms/0.2, 1.0) · 0.20)   # peso 0.20, normalizado contra 0.2 y clamped
  - (clipping_ratio · 0.75)      # peso 0.75, sustractivo
)
```

Detalles no obvios:
- **`duration_score` es un cliff, no lineal**: vale `1.0` si la duración está entre 8s y 15s, si no `0.5`. Fuera de esa ventana pierde la mitad del aporte.
- **`speech_ratio` es el peso más alto** (0.45) — la heurística prioriza segments con poca pausa sobre segments largos o fuertes.
- **`rms` se normaliza contra `0.2`** y se clampa a `[0,1]`: un rms mayor a 0.2 no suma más.
- **`clipping_ratio` es el único término sustractivo** y su peso (0.75) es el mayor en valor absoluto — puede llevar el score a negativo, por eso el `max(0.0, ...)`.

**`pick_best_segment`** (`reference_preparation.py:179-190`) desempata con un tuple `(score, speech_ratio, −clipping_ratio)`. Si dos segments empatan en score, gana el de mayor `speech_ratio`, y si también empatan, el de menor clipping.

**Ventaneo** (`segment_audio`, `reference_preparation.py:101-144`): ventanas fijas de `segment_seconds` (default 12s) con paso `step_seconds`. Ojo: **`step_seconds` por defecto = `segment_seconds`**, así que no hay overlap por defecto. Se descartan los chunks más cortos que `min_segment_seconds` (8s) y se corta a `max_segments` (6).

## Etapa 2 — `scripts/transcribe_reference.py`

**Qué hace**: transcribe el segmento recomendado (Whisper o texto manual corregido) y arma un bundle reutilizable.

**Inputs** (`transcribe_reference.py` argparse):
- `--metadata` (requerido): path al `metadata.json` de la etapa 1.
- `--model` (default `small`): modelo Whisper.
- `--language` (default `es`): hint para Whisper (ISSUE-007: este default es `es`, distinto del casing del dominio).
- `--reference-text-file`: si lo pasás, usa la transcripción manual corregida y marca el bundle como validado.

**Procesamiento**:
1. Lee `recommended_segment_path` del metadata.
2. Si hay `--reference-text-file` → `transcription_validated=True`, `transcription_source="manual_file"`. Sino → Whisper, `transcription_validated=False`, `transcription_source="whisper:<model>"`.
3. `build_reference_bundle()` desde `infrastructure/reference_bundle.py`.

**Outputs** (en el mismo dir que el metadata):
- `transcription.auto.txt` — transcript automático (solo si fue por Whisper).
- `bundle.json` — bundle serializado.

**Campos del `bundle.json`** (`ReferenceBundle.to_dict`):
- `speaker`, `segment_path`, `source_audio_path`, `reference_text`
- `transcription_source`, `transcription_validated`
- `score`, `recommended_segment_index`, `mode_recommendation`
- `language`, `warnings` (lista, ej. `transcription_not_manually_validated`).

> **Gotcha de calidad** (ISSUE-010): si el bundle viene de Whisper, `transcription_validated=false` y aparece el warning `transcription_not_manually_validated`. La calidad del ICL depende de que el `reference_text` sea preciso, así que el paso de corrección manual importa. El script te lo recuerda al final.

## Etapa 3 — `scripts/compare_reference_configs.py`

**Qué hace**: corre una matriz reproducible de configuraciones desde uno o más bundles y genera audio + manifest.

**Inputs** (`compare_reference_configs.py` argparse):
- `--bundle` (requerido, repetible): paths a `bundle.json`.
- `--text` (requerido): texto objetivo.
- `--text-label` (default `custom`): etiqueta estable para naming de output.
- `--output-dir` (default `output/voice_compare`).
- `--model-path` (default **`Qwen/Qwen3-TTS-12Hz-1.7B-Base`**) — ISSUE-004: distinto del default del CLI.
- `--device` (default `mps`).
- `--include-spanish-icl`: agrega un caso `spanish+icl` por bundle.

**Procesamiento**:
1. `_load_bundle()`: parsea y valida el bundle, verifica que `segment_path`/`source_audio_path` existan.
2. Carga `Qwen3TTSModel.from_pretrained(args.model_path, ...)`.
3. Por cada bundle, `build_default_cases()` (`comparison_manifest.py`) arma los casos base:
   - `<slug>-auto-icl` (`language="auto"`, `mode="icl"`)
   - `<slug>-auto-embedding` (`language="auto"`, `mode="embedding"`)
4. `_run_case()`: construye el voice-clone prompt (con `x_vector_only_mode` para embedding), genera, escribe el WAV y devuelve `ComparisonResult` (status success/failed).

**Outputs** (bajo `output/voice_compare/<slug(text-label)>/`):
- `<case_id>.wav` por cada caso.
- `manifest.json`: `model_path`, `target_text`, `output_dir`, y la lista `cases` con status, output path, duration y error si falló.

**Semántica de salida**: si falla cualquier caso, el script termina con `exit 1` pero el manifest igual se persiste.

## Matriz por defecto

| Caso | language | mode | x_vector_only_mode |
|------|----------|------|--------------------|
| `<slug>-auto-icl` | `auto` | `icl` | `False` |
| `<slug>-auto-embedding` | `auto` | `embedding` | `True` |
| (opcional) `<slug>-spanish-icl` | `spanish` | `icl` | `False` |

## Baseline oficial

El baseline de comparación (modelo, textos canónicos, rubrica subjetiva de timbre/acento/entonación/drift) está en `.pi/plan/baseline-reference.md`. El modelo baseline declarado es **`Qwen3-TTS-12Hz-1.7B-Base`**, consistente con el default del script de comparación. Ver ISSUE-004 e ISSUE-008.
