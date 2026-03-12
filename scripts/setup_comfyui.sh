#!/bin/bash
# ComfyUI Setup Script for TTS Lab
# This script installs ComfyUI and the Qwen-TTS plugin for visual exploration

set -e

PROJECT_ROOT="/Users/felipe_gonzalez/Developer/Tts_tq"
COMFYUI_DIR="$PROJECT_ROOT/comfyui"

echo "=== ComfyUI Setup for TTS Lab ==="

# Check if ComfyUI already exists
if [ -d "$COMFYUI_DIR" ]; then
    echo "ComfyUI directory already exists at $COMFYUI_DIR"
    read -p "Do you want to reinstall? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping ComfyUI installation."
        exit 0
    fi
    rm -rf "$COMFYUI_DIR"
fi

# Clone ComfyUI
echo ""
echo "Step 1: Cloning ComfyUI..."
git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"

# Create virtual environment
echo ""
echo "Step 2: Creating virtual environment..."
cd "$COMFYUI_DIR"
python3 -m venv venv
source venv/bin/activate

# Install ComfyUI dependencies
echo ""
echo "Step 3: Installing ComfyUI dependencies..."
pip install --upgrade pip
pip install torch torchaudio transformers librosa accelerate

# Install ComfyUI-Qwen-TTS plugin
echo ""
echo "Step 4: Installing ComfyUI-Qwen-TTS plugin..."
mkdir -p custom_nodes
cd custom_nodes
git clone https://github.com/flybirdxx/ComfyUI-Qwen-TTS.git

# Install huggingface_hub for model downloads
echo ""
echo "Step 5: Installing huggingface_hub..."
pip install -U "huggingface_hub[cli]"

# Create models directory
echo ""
echo "Step 6: Creating models directory..."
mkdir -p models/qwen-tts

# Create workflows directory
mkdir -p "$COMFYUI_DIR/workflows"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To download models, run:"
echo "  cd $COMFYUI_DIR"
echo "  source venv/bin/activate"
echo "  huggingface-cli download Qwen/Qwen3-TTS-Tokenizer-12Hz --local-dir ./models/qwen-tts/Qwen3-TTS-Tokenizer-12Hz"
echo "  huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local-dir ./models/qwen-tts/Qwen3-TTS-12Hz-1.7B-CustomVoice"
echo "  huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base --local-dir ./models/qwen-tts/Qwen3-TTS-12Hz-1.7B-Base"
echo ""
echo "To start ComfyUI:"
echo "  cd $COMFYUI_DIR"
echo "  source venv/bin/activate"
echo "  python main.py --listen 0.0.0.0 --port 8188"
echo ""
echo "Then open: http://localhost:8188"
