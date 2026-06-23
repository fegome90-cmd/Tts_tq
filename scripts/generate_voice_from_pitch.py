#!/usr/bin/env python3
"""
Generar voz clonada desde pitch.mp3 (audio real del examen)
"""
from pathlib import Path

import soundfile as sf
from qwen_tts import Qwen3TTSModel

# Configuración con NUEVO audio de referencia (pitch.mp3)
REF_AUDIO = "voice_profiles/felipe/pitch_segment_15s_fixed.wav"
REF_TEXT = "Buenos días. Mi nombre es Felipe González, enfermero clínico del Instituto Oncológico FALC. Desde mi experiencia en IANISA he observado un patrón preocupante, el catetertic ampliamente utilizado por pacientes matroncológicos para quineterapia."

OUTPUT_DIR = Path("output/from_pitch")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Textos de prueba
TEST_TEXTS = [
    "Hola, esta es mi voz clonada desde el audio del pitch.",
    "La tecnología ha avanzado significativamente en los últimos años.",
    "Bienvenidos a este nuevo proyecto de inteligencia artificial.",
    "Mi nombre es Felipe y soy enfermero clínico especializado en oncología.",
]

print("=" * 60)
print("GENERANDO VOZ CLONADA DESDE PITCH.MP3")
print("=" * 60)
print()
print("Audio de referencia: pitch_segment_15s_fixed.wav")
print("Transcripción (Whisper small):")
print(f"  {REF_TEXT[:80]}...")
print()

print("Cargando modelo Qwen3-TTS Base (1.7B)...")
model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device_map="mps",
)

for i, text in enumerate(TEST_TEXTS, 1):
    print(f"\n[{i}/{len(TEST_TEXTS)}] Generando: {text[:50]}...")

    # Full ICL mode (máxima calidad)
    wavs, sr = model.generate_voice_clone(
        text=text,
        language="Spanish",
        ref_audio=REF_AUDIO,
        ref_text=REF_TEXT,
        x_vector_only_mode=False  # Full ICL mode
    )

    output_path = OUTPUT_DIR / f"pitch_clone_{i:02d}.wav"
    sf.write(output_path, wavs[0], sr)

    duration = len(wavs[0]) / sr
    print(f"  ✅ {output_path.name} ({duration:.2f}s)")

print()
print("=" * 60)
print("COMPLETADO")
print("=" * 60)
print(f"\nAudios guardados en: {OUTPUT_DIR}")
print("\nComparar con versión anterior:")
print("  - output/from_pitch/ (NUEVO - desde pitch.mp3)")
print("  - output/improved/ (ANTERIOR - desde reference_v2.wav)")
