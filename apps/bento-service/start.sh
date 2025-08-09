#!/bin/bash
set -e

echo "🚀 Starting Mochi-1 Text-to-Video Service"
echo "📍 Using system Python (no virtual environment)"

# Ensure we're using system Python and BentoML
export VIRTUAL_ENV=""
export PYTHONPATH="/workspace:/usr/local/lib/python3.11/site-packages"

# Use system python and bentoml directly
PYTHON_BIN="/usr/local/bin/python3"
BENTOML_BIN="/usr/local/bin/bentoml"

echo "🔍 Python version: $($PYTHON_BIN --version)"
echo "🔍 BentoML location: $BENTOML_BIN"

# Get the Bento tag
BENTO_TAG=$($BENTOML_BIN list text_to_video_generator_mochi -o json | jq -r ".[0].tag")
echo "📦 Found Bento tag: $BENTO_TAG"

echo "🌟 Starting Mochi-1 service on 0.0.0.0:3000"
exec $BENTOML_BIN serve $BENTO_TAG --host 0.0.0.0 --port 3000
