# WO-001 — Baseline de clonación y criterios de éxito

## Estado
Ready for execution

## Lifecycle mode
- **Modo:** manual worktree flow
- **Branch sugerido:** `codex/wo-001-baseline`
- **Worktree sugerido:** `.worktrees/wo-001-baseline`

## Objetivo
Definir una baseline oficial, pequeña y repetible para evaluar mejoras del laboratorio de voice cloning.

## Requerimientos restate
Este WO debe dejar definido:
1. modelo oficial de baseline;
2. referencias oficiales candidatas para comparar;
3. textos canónicos cortos de prueba;
4. criterio de éxito subjetivo mínimo para timbre, acento, entonación y deriva.

## No-goals
- No modificar pipeline de inferencia.
- No agregar nuevas abstracciones del dominio.
- No crear automatización de comparación.
- No tocar ComfyUI salvo como referencia documental.
- No implementar código productivo fuera de documentación/configuración mínima del baseline.

## Alcance estricto
### Debe incluir
- Selección de baseline inicial del modelo.
- Selección de referencia A y referencia B.
- Definición de 2 a 3 textos canónicos cortos.
- Definición de una rúbrica simple de evaluación subjetiva.
- Documentación del baseline para uso en los WOs siguientes.

### Debe excluir
- preparación automática de referencias;
- transcripción automatizada;
- matrices de ejecución;
- chunking por frases;
- consolidación CLI.

## Supuestos
- El modelo base de clonación seguirá siendo `Qwen3-TTS-12Hz-1.7B-Base`.
- `pitch_seg1.wav` es una referencia real candidata fuerte.
- `reference_v2.wav` puede servir como referencia comparativa secundaria.
- La validación subjetiva final la hace Felipe.

## Riesgos
1. Elegir una referencia incorrecta como baseline.
2. Definir textos de comparación demasiado largos y provocar deriva temprana.
3. Dejar una rúbrica subjetiva demasiado vaga.
4. Abrir scope hacia automatización antes de fijar baseline.

## Mitigaciones
- Limitar textos a una sola frase por muestra.
- Tomar máximo 2 referencias principales.
- Documentar una rúbrica cerrada de 1 a 5.
- Cerrar el WO solo cuando el baseline quede utilizable por siguientes WOs.

## Plan paso a paso
1. Inventariar referencias actuales disponibles y útiles.
2. Elegir baseline inicial:
   - modelo oficial;
   - referencia A;
   - referencia B.
3. Definir textos canónicos:
   - uno neutro;
   - uno conversacional;
   - uno con chilenismo ligero.
4. Definir rúbrica subjetiva:
   - timbre;
   - acento;
   - entonación;
   - deriva.
5. Documentar baseline en archivo estable dentro del repo.
6. Verificar que WO-002 pueda consumir esta baseline sin ambigüedad.

## Archivos candidatos a modificar
- `README.md`
- posible nuevo doc: `.pi/plan/baseline-reference.md`
- posible nuevo doc: `docs/reference-workflow.md`
- `voice_profiles/felipe/` (solo si se agrega metadata, no audio nuevo)

## Verificación
### Manual
- Confirmar que el baseline responde estas preguntas sin interpretación extra:
  - ¿qué modelo usar?
  - ¿qué dos referencias usar?
  - ¿qué textos usar?
  - ¿cómo se puntúa el resultado?

### Técnica
- `git diff --stat` pequeño y entendible
- sin cambios de código de inferencia
- sin artefactos generados innecesarios

## Criterio de salida
WO-001 se considera completo solo si deja:
- baseline oficial definida;
- referencias A/B definidas;
- textos canónicos definidos;
- rúbrica subjetiva 1–5 definida;
- documentación suficiente para arrancar WO-002 sin preguntas abiertas operativas.

## Checklist de salida
- [ ] Modelo baseline definido.
- [ ] Referencia A definida.
- [ ] Referencia B definida.
- [ ] 2–3 textos canónicos definidos.
- [ ] Rúbrica subjetiva definida.
- [ ] Documento baseline guardado en repo.
- [ ] Scope se mantuvo sin tocar pipeline.

## Evidencia esperada
- Documento corto de baseline.
- Diff pequeño, documental/configurativo.
- Handoff que habilite WO-002.

## Blockers que deben detener ejecución
- No hay claridad sobre qué audio debe ser referencia A/B.
- Felipe no valida la rúbrica propuesta.
- El WO intenta empezar a automatizar preparación de referencias.
