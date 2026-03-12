# Plan WorkOrders: TTS Lab Pragmatic Improvements

## Objetivo
Convertir el plan pragmático aprobado en un set de WorkOrders pequeños, secuenciales y verificables, priorizados por complejidad/tiempo. Todo lo que implique sobreingeniería o alta complejidad queda explícitamente diferido a futuro.

## Modo de ejecución
- **Modo recomendado:** manual worktree flow
- **Razón:** no hay evidencia de WOs ya normalizados en `WO-####` para este repo y el alcance es de mejora incremental sobre Python/CLI.
- **Regla:** un branch + un worktree por WO, sin mezclar cambios.

## Reglas globales
- No implementar en el árbol principal sucio.
- Cada WO debe cerrar con evidencia verificable.
- Si un WO crece o toca demasiadas capas, se divide antes de seguir.
- ComfyUI se usa solo como apoyo exploratorio; la baseline oficial vive en CLI/Python.
- Quality gates oficiales: `uv run pytest`, `uv run mypy`, `uv run ruff check`.

## Orden recomendado
1. WO-001 baseline y criterios
2. WO-002 preparación de referencias
3. WO-003 transcripción + bundle
4. WO-004 comparación de configuraciones
5. WO-005 chunking por frases
6. WO-006 consolidación CLI + docs
7. WO-007 validación final

---

# WO-001 — Baseline de clonación y criterios de éxito
**Complejidad:** LOW  
**Tiempo estimado:** 0.5 día  
**Branch sugerido:** `codex/wo-001-baseline`  
**Worktree sugerido:** `.worktrees/wo-001-baseline`

## Alcance
- Congelar baseline técnica inicial del laboratorio.
- Elegir referencias candidatas oficiales.
- Fijar textos canónicos cortos de comparación.
- Definir criterio de éxito subjetivo mínimo.

## No-goals
- No cambiar pipeline de inferencia.
- No agregar nuevas abstracciones del dominio.
- No automatizar comparación todavía.

## Pasos
1. Inventariar referencias actuales utilizables.
2. Seleccionar baseline inicial:
   - modelo base oficial
   - referencia A
   - referencia B
3. Definir 2 a 3 textos canónicos cortos.
4. Definir plantilla de evaluación subjetiva:
   - timbre
   - acento
   - entonación
   - deriva
5. Documentar baseline en plan o doc corto.

## Riesgos
- Elegir una referencia mala como baseline.
- Definir criterios subjetivos demasiado vagos.

## Mitigaciones
- Usar audio real limpio como punto de partida.
- Mantener texto corto y comparable.

## Archivos candidatos
- `README.md`
- posible nuevo doc: `docs/reference-workflow.md`
- `voice_profiles/felipe/`

## Pruebas / verificación
- Verificación manual de que los textos y referencias están definidos y son reproducibles.

## Criterio de salida
- Baseline oficial definida.
- Textos canónicos definidos.
- Rubrica subjetiva documentada.

---

# WO-002 — Preparación de referencias
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 a 1.5 días  
**Branch sugerido:** `codex/wo-002-reference-prep`  
**Worktree sugerido:** `.worktrees/wo-002-reference-prep`

## Alcance
- Crear flujo reproducible de preparación de referencia.
- Convertir, segmentar y evaluar referencias básicas.
- Guardar metadata de segmentos y segmento recomendado.

## No-goals
- No hacer DSP complejo.
- No hacer diarization.
- No hacer scoring avanzado por embeddings.

## Pasos
1. Crear utilidad de preparación de audio.
2. Estandarizar salida a WAV mono 24 kHz / 16-bit.
3. Segmentar clips útiles de 8–15s.
4. Calcular score básico por segmento:
   - duración
   - speech ratio
   - clipping básico
   - silencio excesivo
5. Guardar metadata y referencia recomendada.

## Riesgos
- Sobrelimpiar audio y perder identidad.
- Multiplicar scripts sin consolidación futura.

## Mitigaciones
- Mantener limpieza opcional y ligera.
- Guardar original y derivado.

## Archivos candidatos
- posible nuevo: `scripts/prepare_reference.py`
- `voice_profiles/felipe/refs/`
- posible soporte en `src/tts_lab/infrastructure/`
- tests nuevos para lógica determinista

## Pruebas / verificación
- Unit tests de validación de metadata y scoring básico.
- Ejecución manual sobre una referencia real conocida.

## Criterio de salida
- Existe flujo reproducible para generar referencias preparadas.
- Se produce metadata clara y segmento recomendado.

---

# WO-003 — Transcripción y bundle de referencia
**Complejidad:** MEDIUM  
**Tiempo estimado:** 0.5 a 1 día  
**Branch sugerido:** `codex/wo-003-reference-bundle`  
**Worktree sugerido:** `.worktrees/wo-003-reference-bundle`

## Alcance
- Transcribir referencia seleccionada.
- Guardar texto corregible y bundle reutilizable.
- Estandarizar la entrada para ICL.

## No-goals
- No construir editor visual.
- No hacer gestión compleja de datasets.

## Pasos
1. Ejecutar Whisper sobre referencia recomendada.
2. Guardar transcripción junto al audio.
3. Permitir corrección manual simple.
4. Crear bundle reutilizable:
   - audio
   - transcripción
   - origen
   - score
   - modo recomendado

## Riesgos
- Transcripción inexacta degradando ICL.
- Bundle sin validación mínima.

## Mitigaciones
- Marcar transcripción como auto/manual.
- Requerir campos mínimos en metadata.

## Archivos candidatos
- posible nuevo: `scripts/transcribe_reference.py`
- posible soporte en `src/tts_lab/application/` o `infrastructure/`
- `voice_profiles/felipe/refs/`

## Pruebas / verificación
- Unit tests de construcción/lectura de bundle.
- Smoke test con bundle real.

## Criterio de salida
- Existe un bundle de referencia reproducible y utilizable para ICL.

---

# WO-004 — Comparador de configuraciones
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 día  
**Branch sugerido:** `codex/wo-004-config-compare`  
**Worktree sugerido:** `.worktrees/wo-004-config-compare`

## Alcance
- Ejecutar una matriz pequeña de configuraciones comparables.
- Guardar outputs y manifests por corrida.
- Reducir comparación manual caótica.

## No-goals
- No hacer ranking automático.
- No hacer dashboard.
- No correr docenas de combinaciones.

## Pasos
1. Fijar máximo 4–6 combinaciones.
2. Ejecutar la matriz con textos canónicos.
3. Guardar resultados en estructura estable.
4. Emitir manifest JSON por corrida.
5. Dejar naming consistente de outputs.

## Riesgos
- Matriz demasiado grande y lenta.
- Outputs sin trazabilidad exacta.

## Mitigaciones
- Limitar combinaciones.
- Manifest obligatorio por corrida.

## Archivos candidatos
- `scripts/generate_voice_case.py`
- `scripts/generate_voice_matrix.py`
- posible soporte en `src/tts_lab/cli.py`
- `output/voice_matrix/`

## Pruebas / verificación
- Tests de manifest y naming.
- Corrida manual pequeña con referencias reales.

## Criterio de salida
- Comparación A/B reproducible con manifests legibles.

---

# WO-005 — Generación por frases cortas
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 día  
**Branch sugerido:** `codex/wo-005-sentence-chunking`  
**Worktree sugerido:** `.worktrees/wo-005-sentence-chunking`

## Alcance
- Reducir deriva en textos largos mediante chunking por oraciones.
- Generar oraciones por separado y concatenar con pausas controladas.

## No-goals
- No hacer prosody alignment avanzada.
- No hacer edición tipo DAW.
- No hacer crossfade complejo.

## Pasos
1. Implementar split por oraciones.
2. Generar un audio por oración.
3. Concatenar con pausas simples controladas.
4. Guardar metadata por chunk y salida final.

## Riesgos
- Segmentación deficiente en español.
- Unión de audios con pausas artificiales.

## Mitigaciones
- Empezar por reglas simples y previsibles.
- Mantener pausas fijas y visibles en metadata.

## Archivos candidatos
- `src/tts_lab/application/use_cases.py`
- `src/tts_lab/application/dto.py`
- `src/tts_lab/cli.py`
- posible nuevo test: `tests/unit/test_text_chunking.py`

## Pruebas / verificación
- Unit tests del chunker.
- Smoke test de generación multi-oración.

## Criterio de salida
- Flujo reproducible para textos medianos/largos con menor deriva observada.

---

# WO-006 — Consolidación en CLI y documentación
**Complejidad:** MEDIUM  
**Tiempo estimado:** 1 a 1.5 días  
**Branch sugerido:** `codex/wo-006-cli-consolidation`  
**Worktree sugerido:** `.worktrees/wo-006-cli-consolidation`

## Alcance
- Llevar flujos validados al entrypoint oficial del proyecto.
- Reducir scripts sueltos como interfaz principal.
- Actualizar README y documentación operativa.

## No-goals
- No rediseñar todo el dominio.
- No crear demasiados comandos si un flujo simple basta.

## Pasos
1. Identificar scripts que ya demostraron valor.
2. Consolidar solo los flujos ganadores en la CLI.
3. Mantener scripts auxiliares como soporte temporal.
4. Actualizar README y ejemplos.

## Riesgos
- Mover muy pronto lógica experimental al core.
- Inflar la CLI con demasiadas opciones.

## Mitigaciones
- Consolidar solo lo ya validado por WOs previos.
- Preferir comandos pocos y claros.

## Archivos candidatos
- `src/tts_lab/cli.py`
- `README.md`
- docs auxiliares

## Pruebas / verificación
- Tests de CLI básicos.
- Verificación manual de help y rutas principales.

## Criterio de salida
- Flujo principal claro, documentado y usable sin scripts dispersos.

---

# WO-007 — Validación final y handoff
**Complejidad:** LOW  
**Tiempo estimado:** 0.5 día  
**Branch sugerido:** `codex/wo-007-final-validation`  
**Worktree sugerido:** `.worktrees/wo-007-final-validation`

## Alcance
- Cerrar el ciclo con validación técnica y baseline ganadora.
- Dejar evidencia de uso y estado final.

## No-goals
- No introducir funcionalidad nueva.
- No reabrir alcance ya diferido.

## Pasos
1. Ejecutar quality gates Python/uv.
2. Ejecutar comparación final corta.
3. Confirmar baseline ganadora.
4. Documentar límites conocidos.
5. Dejar handoff del estado final.

## Riesgos
- Reabrir cambios funcionales al final.
- Confundir deuda previa con regresiones nuevas.

## Mitigaciones
- Tratar WO-007 solo como cierre y verificación.
- Documentar baseline debt explícita si aparece.

## Pruebas / verificación
- `uv run pytest tests/unit/ -v`
- `uv run pytest tests/unit/ --cov=src --cov-fail-under=80`
- `uv run mypy`
- `uv run ruff check`

## Criterio de salida
- Evidencia técnica completa.
- Baseline ganadora documentada.
- Handoff listo para siguiente iteración.

---

## Dependencias entre WOs
- WO-001 desbloquea WO-002/003/004.
- WO-002 desbloquea WO-003.
- WO-003 desbloquea WO-004 y WO-005.
- WO-004 puede correr antes de WO-005 si hay una baseline estable.
- WO-006 depende de validación funcional previa de WO-002 a WO-005.
- WO-007 depende de todos los anteriores.

## WOs diferidos a futuro
No entran en esta ejecución:
- servicio persistente de inferencia
- ranking automático por embeddings / speaker similarity
- UI dedicada de evaluación
- fine-tuning / speaker adaptation
- integración avanzada con ComfyUI como frontend oficial

## Recomendación ejecutiva
Si se quiere minimizar riesgo, ejecutar primero solo:
- WO-001
- WO-002
- WO-003
- WO-004

Y re-evaluar antes de abrir WO-005/006. Esa división entrega valor temprano sin empujar el proyecto a sobreingeniería.
