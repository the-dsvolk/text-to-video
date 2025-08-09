# Manual Testing Guide for BentoML Text-to-Video Service (Mochi-1)

This guide contains verified working commands for testing the BentoML service with Mochi-1 model on a GPU machine.

## Prerequisites
- SSH access to GPU machine with NVIDIA drivers and Docker installed
- Docker with GPU support configured
- **MINIMUM**: 22GB VRAM GPU (optimized with PyTorch 2.8.0 + no virtual env)
- **RECOMMENDED**: H100 80GB (optimal), RTX 4090 (24GB), A6000 (48GB)

## 1. Pull Container Image ✅ WORKING

```bash
# Pull the latest BentoML service image
docker pull ghcr.io/the-dsvolk/bento-video-service:latest
# or
sudo nerdctl pull ghcr.io/the-dsvolk/bento-video-service:mochi-1
```

## 2. Create Local Directories ✅ WORKING

```bash
# Create directories for video output and shared data
mkdir -p ~/video-test/videos ~/video-test/data ~/video-test/cache

# Set permissions
chmod 755 ~/video-test/videos ~/video-test/data ~/video-test/cache
```

## 3. Run Container with Mochi-1 Optimization ⚠️ UPDATED

# Stop and remove current container

```bash
docker stop bento-video-service
docker rm bento-video-service
```

### Option A: Single High-VRAM GPU (24GB+ required)
```bash
# Run container with Mochi-1 optimized settings for single GPU
docker run -d \
  --name bento-video-service \
  --gpus all \
  -p 3000:3000 \
  -v ~/video-test/videos:/data/videos \
  -v ~/video-test/cache:/cache \
  -e SHARED_VOLUME_PATH="/data/videos" \
  -e CUDA_VISIBLE_DEVICES="0" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e CUDA_LAUNCH_BLOCKING=1 \
  --shm-size=2g \
  ghcr.io/the-dsvolk/bento-video-service:latest
```

### Option B: Dual GPU Setup (12GB+ each)
```bash
# Run container with dual GPU allocation
docker run -d \
  --name bento-video-service \
  --gpus all \
  -p 3000:3000 \
  -v ~/video-test/videos:/data/videos \
  -v ~/video-test/cache:/cache \
  -e SHARED_VOLUME_PATH="/data/videos" \
  -e CUDA_VISIBLE_DEVICES="0,1" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e CUDA_LAUNCH_BLOCKING=1 \
  --shm-size=4g \
  ghcr.io/the-dsvolk/bento-video-service:latest
```

### Option C: netrdctl
```bash
 sudo nerdctl run -d \
  --name bento-video-service \
  --network host \
  --gpus all \
  -v ~/video-test/videos:/data/videos \
  -v ~/video-test/cache:/cache \
  -e SHARED_VOLUME_PATH="/data/videos" \
  -e CUDA_VISIBLE_DEVICES="0,1" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e CUDA_LAUNCH_BLOCKING=1 \
  --shm-size=4g \
  ghcr.io/the-dsvolk/bento-video-service:mochi-1
fc4199a4e1034f2055498d85e49c8bad69fa2e03415039208d4c66da5a982ca2
ubuntu@g471:~$ sudo nerdctl ps
CONTAINER ID    IMAGE                                             COMMAND                   CREATED           STATUS    PORTS    NAMES
fc4199

````

## 4. Check Service Health ✅ WORKING

```bash
# Wait for models to load (check logs first)
docker logs bento-video-service

# Test health endpoint
curl -X POST http://localhost:3000/health
```

Expected response (Mochi-1):
```json
{
  "status": "healthy",
  "service": "text-to-video-generator-mochi-1",
  "model": "genmo/mochi-1-preview",
  "variant": "bf16",
  "device": "cuda",
  "cuda_available": true,
  "video_export_method": "mochi_built_in",
  "memory_optimizations": {
    "cpu_offload": true,
    "vae_tiling": true,
    "autocast": true
  },
  "gpu_name": "NVIDIA RTX 4090",
  "gpu_memory_total": 25438961664,
  "gpu_memory_allocated": 22318439424,
  "recommended_vram": "22GB minimum"
}
```


## Sample Generation Test ✅ WORKING

```bash
# Test video generation with optimized settings
JOB_ID="test-$(date +%s)"
echo "Job ID: $JOB_ID"

curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"A serene sunset over calm ocean waves\",
    \"job_id\": \"$JOB_ID\",
    \"num_frames\": 84
  }"

# Expected response (Mochi-1):
# {
#   "status": "complete",
#   "success": true,
#   "job_id": "test-1234567890",
#   "output_path": "/data/videos/test-1234567890.mp4",
#   "num_frames": 84,
#   "duration_seconds": 2.8,
#   "fps": 30,
#   "message": "High-quality video generated successfully with Mochi-1"
# }
```


## Manual execution from Docker (Mochi-1) ⚠️ UPDATED

```bash
# Test Mochi-1 service directly in container (NO virtual environment)
docker exec -it bento-video-service python3 -c "
import sys; sys.path.append('/workspace')
from src.service import TextToVideoGeneratorMochi
service = TextToVideoGeneratorMochi()
print('Testing Mochi-1 video generation...')
print('⚠️  This will take several minutes and requires 22GB+ VRAM')
result = service.generate('a beautiful sunset over calm ocean waves', 'test-mochi-123', num_frames=84)
print(f'Result: {result}')

# Check if the video file was created
import os
if result.get('success'):
    output_path = result.get('output_path')
    if output_path and os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f'✅ Video file created: {output_path}')
        print(f'📁 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)')
        print(f'🎬 Duration: {result.get(\"duration_seconds\", \"unknown\")}s at {result.get(\"fps\", \"unknown\")} fps')
        print(f'🎞️  Frames: {result.get(\"num_frames\", \"unknown\")}')
    else:
        print('❌ Video file not found')
else:
    print('❌ Generation failed:', result.get('error'))
"
```

## Notes (Mochi-1 Update)

### ⚠️ **IMPORTANT: Hardware Requirements Changed**
- **NEW**: Uses Mochi-1 model (~10B parameters) instead of Tiny-SD + SVD
- **Memory Requirement**: 22GB+ VRAM (bfloat16 variant with optimizations)
- **NOT compatible** with Tesla T4 (15GB) - requires high-end GPUs
- **Recommended GPUs**: H100 80GB (optimal), RTX 4090 (24GB), A6000 (48GB), V100 32GB

### ✅ **What's Improved**
- **Quality**: State-of-the-art video generation with high-fidelity motion
- **Resolution**: Higher resolution support than previous SD+SVD pipeline
- **Frame Count**: 84 frames (~2.8s at 30fps) vs 14 frames previously
- **Prompt Adherence**: Better understanding and following of text prompts

### 🔧 **Technical Changes**
- Service class: `TextToVideoGenerator` → `TextToVideoGeneratorMochi`
- **Base image**: PyTorch 2.8.0 + CUDA 12.8 + cuDNN 9 (optimized for H100)
- **Virtual environment**: DISABLED - uses system Python directly (space optimized)
- **Memory optimizations**: CPU offload + VAE tiling + autocast enabled
- **Cache location**: `/cache` (not `/home/bentoml/.cache`)
- Export method: Uses Mochi's built-in video export (no ffmpeg fallback needed)
- Generation time: Longer due to higher quality (expect 5-15 minutes per video)

### 🚨 **Breaking Changes**
- **Tesla T4 NO LONGER SUPPORTED** - insufficient VRAM
- API response format updated with additional metadata
- Health check response includes Mochi-1 specific information
- Wait for "Mochi-1 model loaded successfully" in logs before testing
