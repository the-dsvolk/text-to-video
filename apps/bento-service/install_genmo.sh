#!/bin/bash
echo "Installing pillow and Genmo Mochi with correct index strategy (without flash-attn)..."

# Check what's available in the environment
echo "Available Python installations:"
which python3
which python
ls -la /app/.venv/bin/ | grep python

echo "Checking for package managers:"
which pip || echo "pip not found"
which uv || echo "uv not found"

# Use uv to install to the virtual environment (not --system)
echo "Installing to BentoML virtual environment using uv..."
uv pip install --index-strategy unsafe-best-match \
  --extra-index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  pillow==9.5.0 \
  git+https://github.com/genmoai/mochi.git --no-deps

echo "Installing genmo dependencies manually (excluding flash-attn but including ray)..."
uv pip install --index-strategy unsafe-best-match \
  --extra-index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  accelerate \
  diffusers \
  transformers \
  datasets \
  click \
  omegaconf \
  einops \
  pyyaml \
  ray[default]

echo "Pillow and Genmo Mochi packages installed successfully (without flash-attn/triton)!"
echo "📋 Note: Model weights (42GB+) need to be downloaded separately at runtime"
echo "📋 Use persistent volumes or init containers for model storage in production"
