from __future__ import annotations

import argparse
from pathlib import Path

import soundfile as sf
from qwen_tts import Qwen3TTSModel

MODEL_PATH = "comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"
TARGET_TEXT = "Hola, soy Felipe. Esta es una prueba corta de mi voz para comparar configuraciones."

CASES = {
    "01_refv2_auto_icl": {
        "ref_audio": "voice_profiles/felipe/reference_v2.wav",
        "ref_text": "La tecnología de inteligencia artificial ha revolucionado la forma en que interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones que facilitan nuestras tareas diarias.",
        "language": "auto",
        "x_vector_only_mode": False,
    },
    "02_refv2_spanish_icl": {
        "ref_audio": "voice_profiles/felipe/reference_v2.wav",
        "ref_text": "La tecnología de inteligencia artificial ha revolucionado la forma en que interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones que facilitan nuestras tareas diarias.",
        "language": "spanish",
        "x_vector_only_mode": False,
    },
    "03_refv2_auto_embedding": {
        "ref_audio": "voice_profiles/felipe/reference_v2.wav",
        "ref_text": "La tecnología de inteligencia artificial ha revolucionado la forma en que interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones que facilitan nuestras tareas diarias.",
        "language": "auto",
        "x_vector_only_mode": True,
    },
    "04_pitch1_auto_icl": {
        "ref_audio": "voice_profiles/felipe/pitch_seg1.wav",
        "ref_text": "Buenos días, mi nombre es Felipe González. Desde mi experiencia he observado un patrón preocupante.",
        "language": "auto",
        "x_vector_only_mode": False,
    },
    "05_pitch1_spanish_icl": {
        "ref_audio": "voice_profiles/felipe/pitch_seg1.wav",
        "ref_text": "Buenos días, mi nombre es Felipe González. Desde mi experiencia he observado un patrón preocupante.",
        "language": "spanish",
        "x_vector_only_mode": False,
    },
    "06_pitch1_auto_embedding": {
        "ref_audio": "voice_profiles/felipe/pitch_seg1.wav",
        "ref_text": "Buenos días, mi nombre es Felipe González. Desde mi experiencia he observado un patrón preocupante.",
        "language": "auto",
        "x_vector_only_mode": True,
    },
    "07_pitch2_auto_icl": {
        "ref_audio": "voice_profiles/felipe/pitch_seg2.wav",
        "ref_text": "Esto coincide con evidencia reciente. La tasa de complicaciones en pacientes oncológicos es alta.",
        "language": "auto",
        "x_vector_only_mode": False,
    },
    "08_pitch3_auto_icl": {
        "ref_audio": "voice_profiles/felipe/pitch_seg3.wav",
        "ref_text": "¿Por qué esta población está tan vulnerable? Enfrenta una tormenta perfecta por la enfermedad de base.",
        "language": "auto",
        "x_vector_only_mode": False,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    args = parser.parse_args()

    case = CASES[args.case]
    output_dir = Path("output/voice_matrix")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Cargando modelo para {args.case}...", flush=True)
    model = Qwen3TTSModel.from_pretrained(MODEL_PATH, device_map="mps")

    print(f"Creando prompt para {args.case}...", flush=True)
    prompt = model.create_voice_clone_prompt(
        case["ref_audio"],
        case["ref_text"],
        x_vector_only_mode=case["x_vector_only_mode"],
    )

    print(f"Generando {args.case}...", flush=True)
    wavs, sr = model.generate_voice_clone(
        TARGET_TEXT,
        case["language"],
        voice_clone_prompt=prompt,
    )
    output_path = output_dir / f"{args.case}.wav"
    sf.write(output_path, wavs[0], sr)
    print(f"Listo: {output_path} ({len(wavs[0]) / sr:.2f}s)", flush=True)


if __name__ == "__main__":
    main()
