# Plan: comparison follow-up hardening

## 1. Restatement de requerimientos

Transformar los hallazgos pendientes de la revisión técnica en un plan ejecutable, sin implementar todavía, para reforzar el flujo de comparación y bundles en estas áreas:

- evitar colisiones de `case_id` y sobrescritura silenciosa de outputs
- endurecer la validación del payload de `bundle.json`
- mejorar la robustez diagnóstica en la generación por caso
- validar antes los paths al construir `ReferenceBundle`
- decidir explícitamente si la exposición de paths absolutos en el manifest requiere tratamiento adicional

Alcance técnico esperado:
- `scripts/compare_reference_configs.py`
- `src/tts_lab/infrastructure/comparison_manifest.py`
- `src/tts_lab/infrastructure/reference_bundle.py`
- tests unitarios relacionados

Restricción explícita: esta fase no toca código; solo planifica, audita el plan y espera confirmación.

## 2. Supuestos y preguntas abiertas

### Supuestos de trabajo

- El endurecimiento solicitado es incremental sobre el estado actual del comparador; no implica rediseño del flujo completo.
- La semántica de salida ya aprobada previamente (`exit 1` si falla cualquier caso) se mantiene sin cambios.
- La prioridad principal es robustez funcional y trazabilidad de errores, no optimización de performance.
- Los tests nuevos deben seguir aislando el script con fakes/mocks y no depender de modelos reales.
- La exposición de rutas absolutas en manifest solo requiere acción si el artefacto va a compartirse fuera del entorno local.

### Decisiones cerradas

1. `case_id` único:
   - Decisión: usar hash corto derivado de `bundle_path`.
   - Motivo: evita colisiones incluso si `speaker` y `segment_path.stem` se repiten.
2. Validación de payload:
   - Decisión: validación estricta para todos los campos requeridos del loader.
   - Motivo: elimina coerciones silenciosas y hace fallar el input inválido en el borde correcto.
3. Paths en manifest:
   - Decisión: diferido fuera de esta iteración.
   - Motivo: evitar scope creep mientras el manifest siga siendo un artefacto local/debug.

### Sin bloqueos abiertos

No quedan decisiones funcionales bloqueantes para implementación. El tratamiento de exposición de paths queda explícitamente diferido y no debe entrar en esta ejecución salvo nueva instrucción del usuario.

## 3. Fases de implementación

### Fase 0 — Fijar contrato de implementación

Objetivo: arrancar con decisiones funcionales cerradas y sin ambigüedad entre fases y criterios.

Decisiones ya aprobadas:
1. `case_id` se vuelve único con hash corto derivado de `bundle_path`.
2. La validación del payload será estricta para todos los campos requeridos del loader.
3. El tratamiento de paths absolutos en manifest queda diferido fuera de esta iteración.

Reglas de ejecución aprobadas:
- Mantener cambios atómicos y medibles por PR/commit lógico.
- Mantener pruebas mínimas por ruta crítica en cada fase afectada.
- Hacer una revisión manual final de consistencia entre fases, criterios y riesgos antes de ejecutar.

Resultado esperado:
- No quedan decisiones bloqueantes para implementación.

### Fase 1 — Evitar colisiones de `case_id`

Objetivo: impedir sobrescritura silenciosa de outputs cuando distintos bundles compartan el mismo `segment_path.stem`.

Pasos:
1. Revisar generación de `bundle_slug` en `build_default_cases()`.
2. Incorporar un discriminador único y estable en `case_id` usando hash corto de `bundle_path`.
3. Mantener nombres suficientemente legibles para debugging, combinando legibilidad humana + sufijo estable de unicidad.
4. Verificar que el caso adicional `spanish-icl` use la misma estrategia.
5. Añadir tests con dos bundles distintos que hoy colisionarían.

Resultado esperado:
- Cada output `.wav` y cada caso del manifest tiene id estable y no colisiona entre bundles distintos.

### Fase 2 — Endurecer validación de `bundle.json`

Objetivo: eliminar coerciones silenciosas y aceptar solo payloads válidos.

Pasos:
1. Revisar `_load_bundle()` en `scripts/compare_reference_configs.py`.
2. Agregar helpers de validación explícita, por ejemplo:
   - `_require_string(...)`
   - `_require_int(...)`
   - `_require_float(...)`
   - `_require_string_list(...)`
3. Reemplazar coerciones con `str(...)`, `int(...)`, `float(...)` por validación estricta.
4. Validar que `warnings` sea una lista de strings, no cualquier iterable.
5. Mantener mensajes de error accionables y consistentes con el estilo actual de `SystemExit`.

Resultado esperado:
- Los bundles inválidos fallan temprano con mensajes precisos.
- Se evita aceptar datos corruptos que hoy podrían convertirse silenciosamente.

### Fase 3 — Reforzar robustez de ejecución por caso

Objetivo: mejorar manejo de resultados anómalos del modelo y calidad diagnóstica del manifest.

Pasos:
1. Validar explícitamente que `generate_voice_clone()` devuelva audio no vacío.
2. Validar que `sample_rate > 0` antes de calcular duración.
3. Mantener el comportamiento de fallo por caso, sin romper la persistencia del manifest.
4. Mejorar `error_message` para incluir tipo de excepción o un mensaje más útil.
5. Confirmar cobertura para casos de lista vacía, sample rate inválido y excepción del modelo.

Resultado esperado:
- Menos errores opacos por caso.
- Mejor capacidad de diagnóstico desde `manifest.json`.

### Fase 4 — Validación temprana en `build_reference_bundle()`

Objetivo: impedir construir bundles estructuralmente válidos pero rotos por paths inexistentes.

Pasos:
1. Revisar `build_reference_bundle()` en `reference_bundle.py`.
2. Validar que `normalized_path` exista y sea archivo.
3. Validar que `recommended["path"]` exista y sea archivo.
4. Mantener la separación de responsabilidades:
   - validación de construcción en `build_reference_bundle()`
   - validación de consumo serializado en `_load_bundle()`
5. Añadir tests de paths inexistentes.

Resultado esperado:
- Los bundles inválidos fallan en origen, no solo cuando se consumen más adelante.

### Fase 5 — Decisión explícita sobre exposición de paths en manifest

Objetivo: resolver si la serialización de rutas absolutas requiere cambio funcional.

Pasos:
1. Determinar si `manifest.json` es solo local o también compartible.
2. Si el alcance entra ahora, elegir una estrategia mínima:
   - rutas relativas al workspace
   - redacción parcial
   - flag opcional como `--redact-paths`
3. Si no entra ahora, dejarlo explícitamente diferido para evitar scope creep.

Resultado esperado:
- El riesgo de exposición de paths queda resuelto o conscientemente diferido.

## 4. Archivos candidatos a modificar

### Producción

- `src/tts_lab/infrastructure/comparison_manifest.py`
  - unicidad de `case_id`
- `scripts/compare_reference_configs.py`
  - validación estricta del payload
  - robustez de `_run_case()`
  - sin cambios de paths en manifest en esta iteración
- `src/tts_lab/infrastructure/reference_bundle.py`
  - validación temprana de paths durante construcción del bundle

### Tests

- `tests/unit/test_comparison_manifest.py`
  - colisiones de `case_id`
  - serialización consistente
- `tests/unit/test_compare_reference_configs.py`
  - validación estricta de tipos
  - `warnings` mal formados
  - audio vacío / sample rate inválido
  - errores enriquecidos por caso
- `tests/unit/test_reference_bundle.py`
  - rechazo de paths inexistentes en construcción de bundle

## 5. Riesgos y mitigaciones

### Riesgo 1 — Cambio de formato de nombres de output

- Riesgo: consumidores o scripts manuales podrían depender del naming actual de `case_id`.
- Mitigación:
  - documentar el nuevo patrón
  - mantener ids legibles y estables
  - cubrir con tests la nueva convención

### Riesgo 2 — Validación demasiado estricta rompe bundles antiguos

- Riesgo: bundles previamente tolerados podrían empezar a fallar.
- Mitigación:
  - limitar la validación a campos requeridos y críticos
  - producir mensajes de error claros para corrección rápida

### Riesgo 3 — Duplicación de validación entre builder y loader

- Riesgo: reglas similares en `build_reference_bundle()` y `_load_bundle()` divergen con el tiempo.
- Mitigación:
  - documentar responsabilidad de cada capa
  - mantener helpers pequeños y semánticamente separados

### Riesgo 4 — Scope creep por paths en manifest

- Riesgo: intentar resolver portabilidad/redacción de paths puede expandir demasiado el alcance.
- Mitigación:
  - mantenerlo explícitamente fuera de esta iteración
  - reabrirlo solo si aparece un requisito real de compartir manifests fuera del entorno local

### Riesgo 5 — Tests frágiles por dependencia de librerías externas

- Riesgo: el script depende de `Qwen3TTSModel` y `soundfile`.
- Mitigación:
  - seguir usando fakes/monkeypatch
  - no introducir pruebas con modelo real en unit tests

## 6. Estrategia de pruebas

### Unit tests

1. `build_default_cases()`
   - genera `case_id` distintos para bundles distintos con mismo stem
   - mantiene estructura esperada de ids
2. `_load_bundle()`
   - rechaza strings/números/listas en campos donde se espera tipo distinto
   - rechaza `warnings` que no sean lista de strings
3. `_run_case()` / flujo principal
   - rechaza audio vacío
   - rechaza `sample_rate <= 0`
   - conserva manifest y marca fallo por caso con error enriquecido
4. `build_reference_bundle()`
   - rechaza `normalized_path` inexistente
   - rechaza `recommended_segment_path` inexistente

### Verificación estática

Gate mínimo por ruta crítica, aprobado para esta ejecución:
- `uv run pytest` sobre tests unitarios afectados
- `uv run mypy` sobre archivos modificados y tests nuevos/ajustados
- `uv run ruff` sobre archivos modificados y tests nuevos/ajustados

### Smoke checks recomendados

- corrida con dos bundles distintos que antes colisionaban
- corrida con respuesta vacía del modelo fake
- corrida con bundle inválido por tipo

## 7. Estimación de complejidad

**MEDIUM**

Motivo:
- Los cambios son localizados, pero tocan contrato observable (`case_id`), validación de input y robustez del flujo principal.
- La complejidad principal no está en el código sino en decidir el nivel correcto de estrictez y el alcance real del tratamiento de paths en manifest.

## Recomendación de ejecución

Orden sugerido:
1. Corregir colisiones de ids con hash corto derivado de `bundle_path`.
2. Endurecer validación estricta del payload.
3. Reforzar robustez de `_run_case()`.
4. Validar paths en `build_reference_bundle()`.
5. Ejecutar gate mínimo (`pytest`, `mypy`, `ruff`).
6. Mantener fuera de alcance el tratamiento de paths absolutos en manifest.
