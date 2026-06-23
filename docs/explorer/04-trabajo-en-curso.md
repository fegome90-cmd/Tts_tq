# 04 — Trabajo en curso

Estado del trabajo en vuelo al momento del snapshot (2026-06-23). Si retomás una sesión, arrancá acá.

## Worktree: `.worktrees/wo-001-comparison-followup-hardening/`

Existe una copia del repo en `.worktrees/wo-001-comparison-followup-hardening/` que contiene una implementación **más completa** del hardening de comparación y bundles. Estado: **en vuelo, sin commitear a main**.

> **⚠️ Es un git worktree huérfano (orphaned), NO una copia manual.** `git worktree list` sí lo lista, pero apunta al path **pre-rename** `/Users/felipe_gonzalez/Developer/Tts_tq/.worktrees/...` (rama `codex/wo-001-comparison-followup-hardening` @ `8d22656`, marcada **`prunable`**). El `.git` interno referencia `gitdir: /Users/felipe_gonzalez/Developer/Tts_tq/.git/worktrees/...` que ya no existe porque el repo se renombró a `Tts_tq_backup`. Por eso `git -C .worktrees/wo-001-... status` da **`fatal: not a git repository`** (no es salida vacía). El diff que importa está en los archivos, pero la integridad git está rota.

### Qué ya tiene adelantado vs. `main`

Diff real contra `src/tts_lab/infrastructure/` de main:

1. **`comparison_manifest.py`** (~98 → ~106 líneas): agrega `build_case_prefix()` con un hash corto (`sha1(bundle_path)[:8]`) para hacer `case_id` único y legible, y lo usa en los casos `auto-icl` y `auto-embedding`. Implementa la **Fase 1 (unicidad de `case_id`)** del plan de hardening — evita sobrescritura silenciosa de outputs cuando dos bundles comparten el mismo `segment_path.stem`.
2. **`reference_bundle.py`** (~111 → ~120 líneas): agrega `_require_existing_file()` que valida que `normalized_path` y el `path` del segmento recomendado existan como archivo **al construir** el bundle. Implementa la **Fase 4 (validación temprana de paths)** — los bundles rotos fallan en origen, no al consumirlos después.

El resto de `src/` y los tests tienen la misma estructura que main (mismos archivos), aunque el contenido de los tests podría diferir en detalle.

### Qué ya estaba en main (commit `82a66f9`)

El commit `fix(comparison): harden bundle loading and manifest output` ya aterrizó parte del hardening en main: el `_require_boolean` y `_require_existing_path` en `scripts/compare_reference_configs.py`, y la semántica `exit 1` si falla algún caso. El worktree **continúa** esa línea.

## Planes sin trackear (`.pi/plan/`)

Dos planes nuevos no commiteados, ambos **solo planificación** (sin implementar en main):

| Plan | Alcance | Estado |
|------|---------|--------|
| `.pi/plan/comparison-bundle-robustness.md` | Hardening inicial: exit code, validación de `transcription_validated`, paths en bundle, trazabilidad de `bundle_path`, simplificar rama muerta de `mode_recommendation`, cacheo de prompts (este último fuera de alcance). | Parcialmente resuelto por `82a66f9`. |
| `.pi/plan/comparison-followup-hardening.md` | Follow-up en 5 fases: (1) `case_id` único por hash de `bundle_path`, (2) validación estricta del payload del bundle, (3) robustez de `_run_case` (audio vacío / `sample_rate<=0` / errores enriquecidos), (4) validación de paths en `build_reference_bundle`, (5) decisión sobre exposición de paths absolutos en manifest (diferida). Complejidad estimada: MEDIUM. | Fases 1 y 4 implementadas en el worktree. Fases 2, 3 y 5 **pendientes**. |

## Próximos pasos sugeridos (orden recomendado por el plan)

1. **Reparar el worktree huérfano**: el worktree YA es git worktree pero quedó huérfano por el rename `Tts_tq` → `Tts_tq_backup`. Opciones: (a) `git worktree prune` y re-agregar el diff como branch limpia en el repo actual, o (b) migrar manualmente las Fases 1 y 4 (ya implementadas) a una branch nueva y descartar el worktree roto.
2. **Fase 2** — validación estricta del payload en `_load_bundle()` (`compare_reference_configs.py`): reemplazar coerciones `str()/int()/float()` por helpers `_require_string/_require_int/_require_float/_require_string_list`.
3. **Fase 3** — robustez de `_run_case()` (`compare_reference_configs.py`): validar audio no vacío y `sample_rate > 0`, enriquecer `error_message`.
4. **Fase 5** — exposición de paths absolutos en `manifest.json`: diferida por decisión; reabrir solo si el manifest se comparte fuera del entorno local.
5. Mientras tanto, evaluar encarar los **Alta** del issue log (ISSUE-004 modelos, ISSUE-005 use case de clone), que son ortogonales a este hardening.

## Archivos clave del trabajo en curso

- `.worktrees/wo-001-comparison-followup-hardening/src/tts_lab/infrastructure/comparison_manifest.py`
- `.worktrees/wo-001-comparison-followup-hardening/src/tts_lab/infrastructure/reference_bundle.py`
- `.pi/plan/comparison-followup-hardening.md`
- `.pi/plan/comparison-bundle-robustness.md`
