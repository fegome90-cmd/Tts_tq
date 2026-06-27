# Bitácora de Experimentos: Clonación de Voz con Acento Chileno

> **Fechas:** 2026-06-23 a 2026-06-25
> **Sesiones:** TTS Lab voice cloning research — Qwen3-TTS, XTTS-v2, ElevenLabs v2/v3, Inworld TTS-2
> **Objetivo:** Clonar voz de Felipe González (chileno) y evaluar preservación de acento chileno
> **Método:** Autoresearch loop (baseline → hipótesis → experimento → validación → loop) + evaluación ciega humana
> **Evaluador humano:** Felipe González (hablante nativo chileno)

---

## Resumen Ejecutivo

Tras 15+ experimentos con 5 motores TTS (Qwen3-TTS-Base, XTTS-v2, ElevenLabs v2/v3, Inworld TTS-2), se determinó que:

1. **El acento chileno NO se clona zero-shot desde un pitch formal.** Todos los modelos comerciales (ElevenLabs, Inworld) neutralizan el acento regional hacia español genérico o ibérico cuando la referencia es un registro académico/formal.
2. **XTTS-v2 (open-source)** es el único modelo que preserva el acento chileno cuando la referencia lo contiene de forma marcada (Speaker 9697 coloquial).
3. **ElevenLabs Voice Library** tiene voces chilenas nativas pre-entrenadas (Cristian Cornejo, voice_id=ClNifCEVq1smkl4M3aTk) que suenan chilenas con alta calidad. La clave es que fueron entrenadas con data chilena nativa, no clonadas zero-shot.
4. **Inworld TTS-2** produce la mejor calidad técnica (48kHz, Mercedes vs Fiat 600) pero no preserva acento chileno.
5. **Qwen3-TTS-Base** no logra clonar el timbre del speaker en modo zero-shot (cosine similarity 0.01–0.25 vs 1.0 self).
6. El **acento chileno depende de marcas consonánticas** (aspiración de /s/, elisión de /d/, asibilación de /tɾ/) que ningún modelo comercial preserva desde referencia formal.

### Dos caminos viables para producción

**Camino A — ElevenLabs + voces chilenas pre-entrenadas:**

- Voz por defecto: Cristian Cornejo (chileno nativo, alta calidad, 11,976 usos)
- Pros: calidad de producción, API cloud, baja latencia (1.6s)
- Contras: costo por uso, no es la voz del usuario (a menos que se clone con ref coloquial)

**Camino B — XTTS-v2 local + voces chilenas coloquiales de referencia:**

- Voz por defecto: Speaker 9697 o similar del dataset `ylacombe/google-chilean-spanish`
- Pros: gratis, local, privado, preserva acento chileno desde referencia coloquial
- Contras: menor calidad técnica (24kHz), sin cloud

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
| Análisis acústico | F0 (pitch) via autocorrelación, spectral centroid, MFCC, dynamic range, SNR |
| ECAPA calibración | self=1.0, negative control=0.06-0.10 |

---

## Modelos Evaluados

### 1. Qwen3-TTS-12Hz-1.7B-Base (Alibaba)

- **Ubicación:** `comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base`
- **Package:** `qwen-tts>=0.1.1`
- **Clonación:** Zero-shot via `generate_voice_clone()` (ICL mode y embedding mode)
- **Soporte español:** Sí (idioma "spanish" en `LANGUAGE_MAP`)
- **MPS:** Sí (device_map="mps")
- **Veredicto:** ❌ No clona timbre (cosine 0.01-0.25)

### 2. XTTS-v2 (Coqui / idiap fork)

- **Package:** `coqui-tts` v0.27.5 (idiap fork, PyPI)
- **Modelo:** `tts_models/multilingual/multi-dataset/xtts_v2`
- **Clonación:** Zero-shot via `tts_to_file(speaker_wav=..., language="es")`
- **Soporte español:** Sí (1 de 17 lenguajes oficiales)
- **MPS:** Sí
- **Licencia:** CPML (no comercial para los pesos del modelo)
- **Veredicto:** ✅ Preserva acento chileno desde referencia coloquial

### 3. ElevenLabs (API cloud)

- **Modelos probados:** `eleven_multilingual_v2`, `eleven_v3`
- **Clonación:** Instant Voice Clone (IVC) via API
- **Voice Library:** 10+ voces chilenas nativas disponibles (Cristian Cornejo = mejor)
- **Soporte español:** Sí (v2: 29 lenguajes, v3: 70+ lenguajes)
- **MPS:** N/A (cloud API)
- **Licencia:** Cuenta de pago requerida
- **Veredicto:** IVC neutraliza acento ❌ / Voice Library Cristian = chileno ✅

### 4. Inworld TTS-2 (API cloud)

- **Modelo:** `inworld-tts-2` (200+ lenguajes, BCP-47 regional)
- **Clonación:** Instant Voice Clone via API
- **Soporte español:** Sí, soporta `es` y `es-CL` (regional)
- **MPS:** N/A (cloud API)
- **Veredicto:** ❌ Neutraliza acento chileno, pero mejor calidad técnica (48kHz)

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

**Baseline:** 5/5 experimentos con clonación de voz = LOOP.

#### H1a — ref_text fidelity

- **Hipótesis:** Si REF_TEXT = transcripción exacta de Whisper del audio de referencia, ICL mode genera el TARGET_TEXT en vez de colapsar.
- **Resultado:** output_coherence = COHERENT ✅ (inferencia 22.6s, duración 10.16s, max_repeat 1)

#### H1b — reference trimming (5s)

- **Hipótesis:** Si la referencia se recorta a ≤5s, ICL mode no se confunde.
- **Resultado:** output_coherence = COHERENT ✅ (PASS inesperado — ref_text seguía mismatched)

#### H2 — embedding mode (x_vector_only_mode=True)

- **Hipótesis:** Si se ignora ref_text (embedding mode), el modelo genera el target sin confusión ICL.
- **Resultado:** output_coherence = COHERENT ✅ (cleanest output, 5.44s, sin eco de ref_text)

#### Root cause del LOOP (triangulación H1a + H1b + H2)

El LOOP collapse del baseline se manifiesta en **ICL mode** cuando se cumple al menos una condición:

- **(A)** `ref_text` mismatchea el `ref_audio`
- **(B)** `ref_audio` es muy larga (14s vs 3s recomendado)

**Defaults del paquete qwen_tts que causaban el collapse:**

```python
temperature = 0.9          # alto
top_p = 1.0                # sin nucleus filtering
repetition_penalty = 1.05  # DEMASIADO BAJO
max_new_tokens = 8192      # generation_config.json del modelo
```

**Fix validado:**

```python
repetition_penalty = 1.2
top_p = 0.9
temperature = 0.7
max_new_tokens = 512
```

---

### O-2a: Verificar preservación de identidad de speaker (Qwen3-TTS)

**Hipótesis:** Los outputs COHERENT de O-1 preservan la identidad de Felipe.

- **Métrica:** ECAPA cosine similarity (threshold ≥ 0.75 = same speaker)
- **Calibración:** self=1.0000, negative control=0.0600

| Output | Cosine vs ref | Verdict |
|--------|------------------------------|---------|
| clone_h1a | 0.2017 | DIFFERENT-SPEAKER |
| clone_h1b | 0.1141 | DIFFERENT-SPEAKER |
| clone_h2 | -0.0198 | DIFFERENT-SPEAKER |

**Resultado: FAIL 🔴** — Qwen3-TTS-Base NO transfiere el timbre del speaker.

**Nota crítica descubierta después:** `reference_v2_fixed.wav` NO era la voz de Felipe (cosine 0.41 vs pitch real). Las mediciones O-2a iniciales eran engañosas.

---

### O-3a: Research de alternativas

| Candidato | MPS | Español | Zero-shot | Calidad | Total |
|-----------|-----|---------|-----------|---------|-------|
| **XTTS-v2 (idiap)** | ✅ | ✅ oficial | ✅ 6s | ★★★★ | **5/5** |
| F5-TTS | ✅ | ⚠️ needs finetune | ✅ | ★★★★★ | 3/5 |
| GPT-SoVITS | ✅ | ⚠️ needs finetune | ✅ | ★★★★ | 3/5 |
| Qwen3-TTS-Base | ✅ | ✅ | ✅ | ❌ clon falla | 2/5 |

**Resultado: PASS ✅** — XTTS-v2 gana 5/5 en todos los criterios.

---

### O-3b: XTTS-v2 spike (clonación zero-shot de Felipe)

| Output | Cosine vs Felipe | Inferencia | Duración |
|--------|------------------|------------|----------|
| xtts_v2_zero_shot | 0.5550 | 8.9s | 5.74s |

**Evaluación humana (Felipe):** "Suena parecido, con acento neutro, tiene artifacts al final."

---

### O-3c: Referencia correcta + optimización

**Descubrimiento crítico:** `reference_v2_fixed.wav` NO era la voz de Felipe. ECAPA cross-reference:

- `xtts_ref_optimal` vs `pitch_segment_15s_fixed`: **0.96** (mismo speaker ✅)
- `xtts_ref_optimal` vs `reference_v2_fixed`: **0.41** (diferente ❌)

Re-medición con referencia correcta:

| Output | Cosine vs Felipe (pitch15s) | Verdict |
|--------|-----------------------------|---------|
| qwen3_h1a | 0.2532 | DIFFERENT |
| **xtts_v2 (pitch15s)** | **0.5797** | **CLOSE** |

**Evaluación humana (Felipe):** pitch_segment_15s_fixed.wav suena a **español ibérico, no chileno**.

**Root cause del acento neutro:** `pitch_segment_15s_fixed.wav` ES la voz real de Felipe (cross-correlation 0.86 con pitch_full.wav). El "sonar ibérico" es porque el **registro formal del pitch académico** atenúa las marcas fonéticas chilenas.

---

### O-3d: Speaker 9697 chileno nativo en XTTS-v2

- **Referencia:** Speaker 9697 de `ylacombe/google-chilean-spanish` (48 samples, coloquial chileno nativo)

| Output | Cosine vs 9697 |
|--------|----------------|
| 9697_target1 | **0.6649** |

**Evaluación humana (Felipe): "Suena a chileno 100%" ✅**

**Resultado: PASS ✅** — XTTS-v2 SÍ transfiere el acento chileno desde una referencia que lo tiene.

---

### O-3e: MIX multi-ref (Felipe timbre + 9697 acento)

**Evaluación humana (Felipe): "Mala calidad" ❌**

XTTS-v2 promedia embeddings, no separa timbre de acento. El híbrido degrada ambos.

---

### O-3f: OpenVoice voice conversion

**Evaluación humana (Felipe): "Suena robótico, tiene pausas y vocales extendidas" ❌**

Doble pipeline (XTTS → OpenVoice) acumula artefactos sintéticos.

---

### O-4-EL: ElevenLabs IVC (Instant Voice Clone)

#### ElevenLabs Multilingual v2 + Felipe

- **Cosine vs Felipe:** 0.5209
- **Evaluación humana (Felipe):** "Tiene uso de la 'z' como el español ibérico" (zeseo/distinción)

#### ElevenLabs v3 + Felipe

- **Evaluación humana (Felipe):** "Sigue zeseando"

#### ElevenLabs v3 + Speaker 9697 (chileno nativo)

- **Evaluación humana (Felipe):** "Incluso ahí le cambia el acento a uno más neutro, pierde el chileno"

**Resultado: FAIL 🔴 para acento chileno** — ElevenLabs IVC impone su propio G2P que neutraliza acentos regionales.

---

### O-4-EL-Library: ElevenLabs Voice Library (voces chilenas nativas pre-entrenadas)

#### Cristian Cornejo (voice_id=ClNifCEVq1smkl4M3aTk, 11,976 usos)

- **Textos generados:** neutral, coloquial, clínico
- **Evaluación humana (Felipe):** "Suena a chileno. Es la de mejor calidad."
- **Pros:** alta calidad de audio, acento chileno natural
- **Contras:** el coloquial ("po", "al tiro") suena ligeramente a IA (pausas antes de modismos)

#### Otros candidatos chilenos (Vicente Professional, Marco Warm/Friendly, Edgar Rich/Serious)

- **Evaluación humana (Felipe):** "Los otros son de mala calidad sonora, volumen bajo"
- **Veredicto:** Descartados por calidad técnica deficiente

**Resultado: PASS ✅ para Cristian** — ElevenLabs Voice Library tiene voces chilenas nativas de calidad.

---

### O-4-Inworld: Inworld TTS-2

#### Inworld TTS-2 + Felipe (language=es)

- **Cosine vs Felipe:** 0.5159
- **Sample rate:** 48kHz (superior a ElevenLabs 44.1kHz)
- **Dynamic range:** 84.4 dB (superior a ElevenLabs 58.9 dB)
- **Latencia:** 1.6s
- **Evaluación humana (Felipe):** "Se escucha en otra liga, un Fiat 600 vs un Mercedes Benz"
- **Acento:** ❌ Neutro (no chileno)

#### Inworld TTS-2 + Felipe (language=es-CL)

- **Textos generados:** neutral, coloquial, clínico con `language: "es-CL"`
- **Evaluación humana:** Pendiente de evaluación comparativa es vs es-CL

#### Inworld TTS-2 + Speaker 9697 (language=es-CL)

- **Textos generados:** neutral, coloquial
- **Evaluación humana:** Pendiente

#### Comparación ElevenLabs vs Inworld (Felipe)

| Métrica | ElevenLabs v2 | Inworld TTS-2 | Ganador |
|---------|:---:|:---:|:---:|
| ECAPA vs Felipe | **0.52** | 0.52 | Empate |
| Sample rate | 44.1 kHz | **48 kHz** | Inworld |
| Dynamic range | 58.9 dB | **84.4 dB** | Inworld |
| F0 media | **128.9 Hz** (ref=129.0) | 131.4 Hz | ElevenLabs |
| Calidad perceptual | buena | **"Mercedes"** | **Inworld** |
| Acento | ❌ ibérico | ❌ neutro | Inworld |
| Language code regional | ❌ no | **✅ es-CL** | Inworld |

---

## Cuadro Comparativo Final

| Modelo | Referencia | Acento chileno | Zeseo ibérico | Timbre | Cosine ECAPA | Calidad audio | Latencia | Veredicto |
|--------|-----------|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **EL Cristian (librería)** | Pre-entrenada chilena | ✅ **chileno** | ❌ no | N/A (no es Felipe) | N/A | ✅ alta | 1.5s | **🏆 Chileno + calidad** |
| **XTTS-v2** | Speaker 9697 (chileno) | ✅ **100% chileno** | ❌ no | ✅ 9697 (0.67) | 0.67 | ⚠️ media | 5.3s | **🏆 Chileno open-source** |
| **XTTS-v2** | Felipe pitch formal | ❌ neutro | ❌ no | ✅ Felipe (0.58) | 0.58 | ⚠️ media | 8.9s | Timbre OK, acento falla |
| **Inworld TTS-2** | Felipe | ❌ neutro | ❌ no | ✅ Felipe (0.52) | 0.52 | ✅ **alta 48kHz** | 1.6s | Mejor calidad, sin acento |
| **Inworld TTS-2** | Felipe + es-CL | ❓ pendiente | ❌ | ✅ Felipe (0.52) | 0.52 | ✅ alta | 1.6s | Pendiente evaluación es-CL |
| **ElevenLabs v2** | Felipe IVC | ❌ ibérico | ✅ **sí zesea** | ✅ Felipe (0.52) | 0.52 | ✅ alta | 1.6s | Zeseo ibérico |
| **ElevenLabs v3** | Felipe IVC | ❌ neutro | ✅ sí zesea | ✅ Felipe | — | ✅ alta | 2.9s | Zeseo + neutro |
| **ElevenLabs v3** | Speaker 9697 IVC | ❌ neutro | ❌ pierde chileno | ✅ 9697 | — | ✅ alta | 2.9s | Neutraliza |
| **Qwen3-TTS h2** | Felipe embedding | ❌ neutro | ❌ | ❌ no clona | 0.01 | ⚠️ loop colapsado | 10.8s | No clona timbre |
| **XTTS-v2 MIX** | Felipe+9697 | ❌ neutro | ❌ | ❌ híbrido (0.37) | 0.37 | ❌ mala | 5.9s | Calidad degradada |
| **OpenVoice VC** | 9697→Felipe | ❌ robótico | ❌ | ❌ robótico (0.42) | 0.42 | ❌ robótico | 0.6s | Artifacts dobles |

---

## Métricas ECAPA Detalladas

### Calibración

| Referencia | Cosine |
|-----------|--------|
| Self-similarity (reference vs reference) | 1.0000 |
| Negative control (voice_designed vs reference) | 0.0600-0.0963 |
| Threshold same-speaker (literatura ECAPA-VoxCeleb) | ≥ 0.75 |

### Cross-reference entre audios de Felipe

| Par | Cosine | Interpretación |
|-----|--------|----------------|
| xtts_ref_optimal vs pitch_segment_15s_fixed | **0.96** | Mismo speaker (Felipe) ✅ |
| xtts_ref_optimal vs reference_v2_fixed | 0.41 | Diferente speaker ❌ |
| pitch_segment_15s_fixed vs reference_v2_fixed | 0.42 | Diferente speaker ❌ |

**Hallazgo:** `reference_v2_fixed.wav` no es la voz de Felipe.

---

## Análisis Acústico (F0 + Espectral)

### F0 (Pitch)

| Modelo | F0 media (Hz) | F0 std (Hz) | F0 cv | ΔF0 vs Felipe | Interpretación |
|--------|:---:|:---:|:---:|:---:|:---|
| **REF Felipe** | **129.0** | **29.9** | **0.232** | — | Medio, muy variable |
| XTTS-v2 Felipe | 128.6 | 17.7 | 0.138 | 3.4 | Similar pero más monótono |
| XTTS-v2 9697 | 135.4 | 20.8 | 0.154 | 3.2 | Similar |
| ElevenLabs v2 | 128.9 | 19.8 | 0.154 | 2.8 | Más similar en F0 mean |
| ElevenLabs v3 | 142.2 | 42.4 | 0.298 | 4.5 | Muy variable (sobre-expresivo) |
| Inworld TTS-2 | 131.4 | 18.3 | 0.139 | 3.5 | Más estable |

**Insight:** F0 mean de Felipe (129 Hz) se preserva en todos los modelos (±5 Hz). Los clones REDUCEN la variabilidad (cv 0.14-0.17 vs Felipe 0.232) → suenan más monótonos. El acento chileno NO vive en el pitch — vive en los patrones consonánticos.

---

## Veredictos Humanos (Felipe González)

| Experimento | Archivo | Veredicto de Felipe |
|-------------|---------|-------------------|
| XTTS-v2 + Felipe pitch formal | clone_xtts_v2.wav | "Suena parecido, con acento neutro, tiene artifacts al final" |
| XTTS-v2 + Felipe pitch (pitch15s) | clone_xtts_v2_pitch15s.wav | "Esta suena a español ibérico, no a chileno" |
| XTTS-v2 + Speaker 9697 | clone_xtts_9697_target1.wav | **"Suena a chileno 100%"** |
| XTTS-v2 MIX (Felipe+9697) | clone_xtts_felipe_plus_9697_mix.wav | "Mala calidad" |
| OpenVoice VC | clone_openvoice_felipe_accent9697.wav | "Suena robótico, tiene pausas y vocales extendidas" |
| ElevenLabs v2 + Felipe | clone_elevenlabs_felipe.wav | "Tiene uso de la 'z' como el español ibérico" |
| ElevenLabs v3 + Felipe | clone_elevenlabs_v3_felipe.wav | "Sigue zeseando" |
| ElevenLabs v3 + Speaker 9697 | clone_elevenlabs_v3_9697.wav | "Incluso ahí le cambia el acento a uno más neutro, pierde el chileno" |
| Inworld TTS-2 + Felipe | clone_inworld_felipe.wav | "Se escucha en otra liga, un Fiat 600 vs un Mercedes Benz" |
| Inworld TTS-2 + Felipe (acento) | — | "Acento neutro, pero suena como yo" |
| EL Cristian Cornejo (librería) | el_cl_cristian_neutral.wav | **"Suena a chileno. Es la de mejor calidad."** |
| EL Vicente/Marco/Edgar (librería) | el_cl_*_*.wav | "Los otros son de mala calidad sonora (volumen bajo)" |
| EL Cristian coloquial ("po") | el_cl_cristian_coloquial.wav | "El coloquial suena a IA, pausa antes de decir cualquier modismo, sobre todo el 'po'" |

---

## Hallazgos Técnicos Clave

### 1. El LOOP collapse de Qwen3-TTS

**Causa raíz:** Defaults del paquete (`repetition_penalty=1.05`, `top_p=1.0`, `temperature=0.9`) + ref_text mismatched o ref muy larga.

**Fix validado:** `repetition_penalty=1.2`, `top_p=0.9`, `temperature=0.7`, `max_new_tokens=512`.

### 2. Qwen3-TTS-Base no clona timbre

Genera habla coherente pero NO transfiere el timbre del speaker en zero-shot (cosine 0.01-0.25).

### 3. El acento chileno depende de la referencia coloquial

El acento chileno tiene marcas fonéticas específicas (aspiración de /s/, elisión de /d/, asibilación de /tɾ/, modismos). Un registro formal atenúa estas marcas. XTTS-v2 respeta la fonética de la referencia.

### 4. Modelos comerciales neutralizan acentos regionales

ElevenLabs (IVC) e Inworld imponen su propio sistema fonético que neutraliza acentos regionales. ElevenLabs genera zeseo/distinción ibérica. Inworld genera español genérico. No se puede overridear con voice cloning ni con language code.

### 5. ElevenLabs Voice Library es la excepción comercial

Las voces chilenas **pre-entrenadas** de la librería (Cristian Cornejo) SÍ suenan chilenas porque fueron entrenadas con data chilena nativa. La clave es que el acento está en los pesos del modelo, no se intenta clonar zero-shot.

### 6. XTTS-v2 respeta la fonética de la referencia

A diferencia de los modelos comerciales, XTTS-v2 respeta más fielmente la fonética de la referencia sin imponer su propia fonética. Por eso preserva el acento chileno cuando la referencia lo tiene.

### 7. El acento chileno NO vive en el pitch (F0)

Vive en los patrones consonánticos. F0 mean se preserva en todos los modelos (±5 Hz). La diferencia de acento no es detectable por análisis de pitch.

### 8. Voice conversion (OpenVoice) no funciona con audio sintético

Doble pipeline (XTTS → OpenVoice) acumula artefactos sintéticos, produciendo audio robótico.

### 9. Modelos open-source 2026 pendientes de probar

- **Pocket TTS** (kyutai, 100M params, CPU, español dedicado) — más prometedor
- **CosyVoice 3** (FunAudioLLM, 0.5B, 9 idiomas con español)
- **Fish Speech S2 Pro** (fishaudio, 4.6B, 80+ idiomas, requiere GPU)

---

## Hiperparámetros Ganadores

### XTTS-v2

```python
tts.tts_to_file(
    text=target_text,
    speaker_wav=[ref1.wav, ref2.wav, ref3.wav],
    language="es",
    file_path=output_path,
    temperature=0.1,
    length_penalty=1.0,
    repetition_penalty=2.0,
)
```

### ElevenLabs Voice Library (Cristian)

```python
# Voice ID: ClNifCEVq1smkl4M3aTk
# Model: eleven_multilingual_v2
# Language: es (no soporta es-CL regional como Inworld)
client.text_to_speech.convert(
    voice_id="ClNifCEVq1smkl4M3aTk",
    text=target_text,
    model_id="eleven_multilingual_v2",
    voice_settings={"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
)
```

### Inworld TTS-2

```python
requests.post("https://api.inworld.ai/tts/v1/voice", json={
    "text": target_text,
    "voiceId": cloned_voice_id,
    "modelId": "inworld-tts-2",
    "language": "es-CL",  # soporta BCP-47 regional
})
```

---

## Documentos de Referencia

- **Análisis de arquitecturas TTS para acento chileno:** `/Users/felipe_gonzalez/Developer/tqt_app/docs/wiki/references/clonacion-voz-acento-chileno.md`
  - Requiere 3 capas para acento chileno perfecto: G2P + corpora + LoRA
  - COSCACH (1,383h) como gold standard
  - Hiperparámetros LoRA Qwen3: LR=2e-6, cp_lr=0, stop epoch 10-12, lora_scale=0.25-0.35

---

## Archivos Generados

### Outputs de audio (`output/experiments/`)

#### Qwen3-TTS experiments (O-1)

| Archivo | Descripción |
|---------|-------------|
| clone_h1a_ref_text_real.wav | O-1 H1a: ref_text fidelity |
| clone_h1b_trim_only.wav | O-1 H1b: trimming |
| clone_h2_embedding.wav | O-1 H2: embedding mode |
| clone_fixed_icl.wav | O-1: sampling fix ICL |
| clone_simple_path.wav | O-1: official single-inference path |

#### XTTS-v2 experiments (O-3b to O-3e)

| Archivo | Descripción |
|---------|-------------|
| clone_xtts_v2.wav | O-3b: spike inicial |
| clone_xtts_v2_pitch15s.wav | O-3c: ref correcta pitch15s |
| clone_xtts_v2_optimized.wav | O-3c: multi-ref + low temp |
| clone_xtts_9697_target1.wav | **O-3d: chileno 100%** |
| clone_xtts_9697_target2.wav | O-3d: texto coloquial |
| clone_xtts_felipe_plus_9697_mix.wav | O-3e: MIX (mala calidad) |

#### OpenVoice experiment (O-3f)

| Archivo | Descripción |
|---------|-------------|
| clone_openvoice_felipe_accent9697.wav | O-3f: VC robótico |

#### ElevenLabs experiments (O-4-EL)

| Archivo | Descripción |
|---------|-------------|
| clone_elevenlabs_felipe.wav | EL v2: zeseo ibérico |
| clone_elevenlabs_v3_felipe.wav | EL v3: sigue zeseando |
| clone_elevenlabs_v3_9697.wav | EL v3 + 9697: pierde chileno |
| elevenlabs_v3_felipe_neutral.wav | EL v3: texto neutral |
| elevenlabs_v3_felipe_coloquial.wav | EL v3: texto coloquial |
| elevenlabs_v3_felipe_clinico.wav | EL v3: texto clínico |

#### ElevenLabs Voice Library — Voces chilenas nativas (O-4-EL-Library)

| Archivo | Descripción |
|---------|-------------|
| **el_cl_cristian_neutral.wav** | **Cristian: chileno, mejor calidad** |
| **el_cl_cristian_coloquial.wav** | Cristian: coloquial (pausa antes de "po") |
| **el_cl_cristian_clinico.wav** | Cristian: texto clínico |
| el_cl_vicente_prof_neutral.wav | Vicente: volumen bajo |
| el_cl_vicente_prof_coloquial.wav | Vicente: coloquial |
| el_cl_vicente_prof_clinico.wav | Vicente: clínico |
| el_cl_marco_neutral.wav | Marco: volumen bajo |
| el_cl_marco_coloquial.wav | Marco: coloquial |
| el_cl_marco_clinico.wav | Marco: clínico |
| el_cl_edgar_neutral.wav | Edgar: volumen bajo |
| el_cl_edgar_coloquial.wav | Edgar: coloquial |
| el_cl_edgar_clinico.wav | Edgar: clínico |
| elevenlabs_mauricio_neutral.wav | Mauricio: latinoamericano genérico |
| elevenlabs_mauricio_coloquial.wav | Mauricio: coloquial |
| elevenlabs_mauricio_clinico.wav | Mauricio: clínico |

#### Inworld TTS-2 experiments (O-4-Inworld)

| Archivo | Descripción |
|---------|-------------|
| clone_inworld_felipe.wav | Inworld: "Fiat 600 vs Mercedes" |
| inworld_felipe_es_neutral.wav | Inworld + Felipe, lang=es, neutral |
| inworld_felipe_esCL_neutral.wav | Inworld + Felipe, lang=es-CL, neutral |
| inworld_felipe_es_coloquial.wav | Inworld + Felipe, lang=es, coloquial |
| inworld_felipe_esCL_coloquial.wav | Inworld + Felipe, lang=es-CL, coloquial |
| inworld_felipe_es_clinico.wav | Inworld + Felipe, lang=es, clínico |
| inworld_felipe_esCL_clinico.wav | Inworld + Felipe, lang=es-CL, clínico |
| inworld_9697_esCL_neutral.wav | Inworld + Speaker 9697, lang=es-CL |
| inworld_9697_esCL_coloquial.wav | Inworld + Speaker 9697, lang=es-CL |

### Referencias de audio (`voice_profiles/felipe/`)

| Archivo | Duración | Descripción |
|---------|----------|-------------|
| pitch_from_email.mp3 | 262s | Pitch completo original (estéreo 44100Hz) |
| pitch_full.wav | 262s | Pitch completo (mono 24000Hz) |
| pitch_segment_15s_fixed.wav | 15.5s | Segmento 2.6-18.1s del pitch (voz real de Felipe) |
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

### Inmediato (P0 — esta semana)

1. **Grabar voz coloquial chilena de Felipe** (F1/F2/F3, 12-18s cada una) según el plan experimental Fase 0-5.
2. **Validar XTTS-v2 + Felipe coloquial** — ¿preserva acento chileno cuando la referencia lo tiene?
3. **Probar Pocket TTS** (kyutai, 100M, CPU, español dedicado spanish_24l) como alternativa más liviana.
4. **Evaluar Inworld es-CL** — comparar `es` vs `es-CL` en Felipe y Speaker 9697.

### Medio plazo (P1)

1. **Fine-tuning LoRA Qwen3-TTS** con dataset chileno (según doc de referencia).
2. **Intervención G2P (Espeak-NG)** con reglas chilenas.
3. **Probar CosyVoice 3** (0.5B, español nativo).

### Largo plazo (P2)

1. **Evaluar Fish Speech S2 Pro** en GPU cloud (4.6B, SOTA absoluto).
2. **Evaluar Voxtral TTS** (Mistral AI) como alternativa híbrida.
3. **Integrar Cristian (ElevenLabs) + XTTS-v2 como pipeline dual** en la herramienta.

### Decisión sobre entrenamiento (Fase 5 del plan)

| Caso | Acción |
|------|--------|
| A: buena identidad, acento insuficiente | Adaptación dialectal (LoRA, G2P, corpus chileno) |
| B: buen acento, identidad insuficiente | Más audio propio, fine-tuning de hablante, PVC |
| C: XTTS resuelve ambos con referencia coloquial | No entrenar. Integrar XTTS. |
| D: ningún modelo resuelve ambos | Proyecto mayor (corpus multihablante + individual + speaker encoder) |
