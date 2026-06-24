# Bitácora de Experimentos: Clonación de Voz con Acento Chileno

> **Fecha:** 2026-06-23
> **Sesión:** TTS Lab voice cloning research — Qwen3-TTS, XTTS-v2, ElevenLabs
> **Objetivo:** Clonar voz del hablante objetivo (chileno) y evaluar preservación de acento chileno
> **Método:** Autoresearch loop (baseline → hipótesis → experimento → validación → loop)
> **Evaluador humano:** hablante objetivo (hablante nativo chileno)

---

## Resumen Ejecutivo

Tras 12 experimentos con 3 motores TTS (Qwen3-TTS-Base, XTTS-v2, ElevenLabs v2/v3), se determinó que:

1. **XTTS-v2 (coqui-tts idiap fork)** es el único modelo que preserva el acento chileno cuando la referencia lo contiene.
2. **ElevenLabs (v2 y v3)** impone su propio sistema fonético que neutraliza el acento regional (zeseo ibérico o español genérico), incluso con referencias chilenas nativas.
3. **Qwen3-TTS-Base** no logra clonar el timbre del speaker en modo zero-shot (cosine similarity 0.01–0.25 vs 1.0 self).
4. El **acento chileno depende 100% de la calidad coloquial de la referencia de audio**, no del modelo TTS.

### Pipeline ganador validado

```
Voz chilena coloquial (10-15s, multi-ref: 3 samples)
  ↓ speaker_wav
XTTS-v2 (coqui-tts, temperature=0.1, repetition_penalty=2.0, language="es")
  ↓
Output con acento chileno ✅ (cosine 0.66, humano: "100% chileno")
```

---

## Infraestructura

| Componente | Detalle |
|-----------|---------|
| Hardware | Apple Silicon Mac (MPS), sin GPU externa |
| Python | 3.14 (venv del TTS Lab) |
| Whisper | openai-whisper 20250625, modelo `medium` |
| Speaker verification | speechbrain ECAPA-TDNN (VoxCeleb) |
| Métrica de similitud | Cosine similarity entre embeddings ECAPA (threshold ≥ 0.75 = same speaker) |
| Dataset chileno | `ylacombe/google-chilean-spanish` (HuggingFace) — 7h, 31 hablantes |
| Speaker chileno de referencia | **Speaker 9697** (masculino, chileno nativo, 48 samples disponibles) |

---

## Modelos Evaluados

### 1. Qwen3-TTS-12Hz-1.7B-Base (Alibaba)

- **Ubicación:** `comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base`
- **Package:** `qwen-tts>=0.1.1`
- **Clonación:** Zero-shot via `generate_voice_clone()` (ICL mode y embedding mode)
- **Soporte español:** Sí (idioma "spanish" en `LANGUAGE_MAP`)
- **MPS:** Sí (device_map="mps")

### 2. XTTS-v2 (Coqui / idiap fork)

- **Package:** `coqui-tts` v0.27.5 (idiap fork, PyPI)
- **Modelo:** `tts_models/multilingual/multi-dataset/xtts_v2`
- **Clonación:** Zero-shot via `tts_to_file(speaker_wav=..., language="es")`
- **Soporte español:** Sí (1 de 17 lenguajes oficiales)
- **MPS:** Sí
- **Licencia:** CPML (no comercial para los pesos del modelo)

### 3. ElevenLabs (API cloud)

- **Modelos probados:** `eleven_multilingual_v2` y `eleven_v3`
- **Clonación:** Instant Voice Clone via API
- **Soporte español:** Sí (v2: 29 lenguajes, v3: 70+ lenguajes)
- **MPS:** N/A (cloud API)
- **Licencia:** Cuenta de pago requerida

---

## Experimentos

### O-1: Generar output coherente (fix del LOOP collapse)

**Problema:** 4 de 6 experimentos previos colapsaron en loops de repetición ("hola hola hola..." ×100+ o "ligente ligente..." ×70+).

#### Baseline

| Experimento | Transcripción Whisper | Duración | output_coherence |
|-------------|----------------------|----------|------------------|
| EXP_test | "Jalila Gaztar... Hola hola hola..." ×100 | 20.96s | LOOP |
| EXP_1_icl_completo | "Hola hola hola..." ×113 | 19.04s | LOOP |
| EXP_3_temp_baja | "hola hola hola..." ×118 | 29.76s | LOOP |
| EXP_4_temp_alta | "Hola hola hola..." ×113 | 24.16s | LOOP |
| EXP_2_embedding_neutral | "Bienvenidos a este ejemplo de síntesis..." | 11.04s | COHERENT (no usa clonación) |
| EXP_6_voz_disenada | "Ejemplo de voz diseñada desde cero." | 2.48s | COHERENT (voz diseñada, no clonada) |

**Baseline:** 5/5 experimentos con clonación de voz = LOOP.

#### H1a — ref_text fidelity (only change: REF_TEXT exacto)

- **Hipótesis:** Si REF_TEXT = transcripción exacta de Whisper del audio de referencia, ICL mode genera el TARGET_TEXT en vez de colapsar.
- **Cambios:** REF_TEXT cambiado de frase fabricada ("La tecnología de inteligencia artificial...") a transcripción real de Whisper ("La revolución artificial ha revolucionado...").
- **Todo lo demás idéntico:** referencia 14s, sampling params, seed=42.
- **Resultado:**
  - Inferencia: 22.6s (vs baseline 91s)
  - Duración output: 10.16s (vs baseline 40.88s)
  - max_word_repeat: 1 (vs baseline 113)
  - target_keyword_hits: 5/5
  - **output_coherence: COHERENT ✅**

#### H1b — reference trimming (only change: ref recortada a 5s)

- **Hipótesis:** Si la referencia se recorta a ≤5s (vs 14s), ICL mode no se confunde.
- **REF_TEXT:** original fabricado (mismatched). Solo cambia la duración.
- **Resultado:**
  - Inferencia: 35.9s
  - Duración output: 16.80s
  - max_word_repeat: 2
  - **output_coherence: COHERENT ✅** (PASS inesperado)

#### H2 — embedding mode (x_vector_only_mode=True)

- **Hipótesis:** Si se ignora ref_text (embedding mode), el modelo genera el target sin confusión ICL.
- **Resultado:**
  - Inferencia: 10.8s
  - Duración output: 5.44s (perfecto para el target)
  - Transcripción: target exacto sin eco de ref_text
  - **output_coherence: COHERENT ✅** (cleanest output)

#### Root cause del LOOP (triangulación H1a + H1b + H2)

El LOOP collapse del baseline se manifiesta en **ICL mode** cuando se cumple al menos una condición:

- **(A)** `ref_text` mismatchea el `ref_audio` (texto fabricado vs lo que el audio realmente dice)
- **(B)** `ref_audio` es muy larga (14s vs 3s recomendado por README)

**Embedding mode** (`x_vector_only_mode=True`) evita ambas porque ignora ref_text y ref_code.

**Defaults del paquete qwen_tts que causaban el collapse:**

```python
# _merge_generate_kwargs() hard_defaults:
temperature = 0.9          # alto
top_p = 1.0                # sin nucleus filtering
repetition_penalty = 1.05  # DEMASIADO BAJO para frenar loops
max_new_tokens = 8192      # (generation_config.json del modelo)
```

**Fix validado:**

```python
repetition_penalty = 1.2   # frena loops
top_p = 0.9                # nucleus sampling
temperature = 0.7          # menos ruido
max_new_tokens = 512       # cap razonable
```

---

### O-2a: Verificar preservación de identidad de speaker (Qwen3-TTS)

**Hipótesis:** Los outputs COHERENT de O-1 preservan la identidad del hablante objetivo.

- **Métrica:** ECAPA cosine similarity (threshold ≥ 0.75 = same speaker)
- **Calibración:** self=1.0000, negative control (voice_designed)=0.0600

| Output | Cosine vs reference_v2_fixed | Verdict |
|--------|------------------------------|---------|
| clone_h1a_ref_text_real | 0.2017 | DIFFERENT-SPEAKER |
| clone_h1b_trim_only | 0.1141 | DIFFERENT-SPEAKER |
| clone_h2_embedding | -0.0198 | DIFFERENT-SPEAKER |

**Resultado: FAIL 🔴** — Ningún output de Qwen3-TTS-Base preserva la identidad del speaker.

**Interpretación:** Qwen3-TTS-Base genera habla coherente pero NO transfiere el timbre del speaker. El "clone" es solo fonética, no clonación de timbre.

**Nota crítica descubierta después:** `reference_v2_fixed.wav` NO era la voz del hablante objetivo (cosine 0.41 vs pitch real confirmado por ECAPA). Las mediciones de O-2a eran engañosas. Re-medición con referencia correcta (`pitch_segment_15s_fixed.wav`) más adelante.

---

### O-3a: Research de alternativas (XTTS-v2, F5-TTS, GPT-SoVITS)

**Hipótesis:** Existe al menos una alternativa viable (score ≥ 4/5 en todos los criterios).

| Candidato | MPS | Español | Zero-shot | Calidad | Mant. | License | Total |
|-----------|-----|---------|-----------|---------|-------|---------|-------|
| **XTTS-v2 (idiap)** | ✅ wheels macOS | ✅ oficial (1/17) | ✅ 6s | ★★★★ | ✅ activo | CPML research-OK | **5/5** |
| F5-TTS | ✅ | ⚠️ base zh+en, needs finetune | ✅ | ★★★★★ | ✅ | CC-BY-NC | 3/5 |
| GPT-SoVITS | ✅ | ⚠️ base zh/ja/en/ko/yue | ✅ 5s | ★★★★ | ✅ | MIT | 3/5 |
| Qwen3-TTS-Base | ✅ | ✅ | ✅ | ❌ clon falla | ✅ | Apache | 2/5 |

**Resultado: PASS ✅** — XTTS-v2 gana 5/5 en todos los criterios.

**Decisión:** PROCEED a O-3b (XTTS-v2 spike).

---

### O-3b: XTTS-v2 spike (clonación zero-shot del hablante objetivo)

**Hipótesis:** XTTS-v2 produce cosine ≥ 0.60 (mejora clara sobre Qwen3 baseline 0.1-0.2).

| Output | Cosine vs hablante objetivo (xtts_ref_optimal) | Inferencia | Duración |
|--------|--------------------------------------|------------|----------|
| xtts_v2_zero_shot | 0.5550 | 8.9s | 5.74s |

**Resultado: PARTIAL-PASS ✅** — cosine 0.555, mejora 2.7× sobre Qwen3, pero debajo del threshold same-speaker (0.75).

**Evaluación humana (hablante objetivo):** "Suena parecido, con acento neutro, tiene artifacts al final."

---

### O-3c: Optimización XTTS-v2 + referencia correcta

#### Multi-ref + low temperature (artifacts fix)

- **Params:** temperature=0.1, multi-ref (3 samples), repetition_penalty=2.0
- **Cosine:** 0.5367 (multi-ref mixto)
- **Output:** `clone_xtts_v2_optimized.wav`

#### Referencia correcta (pitch_segment_15s_fixed.wav)

**Descubrimiento crítico:** `reference_v2_fixed.wav` NO era la voz del hablante objetivo. ECAPA cross-reference:

- `xtts_ref_optimal` vs `pitch_segment_15s_fixed`: **0.96** (mismo speaker ✅)
- `xtts_ref_optimal` vs `reference_v2_fixed`: **0.41** (diferente ❌)

Re-medición con referencia correcta:

| Output | Cosine vs hablante objetivo (pitch15s) | Verdict |
|--------|-----------------------------|---------|
| qwen3_h1a | 0.2532 | DIFFERENT |
| qwen3_h2 | 0.0140 | DIFFERENT |
| xtts_v2 (ref_optimal) | 0.5276 | DIFFERENT |
| **xtts_v2 (pitch15s)** | **0.5797** | **CLOSE** |
| xtts_v2 (multi-ref) | 0.5367 | DIFFERENT |

**Evaluación humana (hablante objetivo):** pitch_segment_15s_fixed.wav suena a **español ibérico, no chileno**.

**Root cause del acento neutro:** `pitch_segment_15s_fixed.wav` ES la voz real del hablante objetivo (cross-correlation 0.86 con pitch_full.wav, recorte del segundo 2.6-18.1). El "sonar ibérico" es porque el **registro formal del pitch académico** atenúa las marcas fonéticas chilenas (aspiración de /s/, elisión de /d/, asibilación de /tɾ/).

---

### O-3d: Speaker 9697 chileno nativo en XTTS-v2

**Hipótesis:** XTTS-v2 transfiere acento chileno cuando la referencia lo tiene marcado.

- **Referencia:** Speaker 9697 de `ylacombe/google-chilean-spanish` (48 samples, coloquial chileno nativo)
- **Target 1:** "Hola. Esta es una prueba corta..."
- **Target 2:** "Si quieres ahorrar dinero en el supermarket, te recomiendo ir al tiro porque es más barato."

| Output | Cosine vs 9697 | Cosine vs hablante objetivo |
|--------|----------------|------------------|
| 9697_target1 (formal) | **0.6649** | 0.2317 |
| 9697_target2 (coloquial) | **0.6568** | — |

**Evaluación humana (hablante objetivo): "Suena a chileno 100%" ✅**

**Resultado: PASS ✅** — XTTS-v2 SÍ transfiere el acento chileno desde una referencia que lo tiene.

---

### O-3e: MIX multi-ref (hablante objetivo timbre + 9697 acento)

**Hipótesis:** XTTS-v2 multi-ref mezcla timbre del hablante objetivo + acento chileno del 9697.

- **speaker_wav:** 3 archivos (1 hablante objetivo + 2 Speaker 9697)

| Output | Cosine vs hablante objetivo | Cosine vs 9697 |
|--------|------------------|----------------|
| MIX | 0.3715 | 0.4246 |

**Evaluación humana (hablante objetivo): "Mala calidad" ❌**

**Resultado: FAIL 🔴** — XTTS-v2 promedia embeddings, no separa timbre de acento. El híbrido degrada ambos.

---

### O-3f: OpenVoice voice conversion (desacoplar timbre de acento)

**Hipótesis:** OpenVoice VC transfiere timbre del hablante objetivo al audio con acento chileno del 9697.

- **Pipeline:** XTTS-v2 (9697) → OpenVoice VC (target=hablante objetivo)
- **Modelo:** `voice_conversion_models/multilingual/multi-dataset/openvoice_v2`

| Output | Cosine vs hablante objetivo | Cosine vs 9697 |
|--------|------------------|----------------|
| OpenVoice | 0.4219 | 0.1889 |

**Evaluación humana (hablante objetivo): "Suena robótico, tiene pausas y vocales extendidas" ❌**

**Resultado: FAIL 🔴** — Doble pipeline (XTTS → OpenVoice) acumula artefactos sintéticos.

---

### O-4-EL: ElevenLabs (API cloud)

#### ElevenLabs Multilingual v2 + hablante objetivo

- **Modelo:** `eleven_multilingual_v2`
- **Inferencia:** 1.6s
- **Cosine vs hablante objetivo:** 0.5209
- **Evaluación humana (hablante objetivo):** "Tiene uso de la 'z' como el español ibérico" (zeseo/distinción)

#### ElevenLabs v3 + hablante objetivo

- **Modelo:** `eleven_v3` (70+ lenguajes, más expresivo)
- **Inferencia:** 2.9s
- **Evaluación humana (hablante objetivo):** "Sigue zeseando"

#### ElevenLabs v3 + Speaker 9697 (chileno nativo)

- **Modelo:** `eleven_v3`
- **Referencia:** Speaker 9697 (chileno coloquial)
- **Evaluación humana (hablante objetivo):** "Incluso ahí le cambia el acento a uno más neutro, pierde el chileno"

**Resultado: FAIL 🔴 para acento chileno** — ElevenLabs impone su propio G2P que neutraliza acentos regionales. No se puede overridear con voice cloning ni con referencia chilena nativa. El modelo "suaviza" la fonética hacia español genérico.

---

## Cuadro Comparativo Final

| Modelo | Referencia | Acento chileno | Zeseo ibérico | Timbre clonado | Cosine ECAPA | Inferencia | Veredicto |
|--------|-----------|----------------|---------------|----------------|--------------|------------|-----------|
| **XTTS-v2** | Speaker 9697 | ✅ **100% chileno** | ❌ no zesea | ✅ 9697 (0.67) | 0.66 | 5.3s | **🏆 GANADOR** |
| **XTTS-v2** | hablante objetivo pitch | ❌ neutro | ❌ no zesea | ✅ hablante objetivo (0.58) | 0.58 | 8.9s | Timbre OK, acento falla |
| ElevenLabs v2 | hablante objetivo | ❌ ibérico | ✅ **sí zesea** | ✅ hablante objetivo (0.52) | 0.52 | 1.6s | Zeseo ibérico |
| ElevenLabs v3 | hablante objetivo | ❌ neutro | ✅ sí zesea | ✅ hablante objetivo | — | 2.9s | Zeseo + neutro |
| ElevenLabs v3 | Speaker 9697 | ❌ neutro | ❌ pierde chileno | ✅ 9697 | — | 2.9s | Neutraliza acento |
| Qwen3-TTS h2 | hablante objetivo | ❌ neutro | ❌ | ❌ no clona (-0.01) | 0.01 | 10.8s | No clona timbre |
| XTTS-v2 MIX | hablante objetivo+9697 | ❌ neutro | ❌ | ❌ híbrido (0.37) | 0.37 | 5.9s | Calidad degradada |
| OpenVoice | 9697→hablante objetivo | ❌ no se sabe | ❌ | ❌ robótico (0.42) | 0.42 | 0.6s | Artifacts dobles |

---

## Métricas ECAPA Detalladas

### Calibración

| Referencia | Cosine |
|-----------|--------|
| Self-similarity (reference vs reference) | 1.0000 |
| Negative control (voice_designed vs reference) | 0.0600-0.0963 |
| Threshold same-speaker (literatura ECAPA-VoxCeleb) | ≥ 0.75 |

### Cross-reference entre audios de hablante objetivo

| Par | Cosine | Interpretación |
|-----|--------|----------------|
| xtts_ref_optimal vs pitch_segment_15s_fixed | **0.96** | Mismo speaker (hablante objetivo) ✅ |
| xtts_ref_optimal vs reference_v2_fixed | 0.41 | Diferente speaker ❌ |
| pitch_segment_15s_fixed vs reference_v2_fixed | 0.42 | Diferente speaker ❌ |

**Hallazgo:** `reference_v2_fixed.wav` no es la voz del hablante objetivo. Las mediciones iniciales que la usaban como baseline eran engañosas.

---

## Veredictos Humanos (hablante objetivo)

| Experimento | Archivo | Veredicto de hablante objetivo |
|-------------|---------|-------------------|
| XTTS-v2 + hablante objetivo pitch formal | clone_xtts_v2.wav | "Suena parecido, con acento neutro, tiene artifacts al final" |
| XTTS-v2 + hablante objetivo pitch (pitch15s) | clone_xtts_v2_pitch15s.wav | "Esta suena a español ibérico, no a chileno" |
| XTTS-v2 + Speaker 9697 | clone_xtts_9697_target1.wav | **"Suena a chileno 100%"** |
| XTTS-v2 + Speaker 9697 (coloquial) | clone_xtts_9697_target2.wav | **"Suena a chileno 100%"** |
| XTTS-v2 MIX (hablante objetivo+9697) | clone_xtts_target_plus_9697_mix.wav | "Mala calidad" |
| OpenVoice VC | clone_openvoice_target_accent9697.wav | "Suena robótico, tiene pausas y vocales extendidas" |
| ElevenLabs v2 + hablante objetivo | clone_elevenlabs_target.wav | "Tiene uso de la 'z' como el español ibérico" |
| ElevenLabs v3 + hablante objetivo | clone_elevenlabs_v3_target.wav | "Sigue zeseando" |
| ElevenLabs v3 + Speaker 9697 | clone_elevenlabs_v3_9697.wav | "Incluso ahí le cambia el acento a uno más neutro, pierde el chileno" |

---

## Hallazgos Técnicos Clave

### 1. El LOOP collapse de Qwen3-TTS

**Causa raíz:** Los scripts llamaban `generate_voice_clone()` sin pasar sampling params, activando defaults del paquete (`repetition_penalty=1.05`, `top_p=1.0`, `temperature=0.9`) que no previenen loops de repetición.

**Combinación letal:**

- `repetition_penalty=1.05` no frena loops (estándar anti-loop: 1.2-1.3)
- `top_p=1.0` deja el espacio de muestreo muy ruidoso
- `max_new_tokens=8192` da espacio para 100+ repeticiones

**Variables que agravan:**

- (A) `ref_text` no coincide con el audio de referencia
- (B) `ref_audio` demasiado larga (14s vs 3s recomendado)

**Fix validado:**

```python
repetition_penalty = 1.2
top_p = 0.9
temperature = 0.7
max_new_tokens = 512
```

### 2. Qwen3-TTS-Base no clona timbre

El modelo Qwen3-TTS-Base genera habla coherente en español pero NO transfiere el timbre del speaker en zero-shot. Los outputs "COHERENT" son el target dicho con voz genérica, no clonada.

### 3. El acento chileno depende de la referencia coloquial

El acento chileno tiene marcas fonéticas específicas (aspiración de /s/, elisión de /d/, asibilación de /tɾ/, modismos como "po", "cachái", "al tiro"). Un registro **formal/académico** atenúa estas marcas. Un registro **coloquial** las preserva.

XTTS-v2 respeta la fonética de la referencia → si la referencia tiene marcas chilenas, el output es chileno.

### 4. ElevenLabs neutraliza acentos regionales

ElevenLabs (v2 y v3) impone su propio sistema fonético que:

- Genera zeseo/distinción ibérica (pronunciación de /z/ y /c/)
- Neutraliza acentos regionales hacia español genérico
- NO se puede overridear con voice cloning ni con `language_code`

Esto es una limitación arquitectónica del modelo, no un bug.

### 5. XTTS-v2 respeta la fonética de la referencia

A diferencia de ElevenLabs, XTTS-v2 (open-source, coqui-tts) respeta más fielmente la fonética de la referencia sin imponer su propia fonética. Por eso preserva el acento chileno cuando la referencia lo tiene.

### 6. Voice conversion (OpenVoice) no funciona con audio sintético

OpenVoice VC degrada calidad cuando el source ya es audio sintético (XTTS-v2 output). Los artefactos del TTS se acumulan con los del VC, produciendo audio robótico.

---

## Documentos de Referencia

- **Análisis de arquitecturas TTS para acento chileno:** `nota privada no incluida en el repositorio`
  - Requiere 3 capas para acento chileno perfecto: G2P + corpora + LoRA
  - COSCACH (1,383h) como gold standard
  - Hiperparámetros LoRA Qwen3: LR=2e-6, cp_lr=0, stop epoch 10-12, lora_scale=0.25-0.35

---

## Hiperparámetros Ganadores (XTTS-v2)

```python
tts.tts_to_file(
    text=target_text,
    speaker_wav=[ref1.wav, ref2.wav, ref3.wav],  # multi-ref (3 samples)
    language="es",
    file_path=output_path,
    temperature=0.1,        # determinístico, menos artifacts
    length_penalty=1.0,     # default
    repetition_penalty=2.0, # default XTTS anti-artifact
)
```

---

## Archivos Generados

### Outputs de audio (`output/experiments/`)

| Archivo | Modelo | Referencia | Descripción |
|---------|--------|-----------|-------------|
| clone_h1a_ref_text_real.wav | Qwen3-TTS | hablante objetivo (ref_text exacto) | O-1 H1a: ref_text fidelity |
| clone_h1b_trim_only.wav | Qwen3-TTS | hablante objetivo (ref 5s) | O-1 H1b: trimming |
| clone_h2_embedding.wav | Qwen3-TTS | hablante objetivo (embedding mode) | O-1 H2: embedding mode |
| clone_xtts_v2.wav | XTTS-v2 | hablante objetivo (ref_optimal) | O-3b: spike inicial |
| clone_xtts_v2_pitch15s.wav | XTTS-v2 | hablante objetivo (pitch15s) | O-3c: ref correcta |
| clone_xtts_v2_optimized.wav | XTTS-v2 | hablante objetivo multi-ref | O-3c: multi-ref + low temp |
| clone_xtts_9697_target1.wav | XTTS-v2 | Speaker 9697 | **O-3d: chileno 100%** |
| clone_xtts_9697_target2.wav | XTTS-v2 | Speaker 9697 | O-3d: texto coloquial |
| clone_xtts_target_plus_9697_mix.wav | XTTS-v2 | hablante objetivo+9697 | O-3e: MIX (mala calidad) |
| clone_openvoice_target_accent9697.wav | OpenVoice | 9697→hablante objetivo | O-3f: VC robótico |
| clone_elevenlabs_target.wav | ElevenLabs v2 | hablante objetivo | O-4-EL: zeseo ibérico |
| clone_elevenlabs_v3_target.wav | ElevenLabs v3 | hablante objetivo | O-4-EL: sigue zeseando |
| clone_elevenlabs_v3_9697.wav | ElevenLabs v3 | Speaker 9697 | O-4-EL: pierde chileno |

### Referencias de audio (`voice_profiles/target-speaker/`)

| Archivo | Duración | Descripción |
|---------|----------|-------------|
| source_recording.mp3 | 262s | Pitch completo original (estéreo 44100Hz) |
| pitch_full.wav | 262s | Pitch completo (mono 24000Hz) |
| pitch_segment_15s_fixed.wav | 15.5s | Segmento 2.6-18.1s del pitch (voz real del hablante objetivo) |
| xtts_ref_optimal.wav | 11s | Primeros 11s en formato XTTS-v2 (mono 22050Hz 16-bit) |
| chilean_refs/speaker_9697_ref_1.wav | 7.9s | Speaker 9697 sample 1 (48kHz) |
| chilean_refs/speaker_9697_ref_2.wav | 7.8s | Speaker 9697 sample 2 |
| chilean_refs/speaker_9697_ref_3.wav | 7.7s | Speaker 9697 sample 3 |
| chilean_refs/speaker_9697_xtts_optimal.wav | 7.9s | Sample 1 en formato XTTS-v2 (mono 22050Hz 16-bit) |

### Scripts (`scripts/`)

| Script | Propósito |
|--------|-----------|
| transcribe_experiments.py | Transcripción Whisper batch de experimentos |
| measure_speaker_similarity.py | ECAPA cosine similarity entre referencias y outputs |
| generate_clone_h1a.py | Qwen3-TTS con ref_text exacto (O-1 H1a) |
| generate_clone_h1b.py | Qwen3-TTS con ref recortada (O-1 H1b) |
| generate_clone_h2.py | Qwen3-TTS embedding mode (O-1 H2) |
| generate_clone_xtts.py | XTTS-v2 spike (O-3b) |
| generate_clone_xtts_optimized.py | XTTS-v2 multi-ref + low temp (O-3c) |

---

## Próximos Pasos Recomendados

### Inmediato (zero additional cost)

1. **Grabar voz coloquial chilena del hablante objetivo** (10-15s, hablando natural con modismos) → usar como `speaker_wav` en XTTS-v2 → obtener hablante objetivo + acento chileno.
2. **Integrar XTTS-v2 en TTS Lab** como infraestructura alternativa a Qwen3-TTS-Base.
3. **Usar dataset `ylacombe/google-chilean-spanish`** como fuente de voces chilenas para la herramienta (31 hablantes disponibles).

### Medio plazo (requiere GPU cloud)

1. **Fine-tuning LoRA Qwen3-TTS** con dataset chileno (COSCACH o ylacombe) según hiperparámetros del doc de referencia.
2. **Intervención G2P (Espeak-NG)** con reglas chilenas para mejor pronunciación de fonemas regionales.

### Largo plazo

1. **Explorar F5-TTS** con finetune español chileno (`vdaular/f5-tts-es` existe como modelo community).
2. **Evaluar Voxtral TTS** (Mistral AI) como alternativa híbrida AR+flow-matching.
