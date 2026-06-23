# Plan: comparison bundle robustness hardening

## 1. Restatement de requerimientos

Convertir el review recibido en un plan ejecutable, sin implementar todavía, para endurecer el flujo de comparación y bundle en:

- `scripts/compare_reference_configs.py`
- `src/tts_lab/infrastructure/comparison_manifest.py`
- `src/tts_lab/infrastructure/reference_bundle.py`

El objetivo es corregir problemas de robustez y lógica detectados en el review:

1. Evitar silent failures en `compare_reference_configs.py` cuando fallen uno o más casos.
2. Validar correctamente el tipo de `transcription_validated` al cargar `bundle.json`.
3. Validar temprano la existencia de `segment_path` y `source_audio_path` al cargar el bundle.
4. Corregir la trazabilidad de `bundle_path` en el manifest para apuntar al `bundle.json` real.
5. Simplificar la rama muerta de `mode_recommendation` en `reference_bundle.py`.
6. Evaluar una mejora opcional de performance: cacheo de prompts por bundle + modo.

Restricción explícita: esta fase no toca código; solo planifica, audita el plan y espera confirmación.

## 2. Supuestos y preguntas abiertas

### Supuestos de trabajo

- El comportamiento deseado del comparador es mantener el `manifest.json` aun cuando existan fallos parciales.
- La semántica de salida debe ser explícita para automatización/CI.
- `bundle.json` es el artefacto fuente de trazabilidad; `segment_path` no reemplaza esa referencia.
- El JSON de bundle debe ser estricto en tipos para campos críticos, especialmente booleanos.
- El cambio opcional de cacheo no debe alterar el output funcional ni el contenido del manifest.

### Decisiones cerradas

1. Política de exit code:
   - Decisión: `exit 1` si falla cualquier caso.
   - Motivo: semántica segura y explícita para CI/automatización.
2. Compatibilidad de esquema del manifest:
   - Decisión: corregir `bundle_path` in-place para que apunte al `bundle.json` real usado en la corrida.
   - Motivo: maximizar trazabilidad y eliminar ambigüedad del contrato actual.
3. Cacheo de prompts:
   - Decisión: queda fuera de alcance en esta ejecución.
   - Motivo: priorizar robustez, trazabilidad y tests antes de optimizaciones.

### Sin bloqueos abiertos

No quedan decisiones funcionales pendientes para iniciar implementación. Si durante la ejecución aparece un consumidor externo del manifest que dependa del valor incorrecto actual de `bundle_path`, se tratará como ajuste de compatibilidad acotado, no como cambio de objetivo.

## 3. Fases de implementación

### Fase 0 — Fijar contrato de implementación

Objetivo: arrancar con decisiones funcionales ya cerradas y responsables técnicos claros por fase.

Decisiones ya aprobadas:
- `exit 1` si falla cualquier caso.
- `bundle_path` debe apuntar al `bundle.json` real usado en la corrida.
- El cacheo de prompts queda diferido y fuera de alcance.

Responsables técnicos por fase:
- Fase 1 y Fase 2: `scripts/compare_reference_configs.py`
- Fase 3: `src/tts_lab/infrastructure/comparison_manifest.py` y punto de integración en `scripts/compare_reference_configs.py`
- Fase 4: `src/tts_lab/infrastructure/reference_bundle.py`
- Fase 6 de verificación: `tests/unit/test_reference_bundle.py`, `tests/unit/test_comparison_manifest.py`, `tests/unit/test_compare_reference_configs.py` (nuevo)

### Fase 1 — Endurecer carga y validación del bundle

Objetivo: mover fallos de input inválido al inicio del flujo con mensajes explícitos.

Pasos:
1. Revisar `_load_bundle()` en `scripts/compare_reference_configs.py`.
2. Reemplazar coerción insegura de `transcription_validated` por validación estricta de tipo booleano.
3. Validar presencia y existencia en filesystem de:
   - `segment_path`
   - `source_audio_path`
4. Fallar temprano con `SystemExit` y mensajes accionables cuando el bundle sea inválido.
5. Evaluar si conviene encapsular esta validación en un helper pequeño para mantener funciones cortas.

Resultado esperado:
- Un bundle inválido deja de fallar tarde dentro de la generación.
- El error distingue claramente entre input roto y fallo del modelo.

### Fase 2 — Corregir semántica de salida del comparador

Objetivo: eliminar silent failures del proceso principal.

Pasos:
1. Mantener la captura por caso dentro de `_run_case()` para no perder resultados parciales ni el manifest.
2. Al finalizar la corrida, contabilizar casos `success` vs `failed`.
3. Persistir `manifest.json` antes de decidir el exit status.
4. Aplicar la política definida en Fase 0:
   - `exit 0`: todos los casos terminaron en `success`.
   - `exit 1`: existe al menos un caso `failed`.
5. Emitir un resumen final legible para CLI con conteo de éxitos y fallos, manteniendo contrato explícito de error para automatización.

Resultado esperado:
- CI y automatizaciones pueden diferenciar una corrida completamente exitosa de una corrida con errores.
- El manifest sigue disponible para diagnóstico.

### Fase 3 — Arreglar trazabilidad del manifest

Objetivo: que cada `ComparisonCase` apunte al `bundle.json` real usado en la corrida.

Pasos:
1. Transportar la ruta real del `bundle.json` fuente desde el loader hasta la construcción de `ComparisonCase`.
2. Corregir `bundle_path` in-place para que el manifest serialice la ruta del bundle real, no `segment_path`.
3. Actualizar `build_default_cases()` en `comparison_manifest.py` para usar la ruta correcta.
4. Revisar el armado del caso adicional `spanish-icl` para que herede la trazabilidad correcta.
5. Verificar que `manifest.json` conserve consistencia entre casos por bundle.
6. Si aparece un consumidor interno del contrato anterior, documentar el ajuste y cubrirlo con test para evitar regresiones silenciosas.

Resultado esperado:
- El manifest permite reproducir qué bundle se usó realmente.
- Se mejora el debugging y la auditoría posterior.

### Fase 4 — Simplificar lógica muerta en `reference_bundle.py`

Objetivo: eliminar una rama imposible y reducir confusión.

Pasos:
1. Simplificar `mode_recommendation` para reflejar el comportamiento real del constructor.
2. Verificar si existe algún caller que dependa de la falsa semántica “embedding cuando no hay texto”.
3. Actualizar tests para reflejar la regla explícita.

Resultado esperado:
- La lógica del dominio expresa lo que realmente ocurre.
- Menor deuda de lectura/mantenimiento.

### Fase 5 — Diferido explícitamente: cacheo de prompts

Objetivo: dejar documentado que esta optimización no forma parte de la ejecución aprobada.

Decisión:
1. No implementar cacheo en esta iteración.
2. Revaluarlo solo después de cerrar robustez, trazabilidad y cobertura mínima.
3. Si se retoma más adelante, usar una clave estable como `(bundle.segment_path, bundle.reference_text, case.mode)` y validar que no altere manifest ni comportamiento.

Resultado esperado:
- Alcance acotado y enfocado en corrección funcional.
- La optimización queda registrada como mejora posterior, no como requisito de esta entrega.

## 4. Archivos candidatos a modificar

### Cambios principales

- `scripts/compare_reference_configs.py`
  - endurecer `_load_bundle()`
  - agregar semántica explícita de exit status
  - opcional: cacheo de prompts
- `src/tts_lab/infrastructure/comparison_manifest.py`
  - corregir trazabilidad de `bundle_path`
  - propagar correctamente el bundle real a los casos
- `src/tts_lab/infrastructure/reference_bundle.py`
  - simplificar `mode_recommendation`
  - opcional: transportar metadata de trazabilidad si se decide allí

### Tests candidatos

- `tests/unit/test_reference_bundle.py`
  - ajustar expectativa de `mode_recommendation`
  - agregar cobertura para warnings/validación relacionada si cambia el modelo
- `tests/unit/test_comparison_manifest.py`
  - validar que `bundle_path` apunte al `bundle.json` real
- `tests/unit/test_compare_reference_configs.py` (nuevo, recomendado)
  - validar coerción estricta de booleanos
  - validar errores por paths inexistentes
  - validar exit code según fallos parciales/totales
  - validar persistencia de manifest incluso cuando hay fallos
  - opcional: validar reutilización de prompts si entra cacheo

## 5. Riesgos y mitigaciones

### Riesgo 1 — Cambio de contrato del manifest

- Riesgo: consumidores existentes podrían estar leyendo `bundle_path` como si fuera `segment_path`.
- Mitigación:
  - revisar usos internos del manifest antes de implementar
  - si hay duda, documentar el cambio o introducir transición mínima

### Riesgo 2 — Exit code demasiado estricto para flujos actuales

- Riesgo: pipelines existentes podrían empezar a fallar por fallos parciales que hoy se toleran.
- Mitigación:
  - decidir explícitamente la política antes de implementar
  - documentar nueva semántica en el script/help o changelog técnico

### Riesgo 3 — Duplicar validaciones entre bundle builder y loader

- Riesgo: reglas repartidas entre `build_reference_bundle()` y `_load_bundle()` pueden divergir.
- Mitigación:
  - mantener en `_load_bundle()` solo validaciones de input serializado y filesystem
  - mantener en `build_reference_bundle()` reglas del dominio de construcción

### Riesgo 4 — Cacheo introduce complejidad innecesaria

- Riesgo: optimización prematura complica el script sin beneficio real inmediato.
- Mitigación:
  - tratarlo como parche opcional/posterior
  - implementar solo si la auditoría o el usuario lo aprueban explícitamente

### Riesgo 5 — Tests del script difíciles por dependencia del modelo

- Riesgo: `Qwen3TTSModel` y escritura de audio vuelven frágil la prueba directa.
- Mitigación:
  - aislar tests en helpers pequeños
  - usar monkeypatch/fakes para `from_pretrained`, `create_voice_clone_prompt`, `generate_voice_clone` y `sf.write`

## 6. Estrategia de pruebas

### Unit tests

1. `_load_bundle()`
   - rechaza JSON no objeto
   - rechaza falta de campos requeridos
   - rechaza `transcription_validated` no booleano (`"false"`, `0`, `1`, `null`)
   - rechaza `segment_path` inexistente
   - rechaza `source_audio_path` inexistente
2. `build_default_cases()`
   - serializa `bundle_path` correcto con la ruta real del bundle
3. `build_reference_bundle()`
   - mantiene `mode_recommendation == "icl"` cuando el texto es válido
4. flujo principal del comparador
   - persiste `manifest.json` con casos mezclados `success/failed`
   - devuelve exit code acorde a la política definida
   - mantiene errores por caso dentro del manifest

### Verificación estática

Gate mínimo por ruta crítica para considerar la ejecución completa:
- `uv run pytest` sobre tests unitarios afectados y nuevo test del script
- `uv run mypy` para validar cambios de tipos estrictos
- `uv run ruff` para estilo/lint

### Smoke checks recomendados

- corrida con bundle válido y modelo fake/mock
- corrida con bundle inválido para confirmar fallo temprano y mensaje claro
- corrida con mezcla de un caso exitoso y uno fallido para verificar persistencia + exit status

## 7. Estimación de complejidad

**MEDIUM**

Motivo:
- Los cambios son localizados, pero tocan contrato de manifest, semántica de CLI y estrategia de tests para un script con dependencias pesadas.
- Aunque las decisiones funcionales ya quedaron cerradas, la implementación sigue teniendo impacto transversal en loader, manifest y pruebas del script.

## Recomendación de ejecución

Orden recomendado:
1. Implementar validación temprana del bundle.
2. Implementar semántica de salida con manifest persistente y exit codes explícitos.
3. Ajustar trazabilidad del manifest + tests asociados.
4. Simplificar rama muerta.
5. Ejecutar gate mínimo por ruta crítica (`pytest`, `mypy`, `ruff`).
6. Mantener cacheo fuera de alcance en esta entrega.
