#!/bin/bash
# Grabar audio de referencia optimizado para voice cloning
# REQUISITOS: 10-15 segundos, sin ruido, hablar claro

echo "=========================================="
echo "  GRABACIÓN DE REFERENCIA PARA CLONACIÓN"
echo "=========================================="
echo ""
echo "INSTRUCCIONES:"
echo "1. Usa un lugar SILENCIOSO"
echo "2. Habla CLARO y a ritmo NATURAL"
echo "3. Lee EXACTAMENTE el texto que aparece"
echo "4. No hagas pausas largas"
echo ""
echo "TEXTO A LEER (10-15 segundos):"
echo "----------------------------------------"
echo "La tecnología de inteligencia artificial ha revolucionado la forma en que interactuamos con los dispositivos. Cada día descubrimos nuevas aplicaciones que facilitan nuestras tareas diarias."
echo "----------------------------------------"
echo ""
read -p "Presiona ENTER cuando estés listo para grabar..."

# Grabar 15 segundos
echo ""
echo "🔴 GRABANDO... Habla AHORA"
sox -t coreaudio "Micrófono de iPhone 13 mini" -r 24000 -c 1 -b 16 voice_profiles/felipe/reference_v2.wav trim 0 15

echo ""
echo "✅ Grabación completada: voice_profiles/felipe/reference_v2.wav"
echo ""
echo "Verificando..."
sox --info voice_profiles/felipe/reference_v2.wav

echo ""
echo "Para escuchar: afplay voice_profiles/felipe/reference_v2.wav"
