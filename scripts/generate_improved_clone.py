#!/usr/bin/env python3
"""
Generar voz clonada mejorada con ICL mode + transcripción exacta
"""
from qwen_tts import Qwen3TTSModel
import soundfile as sf
from pathlib import Path

# Configuración
REF_AUDIO = "voice_profiles/felipe/reference_v2_fixed.wav"
REF_TEXT = "La presencia artificial ha revolucionado la forma en que interactuamos con los discursivos. Cada día es cubrimos nuevas habitaciones que disponiten necesarias diarias."
OUTPUT_DIR = Path("output/improved")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Textos de prueba
TEST_TEXTS = [
    "Hola, esta es mi voz clonada con máxima calidad.",
    "La tecnología ha avanzado significativamente en los últimos años.",
    "Bienvenidos a este nuevo proyecto de inteligencia artificial.",
]

print("Cargando modelo Qwen3-TTS Base...")
model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device_map="mps",
)

print(f"Audio de referencia: {REF_AUDIO}")
print(f"Transcripción: {REF_TEXT}")
print()

for i, text in enumerate(TEST_TEXTS, 1):
    print(f"Generando texto {i}/{len(TEST_TEXTS)}: {text[:50]}...")
    
    # Full ICL mode (máxima calidad)
    wavs, sr = model.generate_voice_clone(
        text=text,
        language="Spanish",
        ref_audio=REF_AUDIO,
        ref_text=REF_TEXT,  # Transcripción exacta
        x_vector_only_mode=False  # Full ICL mode
    )
    
    output_path = OUTPUT_DIR / f"improved_icl_{i:02d}.wav"
    sf.write(output_path, wavs[0], sr)
    
    duration = len(wavs[0]) / sr
    print(f"  ✅ {output_path} ({duration:.2f}s)")

print()
print(f"Completado. Audios en: {OUTPUT_DIR}")
