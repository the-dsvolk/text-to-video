#!/bin/bash
set -e
echo "Installing packages directly to system Python (no virtual environment)"

# Install BentoML and ML packages directly to system Python
pip install --no-cache-dir bentoml>=1.1.11 diffusers>=0.30.0 transformers>=4.46.3 accelerate>=0.30.0 sentencepiece>=0.1.97 xformers>=0.0.25 safetensors>=0.4.0 huggingface-hub>=0.20.0 "imageio[ffmpeg]>=2.25.0"

echo "All packages installed to system Python successfully"
