# Explorer — Snapshot del estado del codebase

Esta carpeta es un **snapshot** del estado de TTS Lab tomado el **2026-06-23**, con dos objetivos:

1. **Onboarding rápido**: que cualquier sesión nueva entienda la arquitectura actual y el flujo de voice cloning sin tener que releer todo el repo.
2. **Issue tracking**: dejar registrado un backlog priorizado de inconsistencias y bugs detectados para iterar después.

> Los docs acá adentro describen el **estado real del código** en esta fecha, no el estado deseado. Cuando arreglés algo del issue log, actualizá el correspondiente `03-log-errores.md`.

## Índice

| Archivo | Descripción |
|---------|-------------|
| [`01-arquitectura.md`](01-arquitectura.md) | Estado actual de la arquitectura Clean (domain/application/infrastructure), los tres entry points y diagramas de flujo. |
| [`02-flujo-voice-cloning.md`](02-flujo-voice-cloning.md) | Recorrido detallado del pipeline activo: `prepare_reference` → `transcribe_reference` → `compare_reference_configs`, con artefactos producidos y el algoritmo de scoring de segmentos. |
| [`03-log-errores.md`](03-log-errores.md) | **Backlog de issues.** Tabla priorizada con severidad, ubicación, impacto y acción sugerida. El doc clave para iterar. |
| [`04-trabajo-en-curso.md`](04-trabajo-en-curso.md) | Estado del trabajo en vuelo: el worktree `.worktrees/wo-001-comparison-followup-hardening/` y los planes de hardening no commiteados. |
| [`05-qwen-clonado-internals.md`](05-qwen-clonado-internals.md) | Internals del motor Qwen3-TTS: las dos APIs de `generate_voice_clone` (CLI vs comparador), sampling params, ICL vs embedding, reproducibilidad. |
| [`06-testing.md`](06-testing.md) | Estrategia de testing: layout del suite, patrón de carga dinámica de scripts, `_FakeModel`, mocking de imports lazy, brechas de coverage. |

## Convenciones

- Los paths son **absolutos desde la raíz del repo** (`/Users/felipe_gonzalez/Developer/Tts_tq_backup`).
- Las citas a código usan formato `archivo:línea` para que sean buscables.
- Severidades: **Alta** (rompe validez/correctitud), **Media** (desorienta o es bug latente), **Baja** (código muerto / aspiracional).

## Estado de Git en el momento del snapshot

- Branch actual con WO-001..WO-004 mergueados + un fix de hardening (`82a66f9 fix(comparison): harden bundle loading and manifest output`).
- Cambios sin commitear: `README.md` modificado (` M`), `CLAUDE.md` staged como archivo nuevo (`A`), `AGENTS.md` sin trackear (`??`), y dos planes nuevos sin trackear en `.pi/plan/` (ver `04-trabajo-en-curso.md`).
