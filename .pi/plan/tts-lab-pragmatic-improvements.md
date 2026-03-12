# Plan: TTS Lab Pragmatic Improvements

## 1. Restatement de requerimientos

Objetivo: mejorar el sistema actual de voice cloning de `Tts_tq` de forma pragmática, priorizando cambios de bajo/medio esfuerzo y alto impacto sobre fidelidad, acento, entonación y reproducibilidad.

Restricciones explícitas:
- Este plan no implementa cambios.
- Toda tarea con complejidad alta, alto riesgo o tendencia a sobreingeniería se deja como proyecto futuro.
- ComfyUI se considera herramienta de exploración, no el core del sistema.
- Debe respetarse la arquitectura actual del proyecto (Clean Architecture) y mantener el dominio puro.

Resultado esperado del proyecto inmediato:
- Mejor proceso de preparación de referencias.
- Mejor proceso de comparación de configuraciones.
- Menos deriva en frases largas.
- Mejor trazabilidad de experimentos.

Resultado fuera de alcance inmediato:
- Fine-tuning completo.
- Servicio persistente de inferencia.
- UI compleja de evaluación.
- Automatización extensa sobre ComfyUI.

### Criterios operativos de corte de alcance
Un cambio se considera demasiado complejo para este ciclo y debe moverse a "proyecto futuro" si cumple cualquiera de estos criterios:
- requiere entrenamiento, fine-tuning o datasets curados nuevos;
- introduce un servicio persistente, cola de jobs o infraestructura residente;
- agrega una UI nueva o una integración avanzada con ComfyUI como frontend oficial;
- exige optimización profunda de runtime antes de demostrar mejora real de calidad;
- cruza demasiadas capas a la vez sin entregar una mejora perceptible y validable en una sola iteración.

### Responsables por fase
- Implementación técnica de cada fase: agente ejecutor del proyecto.
- Validación subjetiva de audio (timbre, acento, entonación): Felipe.
- Decisión de corte de alcance y envío a futuro: Felipe, con recomendación técnica del agente.
- Criterio de cierre por fase: cada fase debe dejar un entregable verificable y no depender de una futura fase para demostrar valor básico.

### Exclusiones confirmadas por el usuario
Quedan explícitamente fuera del ciclo inmediato y pasan a proyecto futuro:
- servicio persistente de inferencia;
- ranking automático por embeddings / speaker similarity;
- UI dedicada de evaluación;
- fine-tuning / speaker adaptation;
- integración avanzada con ComfyUI como frontend oficial.

---

## 2. Supuestos y preguntas abiertas

### Supuestos
- El proyecto base a modificar es `Tts_tq`, no OpenClaw.
- El modelo principal para clonación seguirá siendo `Qwen3-TTS-12Hz-1.7B-Base`.
- El flujo principal seguirá siendo CLI/Python, con ComfyUI como apoyo opcional.
- La prioridad es mejorar calidad y flujo de trabajo de laboratorio, no productizar un servicio multiusuario.
- Felipe puede hacer validación subjetiva de audios generados durante el ciclo de comparación.

### Preguntas abiertas
- ¿Se quiere dejar un único flujo oficial (`tts ...`) o se aceptan scripts auxiliares en `scripts/` como etapa intermedia?
- ¿La referencia principal oficial debe salir de `pitch.mp3` o de futuras grabaciones reales controladas?
- ¿Se quiere registrar evaluación subjetiva dentro del repo (JSON/CSV) o basta con manifests técnicos por corrida?

### Decisión provisional para no bloquear el plan
- Mantener scripts auxiliares solo como puente corto; el flujo objetivo debe converger en la CLI del proyecto.
- Tomar `pitch_seg1` y referencias reales limpias como baseline inicial.
- Guardar manifests técnicos y dejar scoring subjetivo como opcional, sin UI dedicada.

---

## 3. Fases de implementación (paso a paso)

## Fase 0 — Alineación y limpieza mínima del alcance
**Complejidad:** LOW  
**Tiempo estimado:** 0.5 día

1. Confirmar baseline oficial de clonación:
   - modelo base
   - referencias válidas
   - texto canónico corto de comparación
2. Congelar un set pequeño de configuraciones comparables:
   - `auto + icl`
   - `auto + embedding`
   - referencia real A
   - referencia real B
3. Documentar qué se considera éxito:
   - mejor timbre
   - menor deriva de acento
   - mejor entonación

### Entregable
- Baseline simple y repetible para comparar mejoras.

---

## Fase 1 — Pipeline de preparación de referencia
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 a 1.5 días

1. Crear flujo para preparar audio de referencia:
   - conversión a WAV mono 24 kHz / 16-bit
   - trimming inicial
   - segmentación en clips de 8–15s
   - limpieza ligera opcional (no agresiva)
2. Agregar scoring simple por segmento:
   - duración válida
   - speech ratio
   - silencio excesivo
   - clipping/saturación básica
3. Generar artefacto de salida por speaker:
   - segmentos
   - metadata
   - segmento recomendado

### Alcance pragmático
- No usar DSP complejo ni modelos avanzados de calidad de audio.
- No hacer diarization ni separación musical sofisticada.

### Entregable
- Un comando o script consistente para preparar referencias reutilizables.

---

## Fase 2 — Transcripción y bundle de referencia
**Complejidad:** MEDIUM  
**Tiempo estimado:** 0.5 a 1 día

1. Ejecutar Whisper sobre el segmento elegido.
2. Guardar transcripción junto al audio.
3. Permitir corrección manual simple del texto transcrito.
4. Crear un bundle de referencia reutilizable:
   - `ref_audio`
   - `ref_text`
   - metadata de origen
   - score de calidad

### Alcance pragmático
- No construir editor visual.
- No meter versionado complejo de datasets.

### Entregable
- Referencias listas para usar en ICL de forma reproducible.

---

## Fase 3 — Comparador de configuraciones
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 día

1. Definir textos canónicos de comparación:
   - corto neutro
   - corto conversacional
   - corto con chilenismo
2. Ejecutar una matriz pequeña de casos:
   - 4 a 6 combinaciones máximo
3. Guardar salidas en una carpeta estructurada.
4. Emitir manifest JSON por corrida con:
   - referencia
   - texto
   - language
   - modo (`icl` / `embedding`)
   - duración
   - output path

### Alcance pragmático
- No hacer ranking automático con embeddings todavía.
- No generar dashboards HTML.

### Entregable
- Comparación A/B reproducible sin depender de memoria manual.

---

## Fase 4 — Generación por frases cortas para reducir deriva
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 día

1. Crear estrategia de chunking por oraciones.
2. Generar cada oración por separado.
3. Concatenar con pausas controladas.
4. Mantener metadata por chunk.

### Alcance pragmático
- Sin prosody alignment avanzada.
- Sin crossfades complejos ni edición tipo DAW.

### Entregable
- Flujo estable para textos medianos/largos con menor deriva de voz/acento.

---

## Fase 5 — Consolidación en CLI del proyecto
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 a 1.5 días

1. Reducir dependencia de scripts experimentales dispersos.
2. Llevar los flujos ganadores a comandos más claros del proyecto.
3. Mantener `scripts/` solo como utilidades temporales o de soporte.
4. Actualizar README y ejemplos.

### Alcance pragmático
- No rediseñar todo el dominio.
- No crear una jerarquía excesiva de casos de uso si el flujo sigue siendo simple.

### Entregable
- Flujo principal coherente y mantenible.

---

## Fase 6 — Validación final
**Complejidad:** LOW  
**Tiempo estimado:** 0.5 día

1. Validar unit tests existentes.
2. Agregar tests puntuales a nuevas piezas deterministas.
3. Ejecutar una corrida real de comparación.
4. Documentar baseline ganadora.

### Entregable
- Sistema con baseline reproducible y criterio claro de uso.

---

## 3.1 Reglas de ejecución del trabajo

- Ejecutar cambios por fase o subfase, no como megapatch transversal.
- Mantener cambios atómicos y medibles; idealmente una preocupación principal por iteración.
- No mover lógica al core hasta validar primero el flujo con bajo riesgo.
- Si una fase crece más de lo esperado, dividirla antes de tocar múltiples módulos a la vez.
- Cada fase debe cerrar con una evidencia concreta: comando reproducible, manifest, test o documentación actualizada.

## 4. Archivos candidatos a modificar

### Código fuente
- `src/tts_lab/cli.py`
- `src/tts_lab/application/dto.py`
- `src/tts_lab/application/use_cases.py`
- `src/tts_lab/domain/entities.py`
- `src/tts_lab/domain/protocols.py`
- `src/tts_lab/domain/exceptions.py`
- `src/tts_lab/infrastructure/config.py`
- `src/tts_lab/infrastructure/file_storage.py`
- `src/tts_lab/infrastructure/qwen_client.py`

### Scripts / utilidades
- `scripts/record_reference.sh`
- `scripts/record_reference_v2.sh`
- `scripts/generate_voice_case.py`
- `scripts/generate_voice_matrix.py`
- `scripts/generate_pitch_clones.py`
- `scripts/generate_improved_clone.py`
- `scripts/generate_voice_from_pitch.py`
- posible nuevo archivo: `scripts/prepare_reference.py`

### Tests
- `tests/unit/test_cli.py`
- `tests/unit/test_qwen_client.py`
- posibles nuevos tests:
  - `tests/unit/test_reference_preparation.py`
  - `tests/unit/test_generation_manifest.py`
  - `tests/unit/test_text_chunking.py`

### Documentación
- `README.md`
- posible nuevo doc: `docs/reference-workflow.md`

### Datos / artefactos
- `voice_profiles/felipe/`
- `output/voice_matrix/`
- posible carpeta de metadata: `voice_profiles/felipe/refs/`

---

## 5. Riesgos + mitigaciones

### Riesgo 1: sobreingeniería del laboratorio
**Riesgo:** convertir un flujo experimental en una plataforma demasiado compleja.  
**Mitigación:** limitar el scope inmediato a preparación de referencia, comparación y chunking.

### Riesgo 2: mezclar demasiado scripts experimentales con el core
**Riesgo:** degradar mantenibilidad.  
**Mitigación:** usar scripts como puente corto y mover solo lo validado a `src/tts_lab/`.

### Riesgo 3: cambios no deterministas por depender del modelo
**Riesgo:** tests frágiles.  
**Mitigación:** testear solo lógica determinista; aislar integración real como pruebas lentas.

### Riesgo 4: limpiar demasiado el audio y perder identidad vocal
**Riesgo:** referencias “limpias” pero menos fieles.  
**Mitigación:** limpieza ligera y siempre conservar audio original + derivado.

### Riesgo 5: derivar hacia mejoras prematuras de performance
**Riesgo:** invertir tiempo en optimizaciones antes de fijar calidad.  
**Mitigación:** diferir servicio persistente, CUDA graphs, caching agresivo y optimizaciones profundas.

### Riesgo 6: ComfyUI tome demasiado protagonismo
**Riesgo:** workflows difíciles de reproducir fuera de la UI.  
**Mitigación:** ComfyUI solo como exploración; baseline oficial en CLI.

---

## 5.1 Semántica de error y observabilidad mínima

### Reglas de error
- Fallar de forma explícita cuando falte referencia, transcripción o artefacto requerido.
- No degradar silenciosamente de ICL a embedding sin dejarlo registrado en salida o manifest.
- Cualquier referencia descartada por calidad debe dejar motivo trazable.
- Si una corrida de generación falla, debe emitirse estado final claro (`success`, `failed`, `skipped`) con contexto mínimo.

### Observabilidad mínima
- Guardar manifest por corrida con configuración usada, referencia elegida y output generado.
- Registrar warnings relevantes: referencia corta/larga, transcripción no validada, modo degradado, chunk omitido.
- Separar claramente errores de infraestructura/modelo vs errores de input/flujo.
- Mantener logs o mensajes suficientes para reproducir una corrida fallida sin inspección manual profunda.

## 6. Estrategia de pruebas

### Unit tests
Enfocar en piezas deterministas:
- segmentación de texto por oraciones
- construcción de manifests
- validación de metadata de referencia
- resolución de paths / bundles
- validaciones básicas de CLI

### Integration tests
Solo casos mínimos marcados como lentos:
- carga del modelo base
- generación con una referencia conocida
- salida de audio no vacía

### Verificación manual
Necesaria para calidad percibida:
- timbre
- acento
- entonación
- deriva en frase larga

### Scope de validación
- Los quality gates oficiales de este plan son solo Python/uv.
- Gates de otros ecosistemas (`bun`, `npm`, `node`) quedan fuera de alcance para esta ejecución salvo que una fase futura introduzca TypeScript de forma explícita.

### Quality gates
- `uv run pytest tests/unit/ -v`
- `uv run pytest tests/unit/ --cov=src --cov-fail-under=80`
- `uv run mypy`
- `uv run ruff check`

---

## 7. Estimación de complejidad

### Alcance inmediato recomendado
- Fase 0: LOW
- Fase 1: MEDIUM
- Fase 2: MEDIUM
- Fase 3: MEDIUM
- Fase 4: MEDIUM
- Fase 5: MEDIUM
- Fase 6: LOW

**Complejidad total del plan recomendado:** MEDIUM

**Tiempo total estimado:** 4.5 a 6.5 días efectivos

---

## 8. Trabajo diferido / proyecto futuro

Estas tareas se consideran demasiado complejas, prematuras o con riesgo de sobreingeniería para el estado actual del proyecto:

### Futuro A — Servicio persistente de inferencia
- proceso residente
- cola de jobs
- caching de modelo y prompts
- cancelación de jobs

**Motivo de diferir:** útil, pero no resuelve primero el problema principal de fidelidad.

### Futuro B — Ranking automático por embeddings / speaker similarity
- extracción de embeddings
- score automático de identidad vocal
- ranking cuantitativo de resultados

**Motivo de diferir:** alto valor, pero requiere elegir bien métricas y tooling.

### Futuro C — UI dedicada de evaluación
- panel de comparación
- scoring interactivo
- visualización de runs

**Motivo de diferir:** no necesaria para validar el flujo central.

### Futuro D — Fine-tuning / speaker adaptation
- datasets curados
- pipelines de entrenamiento
- validación de checkpoints

**Motivo de diferir:** alto costo, alto riesgo y todavía no justificado.

### Futuro E — Integración avanzada con ComfyUI como frontend oficial
- workflows mantenidos como producto
- sincronización de metadata con CLI
- gestión de presets desde UI

**Motivo de diferir:** ComfyUI hoy es herramienta de exploración, no el núcleo del sistema.

---

## 9. Recomendación ejecutiva

Implementar solo este bloque en la próxima ejecución:
1. preparación de referencias
2. bundle con transcripción corregible
3. comparador pequeño de configuraciones
4. generación por frases cortas
5. manifests y documentación mínima

Todo lo demás debe considerarse mejora futura hasta demostrar que este bloque ya elevó materialmente la calidad percibida de la voz clonada.
