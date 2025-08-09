# Multi-stage build for BentoML Text-to-Video Service
# This is an alternative to using bentoml containerize

FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime as base

# Install system dependencies (Python 3.11 already available in base image)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    jq \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install BentoML
RUN python -m pip install --upgrade pip \
    && python -m pip install bentoml==1.1.11

# Set working directory
WORKDIR /workspace

# Copy requirements first for better caching
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY bentofile.yaml .

# Set environment variables for Hugging Face caching
ENV PYTHONPATH=/workspace
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/huggingface/transformers
ENV HF_DATASETS_CACHE=/tmp/huggingface/datasets
ENV CUDA_VISIBLE_DEVICES=0

# Create cache directories
RUN mkdir -p /tmp/huggingface/transformers /tmp/huggingface/datasets

# Create non-root user
RUN useradd --create-home --shell /bin/bash bentoml \
    && chown -R bentoml:bentoml /workspace /tmp/huggingface

# Switch to non-root user
USER bentoml

# Build the Bento
RUN bentoml build

# Get the latest bento tag and serve it
RUN echo '#!/bin/bash' > /workspace/start.sh \
    && echo 'BENTO_TAG=$(bentoml list text_to_video_generator -o json | jq -r ".[0].tag")' >> /workspace/start.sh \
    && echo 'bentoml serve $BENTO_TAG --host 0.0.0.0 --port 3000' >> /workspace/start.sh \
    && chmod +x /workspace/start.sh

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

EXPOSE 3000

CMD ["/workspace/start.sh"]
