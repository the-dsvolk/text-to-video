#!/bin/bash
echo "Installing pillow and Genmo Mochi with correct index strategy..."
uv pip install --index-strategy unsafe-best-match \
  --extra-index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  pillow==9.5.0 \
  git+https://github.com/genmoai/mochi.git
echo "Pillow and Genmo Mochi packages installed successfully!"
