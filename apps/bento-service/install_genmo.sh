#!/bin/bash
echo "Installing pillow and Genmo Mochi with correct index strategy (without flash-attn)..."
uv pip install --system --index-strategy unsafe-best-match \
  --extra-index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  pillow==9.5.0 \
  git+https://github.com/genmoai/mochi.git --no-deps

echo "Installing genmo dependencies manually (excluding flash-attn)..."
uv pip install --system --index-strategy unsafe-best-match \
  --extra-index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  accelerate \
  diffusers \
  transformers \
  datasets \
  click \
  omegaconf \
  einops \
  pyyaml

echo "Pillow and Genmo Mochi packages installed successfully (without flash-attn/triton)!"
