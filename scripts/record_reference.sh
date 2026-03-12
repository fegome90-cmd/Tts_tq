#!/bin/bash
# Record reference audio for voice cloning
# Usage: ./scripts/record_reference.sh [output_file] [duration_seconds]

set -e

OUTPUT_FILE="${1:-voice_profiles/felipe/reference.wav}"
DURATION="${2:-15}"

echo "=== Recording Reference Audio ==="
echo "Output: $OUTPUT_FILE"
echo "Duration: ${DURATION}s"
echo ""
echo "Available microphones:"
echo "  [0] iPhone 13 mini mic"
echo "  [1] MacBook Pro mic"
echo ""
read -p "Select microphone [0-1, default=0]: " MIC_CHOICE
MIC_CHOICE="${MIC_CHOICE:-0}"

echo ""
echo "Prepare to speak the following text:"
echo "---"
echo "Hola, esta es una grabación de referencia para crear un perfil de voz. El objetivo es capturar el tono, ritmo y características naturales de mi voz para poder clonarla con precisión. Es importante hablar de manera clara y natural durante la grabación."
echo "---"
echo ""
read -p "Press ENTER to start recording..."

echo ""
echo "Recording... Speak now!"
ffmpeg -f avfoundation -i ":$MIC_CHOICE" -t "$DURATION" -ar 16000 -ac 1 -y "$OUTPUT_FILE"

echo ""
echo "Recording saved to: $OUTPUT_FILE"
echo ""
echo "To test the clone, run:"
echo "  uv run tts-clone voice $OUTPUT_FILE -r \"Hola, esta es una grabación de referencia para crear un perfil de voz. El objetivo es capturar el tono, ritmo y características naturales de mi voz para poder clonarla con precisión. Es importante hablar de manera clara y natural durante la grabación.\" -t \"Prueba de voz clonada.\" -o output/test.wav"
