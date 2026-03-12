from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import soundfile as sf
from qwen_tts import Qwen3TTSModel

MODEL_PATH = "comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"
OUTPUT_DIR = Path("output/voice_matrix")
TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."


@dataclass(frozen=True)
class Case:
    name: str
    ref_audio: str
    ref_text: str
    language: str
    x_vector_only_mode: bool


CASES: tuple[Case, ...] = (
    Case(
        name="01_refv2_auto_icl",
        ref_audio="voice_profiles/felipe/reference_v2.wav",
        ref_text=(
            "La tecnología de inteligencia artificial ha revolucionado la forma en que "
            "interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones "
            "que facilitan nuestras tareas diarias."
        ),
        language="auto",
        x_vector_only_mode=False,
    ),
    Case(
        name="02_refv2_spanish_icl",
        ref_audio="voice_profiles/felipe/reference_v2.wav",
        ref_text=(
            "La tecnología de inteligencia artificial ha revolucionado la forma en que "
            "interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones "
            "que facilitan nuestras tareas diarias."
        ),
        language="spanish",
        x_vector_only_mode=False,
    ),
    Case(
        name="03_refv2_auto_embedding",
        ref_audio="voice_profiles/felipe/reference_v2.wav",
        ref_text=(
            "La tecnología de inteligencia artificial ha revolucionado la forma en que "
            "interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones "
            "que facilitan nuestras tareas diarias."
        ),
        language="auto",
        x_vector_only_mode=True,
    ),
    Case(
        name="04_pitch1_auto_icl",
        ref_audio="voice_profiles/felipe/pitch_seg1.wav",
        ref_text=(
            "Buenos días, mi nombre es Felipe González. "
            "Desde mi experiencia he observado un patrón preocupante."
        ),
        language="auto",
        x_vector_only_mode=False,
    ),
    Case(
        name="05_pitch1_spanish_icl",
        ref_audio="voice_profiles/felipe/pitch_seg1.wav",
        ref_text=(
            "Buenos días, mi nombre es Felipe González. "
            "Desde mi experiencia he observado un patrón preocupante."
        ),
        language="spanish",
        x_vector_only_mode=False,
    ),
    Case(
        name="06_pitch1_auto_embedding",
        ref_audio="voice_profiles/felipe/pitch_seg1.wav",
        ref_text=(
            "Buenos días, mi nombre es Felipe González. "
            "Desde mi experiencia he observado un patrón preocupante."
        ),
        language="auto",
        x_vector_only_mode=True,
    ),
    Case(
        name="07_pitch2_auto_icl",
        ref_audio="voice_profiles/felipe/pitch_seg2.wav",
        ref_text=(
            "Esto coincide con evidencia reciente. "
            "La tasa de complicaciones en pacientes oncológicos es alta."
        ),
        language="auto",
        x_vector_only_mode=False,
    ),
    Case(
        name="08_pitch3_auto_icl",
        ref_audio="voice_profiles/felipe/pitch_seg3.wav",
        ref_text=(
            "¿Por qué esta población está tan vulnerable? "
            "Enfrenta una tormenta perfecta por la enfermedad de base."
        ),
        language="auto",
        x_vector_only_mode=False,
    ),
)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Cargando modelo...", flush=True)
    model = Qwen3TTSModel.from_pretrained(MODEL_PATH, device_map="mps")
    print("Modelo cargado", flush=True)

    results: list[dict[str, object]] = []

    for case in CASES:
        print(f"Generando {case.name}...", flush=True)
        prompt = model.create_voice_clone_prompt(
            case.ref_audio,
            case.ref_text,
            x_vector_only_mode=case.x_vector_only_mode,
        )
        wavs, sr = model.generate_voice_clone(
            TARGET_TEXT,
            case.language,
            voice_clone_prompt=prompt,
        )
        output_path = OUTPUT_DIR / f"{case.name}.wav"
        sf.write(output_path, wavs[0], sr)
        duration_seconds = len(wavs[0]) / sr
        result = asdict(case)
        result["output_path"] = str(output_path)
        result["duration_seconds"] = round(duration_seconds, 2)
        results.append(result)
        print(f"  -> {output_path} ({duration_seconds:.2f}s)", flush=True)

    manifest = {
        "target_text": TARGET_TEXT,
        "model_path": MODEL_PATH,
        "cases": results,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Manifest: {manifest_path}", flush=True)
    print("Completado", flush=True)


if __name__ == "__main__":
    main()
