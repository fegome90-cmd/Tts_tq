# 06 — Testing

Cómo está armado el suite, los patrones no obvios que conviene replicar, y las brechas de coverage que hoy no se testean. Este doc existe porque los tests usan trucos (carga dinámica de módulos, fakes del modelo) que no son evidentes y que conviene tener documentados antes de tocarlos.

## Layout

- `tests/unit/` — 11 archivos, ~91 tests en total (contado con `pytest --collect-only`). Son los únicos tests que corren; `tests/integration/` está vacío (ISSUE-011).
- `tests/conftest.py` — dos fixtures compartidas, mínimo:

| Fixture | Qué da |
|---------|--------|
| `temp_output_dir` | Un dir temporal creado con `tempfile.mkdtemp()`, limpiado al final del test. |
| `sample_audio_data` | Bytes WAV de **1 segundo de silencio a 24kHz** (generado con numpy + soundfile). Útil como input dummy. |

## Distribución por archivo

| Archivo | Tests | Qué cubre |
|---------|-------|-----------|
| `test_qwen_client.py` | 17 | El cliente Qwen: carga lazy, mocking de `qwen_tts`/`torch`, `_seed_generation` por device, context manager, conversión a `AudioResult`. |
| `test_file_storage.py` | 12 | `FileAudioRepository`: save/load, sanitización de filenames, prevención de path traversal, hash de contenido. |
| `test_reference_preparation.py` | 10 | `compute_segment_metrics`, `segment_audio`, `pick_best_segment` — la heurística de scoring. |
| `test_entities.py` | 9 | Entidades del dominio (inmutabilidad, defaults, factory methods). |
| `test_protocols.py` | 9 | Que las implementaciones cumplen los protocols (structural typing). |
| `test_exceptions.py` | 8 | Jerarquía de excepciones. |
| `test_use_cases.py` | 8 | `GenerateSpeechUseCase`. |
| `test_cli.py` | 6 | CLI con `typer.testing.CliRunner` (incluye assert del default `-Base` de `clone`, `test_cli.py:27`). |
| `test_compare_reference_configs.py` | 5 | El script de comparación vía dynamic module load + `_FakeModel`. |
| `test_reference_bundle.py` | 4 | `build_reference_bundle` y `ReferenceBundle.to_dict`. |
| `test_comparison_manifest.py` | 3 | `build_default_cases`, `build_manifest`. |

## Patrón estrella: cargar un **script** como módulo

`compare_reference_configs.py` es un script suelto en `scripts/`, no un módulo del paquete. Para testearlo sin refactorizarlo, `test_compare_reference_configs.py:18-34` lo carga dinámicamente:

```python
import importlib.util, sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compare_reference_configs.py"
SCRIPT_MODULE_NAME = "compare_reference_configs_for_tests"

def _load_script_module() -> ModuleType:
    cached = sys.modules.get(SCRIPT_MODULE_NAME)           # cachea en sys.modules
    if isinstance(cached, ModuleType):
        return cached
    spec = importlib.util.spec_from_file_location(SCRIPT_MODULE_NAME, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[SCRIPT_MODULE_NAME] = module               # antes de exec
    spec.loader.exec_module(module)
    return module
```

Detalles no obvios:
- **Se cachea en `sys.modules` bajo un alias** (`compare_reference_configs_for_tests`), no bajo el nombre real. Eso evita colisiones y permite reusar la instancia entre tests.
- El cacheo ocurre **antes** de `exec_module` para que imports circulares o referencias internas resuelvan.

> **Replicá este patrón** para cualquier script nuevo en `scripts/` que quieras testear. Es el puente para traer código no empaquetado al suite.

## Patrón estrella: el `_FakeModel` del Qwen

El modelo real `Qwen3TTSModel` pesa GB y no se puede instanciar en CI. El test lo fakedes dos niveles:

### Nivel 1 — `_FakeModel` (`test_compare_reference_configs.py`)

Implementa exactamente la **superficie del Camino B** (ver `05-qwen-clonado-internals.md`): los dos métodos que el comparador llama:

```python
class _FakeModel:
    def __init__(self, *, fail_embedding: bool = False):
        self.fail_embedding = fail_embedding

    def create_voice_clone_prompt(self, segment_path, reference_text, *, x_vector_only_mode):
        return {"segment_path": segment_path, "reference_text": reference_text,
                "x_vector_only_mode": x_vector_only_mode}

    def generate_voice_clone(self, target_text, language, *, voice_clone_prompt):
        if self.fail_embedding and bool(voice_clone_prompt["x_vector_only_mode"]):
            raise RuntimeError("embedding generation failed")
        return ([[0.1, 0.2, 0.3]], 3)   # wavs, sample_rate
```

Notá el flag `fail_embedding`: permite forzar el fallo del caso embedding para testear la semántica `exit 1` del comparador sin necesidad de un modelo real.

### Nivel 2 — `_FakeModelFactory` + monkeypatch

`Qwen3TTSModel` se importa a nivel de módulo en `compare_reference_configs.py:11`. El test lo reemplaza con `monkeypatch.setattr`:

```python
class _FakeModelFactory:
    @staticmethod
    def from_pretrained(model_path, *, device_map):
        return _FakeModel(fail_embedding=True)

monkeypatch.setattr(script_module, "Qwen3TTSModel", _FakeModelFactory)
monkeypatch.setattr(script_module, "_parse_args", lambda: args)        # evita argparse real
monkeypatch.setattr(script_module.sf, "write", lambda *a, **k: None)  # no escribe audio
```

Tres monkeypatches que hacen el test hermético:
- `Qwen3TTSModel` → factory fake (no carga nada).
- `_parse_args` → devuelve un `argparse.Namespace` armado a mano (no parsea `sys.argv`).
- `sf.write` → no-op (no escribe archivos WAV reales en disco).

Después `script_module.main()` corre y el test asserta que `SystemExit(1)` + que el `manifest.json` se escribió con los estados esperados (`["success", "failed"]`).

## Patrón: mockear imports lazy en `qwen_client.py`

`QwenTTSClient._ensure_model_loaded` (`qwen_client.py:48-66`) hace imports **lazy** dentro del método. Para testear sin instalar `qwen-tts`/`torch`, `test_qwen_client.py` usa `patch.dict("sys.modules", ...)`:

```python
with patch.dict("sys.modules", {"qwen_tts": Mock(Qwen3TTSModel=mock_model_class)}):
    client._ensure_model_loaded()   # ahora "funciona" sin el paquete
```

Lo mismo para `torch` cuando se testea `_seed_generation`:

```python
with patch.dict("sys.modules", {"torch": mock_torch}):
    client._seed_generation(42)     # asserta manual_seed / cuda.manual_seed_all / mps.manual_seed
```

El truco clave: `patch.dict("sys.modules", ...)` **intercepta el `import` dentro del método** porque el import es lazy. Si el import fuera top-level, esto no funcionaría — ahí está la justificación del patrón lazy-load en `qwen_client.py`.

## Skip condicional por versión de Python

`test_qwen_client.py:133-136`:

```python
@pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="torch has compatibility issues with Python 3.14",
)
def test_unload_clears_model(self):
    ...
```

Esto documenta una fricción real: **torch no corre bien sobre 3.14**, que es justo la versión del venv (ISSUE-001). Es la señal más concreta de que el "drift" de versión no es solo cosmético.

## Brechas de coverage (qué NO se testea)

| Brecha | Ubicación | Riesgo |
|--------|-----------|--------|
| `scripts/prepare_reference.py` sin tests de script | Solo su módulo backing (`reference_preparation`) está testeado; el script completo (ffmpeg call, escritura de `metadata.json`) no. | Regresiones en el orchestration real del Stage 1. |
| `scripts/transcribe_reference.py` sin tests de script | Idem; el Whisper call + escritura de `bundle.json` no se testean. | Stage 2 sin cobertura. |
| `_validate_voice_profile` solo testeado con `.wav` + rechazo `.txt` | `qwen_client.py:179` acepta `.mp3`/`.flac` pero no hay test de esos caminos. | Extensión soportada sin prueba. |
| Ramas de device en `_seed_generation` mockeadas, no reales | `test_qwen_client.py` mockea `torch`/`cuda`/`mps`; nunca corre sobre hardware real. | El seeding real en mps/cuda no se verifica. |
| `tests/integration/` vacío | ISSUE-011. | Cero cobertura end-to-end; el pipeline completo nunca se corrió en test (ver caveat en `02-flujo`). |

## Cómo correr

```bash
uv run pytest tests/unit/ -v --cov=src --cov-report=term-missing   # suite + coverage
uv run pytest tests/unit/ -n auto                                   # paralelo (pytest-xdist)
uv run pytest tests/unit/test_compare_reference_configs.py -v       # un archivo
```

Target de coverage declarado: **80%** (`.coverage` presente). Los markers `slow`/`integration` están definidos en `pyproject.toml` pero hoy no se aplican a ningún test (no hay tests marcados).

## Relación con issues

- **ISSUE-011**: `tests/integration/` vacío, doc aspiracional.
- **ISSUE-001**: el skip de 3.14 en `test_qwen_client.py:133` es evidencia directa del drift de versión.
- **ISSUE-004**: `test_cli.py:27` es la prueba de que `clone` defaultea a `-Base` (usado para corregir el issue log).
