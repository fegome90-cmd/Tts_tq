"""Unit tests for scripts/compare_reference_configs.py."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compare_reference_configs.py"
SCRIPT_MODULE_NAME = "compare_reference_configs_for_tests"


def _load_script_module() -> ModuleType:
    cached_module = sys.modules.get(SCRIPT_MODULE_NAME)
    if isinstance(cached_module, ModuleType):
        return cached_module

    spec = importlib.util.spec_from_file_location(SCRIPT_MODULE_NAME, SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load compare_reference_configs.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[SCRIPT_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script_module() -> ModuleType:
    return _load_script_module()


@pytest.fixture
def bundle_payload(tmp_path: Path) -> dict[str, object]:
    segment_path = tmp_path / "segment.wav"
    source_audio_path = tmp_path / "source.wav"
    segment_path.write_bytes(b"segment")
    source_audio_path.write_bytes(b"source")
    return {
        "speaker": "felipe",
        "segment_path": str(segment_path),
        "source_audio_path": str(source_audio_path),
        "reference_text": "Hola, esta es una referencia.",
        "transcription_source": "manual_file",
        "transcription_validated": True,
        "score": 0.72,
        "recommended_segment_index": 1,
        "mode_recommendation": "icl",
        "language": "es",
        "warnings": [],
    }


def _write_bundle(tmp_path: Path, payload: dict[str, object]) -> Path:
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(payload), encoding="utf-8")
    return bundle_path


def test_load_bundle_rejects_non_boolean_transcription_validated(
    script_module: ModuleType,
    tmp_path: Path,
    bundle_payload: dict[str, object],
) -> None:
    payload = dict(bundle_payload)
    payload["transcription_validated"] = "false"
    bundle_path = _write_bundle(tmp_path, payload)

    with pytest.raises(SystemExit, match="transcription_validated"):
        script_module._load_bundle(bundle_path)


def test_load_bundle_rejects_missing_segment_path(
    script_module: ModuleType,
    tmp_path: Path,
    bundle_payload: dict[str, object],
) -> None:
    payload = dict(bundle_payload)
    payload["segment_path"] = str(tmp_path / "missing-segment.wav")
    bundle_path = _write_bundle(tmp_path, payload)

    with pytest.raises(SystemExit, match="segment_path"):
        script_module._load_bundle(bundle_path)


def test_load_bundle_rejects_missing_source_audio_path(
    script_module: ModuleType,
    tmp_path: Path,
    bundle_payload: dict[str, object],
) -> None:
    payload = dict(bundle_payload)
    payload["source_audio_path"] = str(tmp_path / "missing-source.wav")
    bundle_path = _write_bundle(tmp_path, payload)

    with pytest.raises(SystemExit, match="source_audio_path"):
        script_module._load_bundle(bundle_path)


class _FakeModel:
    def __init__(self, *, fail_embedding: bool) -> None:
        self.fail_embedding = fail_embedding

    def create_voice_clone_prompt(
        self,
        segment_path: str,
        reference_text: str,
        *,
        x_vector_only_mode: bool,
    ) -> dict[str, object]:
        return {
            "segment_path": segment_path,
            "reference_text": reference_text,
            "x_vector_only_mode": x_vector_only_mode,
        }

    def generate_voice_clone(
        self,
        target_text: str,
        language: str,
        *,
        voice_clone_prompt: dict[str, object],
    ) -> tuple[list[list[float]], int]:
        del target_text, language
        if self.fail_embedding and bool(voice_clone_prompt["x_vector_only_mode"]):
            raise RuntimeError("embedding generation failed")
        return ([[0.1, 0.2, 0.3]], 3)


def test_main_writes_manifest_and_exits_non_zero_on_partial_failure(
    script_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bundle_payload: dict[str, object],
) -> None:
    bundle_path = _write_bundle(tmp_path, bundle_payload)
    output_dir = tmp_path / "output"

    args = argparse.Namespace(
        bundle=[str(bundle_path)],
        text="Hola mundo",
        text_label="Caso Neutral",
        output_dir=str(output_dir),
        model_path="fake-model",
        device="cpu",
        include_spanish_icl=False,
    )

    class _FakeModelFactory:
        @staticmethod
        def from_pretrained(model_path: str, *, device_map: str) -> _FakeModel:
            assert model_path == "fake-model"
            assert device_map == "cpu"
            return _FakeModel(fail_embedding=True)

    monkeypatch.setattr(script_module, "_parse_args", lambda: args)
    monkeypatch.setattr(script_module, "Qwen3TTSModel", _FakeModelFactory)
    monkeypatch.setattr(script_module.sf, "write", lambda path, data, sample_rate: None)

    with pytest.raises(SystemExit) as exc:
        script_module.main()

    assert exc.value.code == 1

    manifest_path = output_dir / "caso-neutral" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert [case["status"] for case in manifest["cases"]] == ["success", "failed"]
    assert manifest["cases"][1]["error_message"] == "embedding generation failed"
    assert manifest["cases"][0]["case"]["bundle_path"] == str(bundle_path.resolve())


def test_main_succeeds_when_all_cases_succeed(
    script_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bundle_payload: dict[str, object],
) -> None:
    bundle_path = _write_bundle(tmp_path, bundle_payload)
    output_dir = tmp_path / "output"

    args = argparse.Namespace(
        bundle=[str(bundle_path)],
        text="Hola mundo",
        text_label="Caso Feliz",
        output_dir=str(output_dir),
        model_path="fake-model",
        device="cpu",
        include_spanish_icl=True,
    )

    class _FakeModelFactory:
        @staticmethod
        def from_pretrained(model_path: str, *, device_map: str) -> _FakeModel:
            assert model_path == "fake-model"
            assert device_map == "cpu"
            return _FakeModel(fail_embedding=False)

    monkeypatch.setattr(script_module, "_parse_args", lambda: args)
    monkeypatch.setattr(script_module, "Qwen3TTSModel", _FakeModelFactory)
    monkeypatch.setattr(script_module.sf, "write", lambda path, data, sample_rate: None)

    script_module.main()

    manifest_path = output_dir / "caso-feliz" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert [case["status"] for case in manifest["cases"]] == ["success", "success", "success"]
