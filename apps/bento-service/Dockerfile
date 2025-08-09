# Multi-stage build for BentoML Text-to-Video Service
# This is an alternative to using bentoml containerize

FROM nvcr.io/nvidia/pytorch:25.01-py3 as base

# Install system dependencies
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get -y --no-install-recommends install \
    vim htop nvtop python3-dev python3-pip git pciutils sysstat \
    curl wget ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install BentoML (PyTorch already optimized in base image)
RUN pip3 install --no-cache-dir bentoml>=1.1.11

# Set working directory
WORKDIR /workspace

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

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
