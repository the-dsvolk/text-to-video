# Manual Testing Guide for BentoML Text-to-Video Service

This guide contains only verified working commands for testing the BentoML service container on a GPU machine.

## Prerequisites
- SSH access to GPU machine with NVIDIA drivers and Docker installed
- Docker with GPU support configured

## 1. Pull Container Image ✅ WORKING

```bash
# Pull the latest BentoML service image
docker pull ghcr.io/the-dsvolk/bento-video-service:latest
```

## 2. Create Local Directories ✅ WORKING

```bash
# Create directories for video output and shared data
mkdir -p ~/video-test/videos ~/video-test/data ~/video-test/cache

# Set permissions
chmod 755 ~/video-test/videos ~/video-test/data ~/video-test/cache
```

## 3. Run Container with Memory Optimization ✅ WORKING

# Stop and remove current container

```bash
docker stop bento-video-service
docker rm bento-video-service
```

```bash
# Run container with optimized PyTorch CUDA memory settings
docker run -d \
  --name bento-video-service \
  --gpus all \
  -p 3000:3000 \
  -v ~/video-test/videos:/data/videos \
  -v ~/video-test/cache:/home/bentoml/.cache \
  -e SHARED_VOLUME_PATH="/data/videos" \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  ghcr.io/the-dsvolk/bento-video-service:latest
```

## 4. Check Service Health ✅ WORKING

```bash
# Wait for models to load (check logs first)
docker logs bento-video-service

# Test health endpoint
curl -X POST http://localhost:3000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "text-to-video-generator",
  "device": "cuda",
  "cuda_available": true,
  "gpu_name": "Tesla T4",
  "gpu_memory_total": 15642329088,
  "gpu_memory_allocated": 11593857024
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
    \"job_id\": \"$JOB_ID\"
  }"
```


## Manual execution from Dcoker
```bash
sudo nerdctl run -it   --name bento-video-service   --gpus all   --network host   -v ~/video-test/videos:/data/videos   -v ~/video-test/cache:/cache   -e SHARED_VOLUME_PATH="/data/videos"   -e CUDA_VISIBLE_DEVICES="0,1"   -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   -e CUDA_LAUNCH_BLOCKING=1   -e HF_HOME=/cache   -e TRANSFORMERS_CACHE=/cache/transformers   --shm-size=4g   --user 0   ghcr.io/the-dsvolk/bento-video-service:mochi-2 bash
```

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

- Latest code uses Tiny-SD model (2.8GB) instead of SDXL (6GB+) for 55% memory reduction
- Generates 512x512 images instead of 1024x576 for memory efficiency
- Reduced inference steps and video frames for Tesla T4 compatibility
- The service needs ~8GB GPU memory instead of ~13GB with optimizations
- Tesla T4 with 14.6GB total memory should now work without memory errors
- Wait for "All models loaded successfully" message in logs before testing
