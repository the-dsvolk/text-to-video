# Space-optimized single-stage build for BentoML Text-to-Video Service
FROM nvcr.io/nvidia/pytorch:25.01-py3

# Install system dependencies and cleanup in single layer
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get -y --no-install-recommends install \
    git curl wget ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install BentoML and dependencies with cleanup
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir bentoml>=1.1.11 && \
    pip3 install --no-cache-dir -r /tmp/requirements.txt && \
    pip3 cache purge && \
    rm -rf /tmp/* /var/tmp/* ~/.cache/pip/* /root/.cache/pip/*

# Set working directory
WORKDIR /workspace

# Copy source code
COPY src/ ./src/
COPY bentofile.yaml .

# Set environment variables for Hugging Face caching (use tmpfs mount)
ENV PYTHONPATH=/workspace
ENV HF_HOME=/cache
ENV TRANSFORMERS_CACHE=/cache/transformers
ENV HF_DATASETS_CACHE=/cache/datasets
ENV CUDA_VISIBLE_DEVICES=0
ENV PYTHONUNBUFFERED=1

# Create non-root user and directories in single layer
RUN useradd --create-home --shell /bin/bash bentoml && \
    mkdir -p /cache/transformers /cache/datasets && \
    chown -R bentoml:bentoml /workspace /cache

# Switch to non-root user
USER bentoml

# Build the Bento (cleanup build artifacts)
RUN bentoml build && \
    rm -rf ~/.cache/pip/* /tmp/* /var/tmp/*

# Create optimized startup script
RUN echo '#!/bin/bash\n\
set -e\n\
BENTO_TAG=$(bentoml list text_to_video_generator_mochi -o json | jq -r ".[0].tag")\n\
echo "Starting Mochi-1 service with tag: $BENTO_TAG"\n\
exec bentoml serve $BENTO_TAG --host 0.0.0.0 --port 3000' > /workspace/start.sh && \
    chmod +x /workspace/start.sh

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

EXPOSE 3000

CMD ["/workspace/start.sh"]
