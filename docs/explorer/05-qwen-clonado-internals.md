# 05 — Internals de clonado con Qwen3-TTS

Documento la superficie real de Qwen3-TTS tal como la usa este repo, los parámetros de sampling disponibles y — lo más importante — **las dos formas distintas en que el repo llama al modelo**, que divergen silenciosamente. Si querés tunear la calidad del clonado, este es el doc para arrancar.

> El paquete es `qwen-tts` (dependencia `qwen-tts>=0.1.1` en `pyproject.toml:16`), que provee `Qwen3TTSModel`. Es **distinto** de los modelos `transformers` de HuggingFace — no se carga con `AutoModel`, sino con `Qwen3TTSModel.from_pretrained(...)`. El motor se baja lazily al primer `from_pretrained` vía el cache de HuggingFace.

## Las dos APIs de `generate_voice_clone` (¡cuidado!)

El repo llama al modelo en **dos formas distintas con el MISMO nombre de método**, y eso es fuente de confusión. No es un bug, es que `Qwen3TTSModel.generate_voice_clone` acepta dos firmas según el camino:

### Camino A — CLI (`qwen_client.py:128-144`, una sola llamada)

```python
wavs, sr = self._model.generate_voice_clone(
    text=text,
    language=language,
    ref_audio=profile.reference_audio_path,   # path al wav
    ref_text=profile.reference_text,
    x_vector_only_mode=x_vector_only_mode,
    temperature=temperature, top_p=top_p, top_k=top_k,
    repetition_penalty=repetition_penalty, max_new_tokens=max_new_tokens,
)
```

Una sola llamada. Le pasás `ref_audio` + `ref_text` + todos los sampling params.

### Camino B — Comparador (`scripts/compare_reference_configs.py:110-119`, dos pasos)

```python
prompt = model.create_voice_clone_prompt(
    bundle.segment_path, bundle.reference_text,
    x_vector_only_mode=(case.mode == "embedding"),
)
wavs, sample_rate = model.generate_voice_clone(
    case.target_text, case.language,
    voice_clone_prompt=prompt,        # ← reutiliza el prompt
)
```

Dos pasos: primero `create_voice_clone_prompt` arma el prompt (con el modo embedding/ICL), después `generate_voice_clone` consume ese prompt. **Sin sampling params** — el comparador no pasa `temperature`/`top_p`/etc.

### Implicaciones

1. **Los dos caminos NO son idénticos ni siquiera con el mismo modelo.** El CLI usa los `DEFAULT_CLONE_*` (ver abajo); el comparador usa defaults internos de `Qwen3TTSModel` que no conocemos desde el código.
2. **El comparador gana en performance** si corrés varios casos: el prompt se construye una vez por segmento y se reutiliza para varios textos. El CLI reconstruye todo cada vez.
3. Cualquier experimento de tuning sobre sampling **solo aplica al CLI**, no al comparador. El comparador no expone esos knobs hoy.

## Parámetros de sampling (`qwen_client.py:16-22`)

Solo el **Camino A** (CLI) los usa. Defaults:

| Constante | Default | Qué controla |
|-----------|---------|--------------|
| `DEFAULT_CLONE_SEED` | `42` | Semilla de sampling. `None` deja el RNG intacto (no determinístico). |
| `DEFAULT_CLONE_TEMPERATURE` | `0.8` | Aleatoriedad. Más alto = más variación (potencialmente más artefactos). |
| `DEFAULT_CLONE_TOP_P` | `0.95` | Nucleus sampling. |
| `DEFAULT_CLONE_TOP_K` | `50` | Top-k sampling. |
| `DEFAULT_CLONE_REPETITION_PENALTY` | `1.1` | Penaliza repetición de tokens. |
| `DEFAULT_CLONE_MAX_NEW_TOKENS` | `2048` | Límite de tokens generados (~2048 samples de audio). |

Estos se exponen como flags del CLI `clone` (`cli.py:58-73`): `--seed`, `--temperature`, `--top-p`, `--top-k`, `--repetition-penalty`, `--max-new-tokens`. El comparador **no** los expone.

## ICL vs Embedding (`x_vector_only_mode`)

El modo de clonado se controla con `x_vector_only_mode`:

| Valor | Modo | Cómo clona |
|-------|------|------------|
| `False` (default) | **ICL** (In-Context Learning) | Usa el par `(ref_audio, ref_text)` como ejemplo in-context. La calidad depende **mucho** de que `ref_text` sea una transcripción precisa del audio (de ahí ISSUE-010). |
| `True` | **Embedding-only** | Extrae solo el vector x del audio de referencia, ignora el texto. Más robusto a transcripciones malas, pero generalmente menos fiel al timbre/estilo. |

Esto mapea directo a la matriz del comparador: `mode="icl"` → `x_vector_only_mode=False`; `mode="embedding"` → `x_vector_only_mode=True` (ver `comparison_manifest.py` y `02-flujo-voice-cloning.md`).

**Cómo elegir**: si tu `bundle.json` viene de Whisper sin corregir (`transcription_validated=false`), el modo embedding suele dar mejores resultados que ICL, porque ICL confunde al modelo si el `reference_text` no matchea el audio. Por eso el comparador corre ambos.

## Reproducibilidad

`_seed_generation` (`qwen_client.py:149-165`) siembra los RNGs **antes de cada `clone_voice`**:

```python
torch.manual_seed(seed)
if cuda.is_available(): cuda.manual_seed_all(seed)
if callable(mps.manual_seed): mps.manual_seed(seed)
```

Detalles:
- **Solo se siembra en `clone_voice`, no en `generate`.** Con mismo input, `clone` es determinístico; `generate` no lo es (salvo que el modelo tenga seeding propio, que no controlamos).
- `seed=None` saltea el seeding (no toca el estado del RNG) — útil si querés variabilidad.
- Los tests mockean este método (`tests/unit/test_qwen_client.py`) con `patch.dict("sys.modules", {"torch": mock_torch})` para no depender de PyTorch real; las ramas por device nunca se ejercitan sobre mps/cuda reales.

## Validación de la referencia (`_validate_voice_profile`, `qwen_client.py:167-180`)

Antes de clonar se valida el `VoiceProfile`:
- El path `reference_audio_path` debe **existir** en disco (`VoiceProfileError` si no).
- El sufijo debe ser `.wav`, `.mp3` o `.flac` (cualquier otra cosa, `VoiceProfileError`).

> Ojo: el check es por extensión, no por contenido. Un `.wav` con encoding raro pasa la validación y puede romper más adentro.

## Conversión a `AudioResult` (`_to_audio_result`, `qwen_client.py:182-204`)

El modelo devuelve `(wavs, sample_rate)` donde `wavs` es una lista de arrays numpy. El helper:
1. Toma `wavs[0]` (ignora el resto).
2. Lo escribe a un `BytesIO` como WAV vía `soundfile`.
3. Calcula `duration_seconds = len(wavs[0]) / sample_rate`.
4. Devuelve `AudioResult(audio_data=bytes, sample_rate, duration_seconds)`.

El formato de salida siempre es WAV (sin importar la extensión del path que pidas después — eso lo decide el `FileAudioRepository`).

## Cheatsheet: qué tunear para qué problema

| Síntoma | Probable causa | Perilla |
|---------|----------------|---------|
| Clone suena distinto cada corrida | No hay seed fijo | `--seed 42` (default del CLI) |
| Clone copia el timbre pero pierde el acento/ritmo | ICL con `ref_text` impreciso | Corregir el `reference_text` o pasar a `--embedding-only` |
| Clone con artefactos / repeticiones | `temperature` muy alto o `repetition_penalty` bajo | Bajar `--temperature` (probar 0.6), subir `--repetition-penalty` (probar 1.2) |
| Audio cortado antes de tiempo | `max_new_tokens` insuficiente para el texto | Subir `--max-new-tokens` |
| Querés comparar configuraciones de sampling | Solo se puede vía CLI | El comparador no expone sampling hoy (ver "Camino B" arriba) |

## Relación con issues

- **ISSUE-004**: los defaults de modelo están fragmentados entre `generate` (`-CustomVoice`) y `clone`/comparador (`-Base`). Acá se ve la consecuencia: los sampling params solo aplican al `clone`/Camino A.
- **ISSUE-006**: `clone_voice` hardcodea `language=DEFAULT_CLONE_LANGUAGE` ("Spanish") como default del método, pero el CLI sí lo deja configurable vía `-l`.
- **ISSUE-010**: el gate `transcription_validated` solo es relevante para ICL; el modo embedding es más tolerante.
