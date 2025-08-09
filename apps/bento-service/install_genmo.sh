#!/bin/bash
echo "Installing Genmo Mochi package with correct index strategy..."
uv pip install --index-strategy unsafe-best-match \
  --extra-index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  git+https://github.com/genmoai/mochi.git
echo "Genmo Mochi package installed successfully!"
