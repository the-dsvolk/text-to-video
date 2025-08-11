# Manual Testing Guide for BentoML Text-to-Video Service

This guide contains only verified working commands for testing the BentoML service container on a GPU machine.

## Prerequisites
```
# Remove old drivers
sudo apt-get purge '*nvidia*'
sudo apt autoremove


# Download the CUDA network repository pin file to prioritize this repo
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600

# Download and install the repository's signing key
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb

# Update your system's package list
sudo apt-get update

# Clean up the downloaded file
rm cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install cuda-drivers-570
sudo apt-get install nvidia-fabricmanager-570
sudo systemctl enable --now nvidia-fabricmanager.service

# Container toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart containerd

```
Exact page from Nvidia, look for 570.86.15
https://docs.nvidia.com/vss/latest/content/quickstart.html#install-the-nvidia-driver
sudo nvidia-ctk runtime configure --runtime=containerd



- SSH access to GPU machine with NVIDIA drivers and Docker installed
- Docker with GPU support configured


## 1. Pull Container Image ✅ WORKING

```bash
# Pull the latest BentoML service image
docker pull ghcr.io/the-dsvolk/bento-video-service:latest
```

## 2. Create Local Directories ✅ WORKING

```bash
# Create directories for video output, model weights, and cache
mkdir -p ~/video-test/videos ~/video-test/weights ~/video-test/cache

# Set permissions
chmod 755 ~/video-test/videos ~/video-test/weights ~/video-test/cache
```

## 3. Download Mochi Model Weights ✅ REQUIRED

The Mochi model requires ~42GB of weights that must be downloaded separately:

### Option A: Using Hugging Face CLI - Specific Files Only (Recommended)

```bash
# Install Hugging Face CLI
pip install --upgrade huggingface_hub[cli]

# Login to Hugging Face (optional, for better download speeds)
huggingface-cli login

# Download only the 3 required model files
cd ~/video-test/weights

# Download each file individually to avoid downloading the entire repo
huggingface-cli download genmo/mochi-1-preview decoder.safetensors --local-dir .
huggingface-cli download genmo/mochi-1-preview encoder.safetensors --local-dir .
huggingface-cli download genmo/mochi-1-preview dit.safetensors --local-dir .

# Verify downloads (should see exactly 3 files, ~42GB total)
ls -lh ~/video-test/weights/
# Expected files:
# - dit.safetensors (~40GB)
# - decoder.safetensors (~1.4GB)
# - encoder.safetensors (~389MB)
```

⚠️ **Important Notes:**
- Total download size: ~42GB
- Download time: 10-60 minutes depending on internet speed
- Ensure you have at least 50GB free disk space
- The container expects weights at `/data/weights` (mounted from `~/video-test/weights`)

## 4. Run Container with Model Weights ✅ WORKING

```bash
# Stop and remove any existing container
docker stop bento-video-service 2>/dev/null || true
docker rm bento-video-service 2>/dev/null || true
```

```bash
# Run container with model weights and optimized settings
docker run -d \
  --name bento-video-service \
  --gpus all \
  -p 3000:3000 \
  -v ~/video-test/videos:/data/videos \
  -v ~/video-test/weights:/data/weights:ro \
  -v ~/video-test/cache:/home/bentoml/.cache \
  -e SHARED_VOLUME_PATH="/data/videos" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  ghcr.io/the-dsvolk/bento-video-service:mochi-2
```

⚠️ **Key Changes:**
- Added `-v ~/video-test/weights:/data/weights:ro` for model weights (read-only)
- Updated image tag to `:mochi-2` (latest with Genmo support)
- Container will now find models at `/data/weights` and load successfully

## 5. Check Service Health ✅ WORKING

```bash
# Wait for models to load (check logs first - may take 5-10 minutes for first load)
docker logs -f bento-video-service

# Look for these success messages:
# - "Loading Mochi-1 model from /data/weights..."
# - "Mochi-1 model loaded successfully!"
# - Model memory movements (CPU ↔ GPU)

# Test health endpoint (wait for successful model loading)
curl -X POST http://localhost:3000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "text-to-video-generator-mochi",
  "model": "Mochi-1",
  "model_directory": "/data/weights",
  "cuda_available": true,
  "gpu_name": "Tesla T4",
  "gpu_memory_total": 15642329088,
  "gpu_memory_allocated": 11593857024
}
```

## 6. Mochi Video Generation Test ✅ WORKING

```bash
# Test video generation with optimized settings
JOB_ID="test-$(date +%s)"
echo "Job ID: $JOB_ID"

curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"A serene sunset over calm ocean waves\",
    \"job_id\": \"$JOB_ID\"
  }"
```


## 7. Manual Docker Execution for Debugging

```bash
# Interactive container with all volumes mounted
sudo nerdctl run -it \
  --name bento-video-service-debug \
  --gpus all \
  --network host \
  -v ~/video-test/videos:/data/videos \
  -v ~/video-test/weights:/data/weights:ro \
  -v ~/video-test/cache:/cache \
  -e SHARED_VOLUME_PATH="/data/videos" \
  -e CUDA_VISIBLE_DEVICES="0,1" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e CUDA_LAUNCH_BLOCKING=1 \
  -e HF_HOME=/cache \
  -e TRANSFORMERS_CACHE=/cache/transformers \
  --shm-size=4g \
  --user 0 \
  ghcr.io/the-dsvolk/bento-video-service:mochi-2 bash
```

### Debug Commands Inside Container:

```
/app/.venv/bin/python3 -c "
import torch
import sys
sys.path.append('.')

# Initialize CUDA
print('Initializing CUDA...')
torch.cuda.init()
print(f'CUDA ready: {torch.cuda.is_available()}')

# Import and create service
from src.service import TextToVideoGenerator
print('Creating Mochi-1 service instance...')
service = TextToVideoGenerator()
print('✅ Service created successfully!')
print('✅ Mochi-1 model loaded and ready!')
"
```

Update the code:
```bash
cat <<'EOF' >src/service.py

EOF
```

```bash
/app/.venv/bin/python3 -c "
from src.service import TextToVideoGenerator
service = TextToVideoGenerator()
print('Testing video generation...')
result = service.generate('a beautiful sunset over calm ocean waves', 'test-final-123')
print(f'Result: {result}')

# Check if the video file was created
import os
if result.get('success'):
    output_path = result.get('output_path')
    if output_path and os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f'✅ Video file created: {output_path}')
        print(f'📁 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)')
    else:
        print('❌ Video file not found')
else:
    print('❌ Generation failed:', result.get('error'))
"
```

## Notes

### Mochi Model Specifications:
- **Model**: Genmo Mochi-1 Preview (state-of-the-art text-to-video)
- **Model Size**: ~42GB total (dit: 40GB, decoder: 1.4GB, encoder: 389MB)
- **Video Output**: 480x848 resolution, 31 frames default (~2.6 seconds at 12fps)
- **GPU Memory**: ~24-30GB continuous usage (no CPU offloading for max performance)
- **Loading Time**: 5-10 minutes for initial model load (Ray initialization + model loading)

### Performance Optimizations:
- **No CPU Offloading**: Models stay on GPU for maximum performance (faster inference)
- **Tiled Spatial Decoding**: Reduces memory footprint during video decoding
- **Memory Management**: Uses `expandable_segments:True` for dynamic GPU memory allocation
- **BF16 Precision**: Uses bfloat16 for memory efficiency while maintaining quality

### Hardware Requirements:
- **Minimum**: 24GB GPU memory (e.g., RTX 4090, A100) - **REQUIRED** without CPU offloading
- **Recommended**: 32GB+ GPU memory (e.g., A100 40GB, H100) for optimal performance
- **Disk Space**: 50GB+ for model weights and temporary files
- **RAM**: 16GB+ system memory recommended

### Troubleshooting:
- Wait for "Mochi-1 model loaded successfully!" before testing
- Check `/data/weights` contains all 3 model files (dit.safetensors, decoder.safetensors, encoder.safetensors)
- Monitor GPU memory usage: `nvidia-smi` - should see ~24-30GB continuous usage
- First generation may take 5-15 minutes due to model compilation and caching
