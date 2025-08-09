#!/bin/bash
set -e
echo "Installing packages directly to system Python (no virtual environment)"

# Install BentoML and ML packages directly to system Python
pip install --no-cache-dir \
    bentoml>=1.1.11 \
    diffusers>=0.30.0 \
    transformers>=4.46.3 \
    accelerate>=0.30.0 \
    sentencepiece>=0.2.0 \
    xformers>=0.0.25 \
    safetensors>=0.4.0 \
    huggingface-hub>=0.20.0 \
    "imageio[ffmpeg]>=2.25.0" \
    addict>=2.4.0 \
    av==13.1.0 \
    click>=8.1.7 \
    einops>=0.8.0 \
    gradio>=3.36.1 \
    moviepy==1.0.3 \
    omegaconf>=2.3.0 \
    pillow==9.5.0 \
    pyyaml>=6.0.2 \
    ray>=2.37.0 \
    setuptools>=75.2.0

echo "All packages installed to system Python successfully"
