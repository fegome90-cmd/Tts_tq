from __future__ import annotations

import soundfile as sf
from qwen_tts import Qwen3TTSModel

MODEL_PATH = "comfyui/models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"
REF_AUDIO = "voice_profiles/felipe/pitch_seg1.wav"
REF_TEXT = (
    "Buenos días, mi nombre es Felipe González. "
    "Desde mi experiencia he observado un patrón preocupante."
)
TARGET_TEXT = (
    "Hola, soy Felipe González. Esta es una prueba de voz clonada usando el audio limpio del pitch."
)

print("Cargando modelo...", flush=True)
model = Qwen3TTSModel.from_pretrained(MODEL_PATH, device_map="mps")
print("Modelo cargado", flush=True)

print("Creando prompt ICL...", flush=True)
prompt_icl = model.create_voice_clone_prompt(
    REF_AUDIO,
    REF_TEXT,
    x_vector_only_mode=False,
)
print("Generando ICL...", flush=True)
wavs, sr = model.generate_voice_clone(
    TARGET_TEXT,
    "spanish",
    voice_clone_prompt=prompt_icl,
)
sf.write("output/pitch_icl.wav", wavs[0], sr)
print(f"ICL listo: {len(wavs[0]) / sr:.2f}s", flush=True)

print("Creando prompt embedding-only...", flush=True)
prompt_embedding = model.create_voice_clone_prompt(
    REF_AUDIO,
    REF_TEXT,
    x_vector_only_mode=True,
)
print("Generando embedding-only...", flush=True)
wavs, sr = model.generate_voice_clone(
    TARGET_TEXT,
    "spanish",
    voice_clone_prompt=prompt_embedding,
)
sf.write("output/pitch_embedding.wav", wavs[0], sr)
print(f"Embedding listo: {len(wavs[0]) / sr:.2f}s", flush=True)

print("Completado", flush=True)
