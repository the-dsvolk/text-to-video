# Deployment Guide

This guide covers deploying the Text-to-Video generation service to Kubernetes using Helm charts.

## Prerequisites

### Required Tools
- **kubectl**: Kubernetes command-line tool
- **Helm**: Kubernetes package manager (v3.12+)
- **Docker**: For building container images
- **GPU-enabled Kubernetes cluster**: With NVIDIA GPU support

### Cluster Requirements
- **Kubernetes**: v1.24+
- **GPU Nodes**: At least one node with NVIDIA GPU
- **Storage**: ReadWriteMany storage class for shared volumes
- **KServe**: Installed for BentoML inference service
- **NVIDIA Device Plugin**: For GPU scheduling

### Optional Components
- **Istio**: Service mesh for advanced traffic management
- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Visualization and dashboards
- **ELK Stack**: Centralized logging

## Installation Steps

### 1. Cluster Preparation

#### Install KServe
```bash
# Install KServe (if not already installed)
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve-runtimes.yaml
```

#### Verify GPU Support
```bash
# Check GPU nodes
kubectl get nodes -l accelerator=nvidia
kubectl describe node <gpu-node-name>
```

### 2. Container Images

#### Option A: Use Pre-built Images (Recommended)
```bash
# Images are automatically built via GitHub Actions
# Latest images:
# - ghcr.io/the-dmitry-s-volkov/fastapi-video-gateway:latest
# - ghcr.io/the-dmitry-s-volkov/bento-video-service:latest
```

#### Option B: Build Images Locally
```bash
# Build FastAPI Gateway
cd apps/fastapi-gateway
docker build -t ghcr.io/the-dmitry-s-volkov/fastapi-video-gateway:latest .
docker push ghcr.io/the-dmitry-s-volkov/fastapi-video-gateway:latest

# Build BentoML Service
cd apps/bento-service
bentoml build
BENTO_TAG=$(bentoml list text_to_video_generator -o json | jq -r '.[0].tag')
bentoml containerize $BENTO_TAG -t ghcr.io/the-dmitry-s-volkov/bento-video-service:latest
docker push ghcr.io/the-dmitry-s-volkov/bento-video-service:latest
```

### 3. Helm Deployment

#### Development Environment
```bash
# Deploy to development
helm upgrade --install text-to-video-dev helm/text-to-video \
  --values helm/text-to-video/values-dev.yaml \
  --namespace text-to-video-dev \
  --create-namespace
```

#### Production Environment
```bash
# Deploy to production
helm upgrade --install text-to-video-prod helm/text-to-video \
  --values helm/text-to-video/values-prod.yaml \
  --namespace text-to-video-prod \
  --create-namespace \
  --set fastapi.image.tag=v1.0.0 \
  --set bentoService.image.tag=v1.0.0
```

#### Custom Configuration
```bash
# Deploy with custom values
helm upgrade --install text-to-video helm/text-to-video \
  --set fastapi.replicaCount=3 \
  --set bentoService.autoscaling.maxReplicas=5 \
  --set storage.pvc.size=200Gi \
  --namespace text-to-video \
  --create-namespace
```

## Configuration Options

### Environment-Specific Values

#### Development (`values-dev.yaml`)
- Single replicas for cost optimization
- NodePort service for local access
- Reduced resource requirements
- Debug mode enabled

#### Production (`values-prod.yaml`)
- Multiple replicas for high availability
- LoadBalancer with SSL termination
- Full resource allocation
- Monitoring enabled

### Key Configuration Parameters

#### FastAPI Gateway
```yaml
fastapi:
  replicaCount: 2
  image:
    repository: ghcr.io/the-dmitry-s-volkov/fastapi-video-gateway
    tag: "latest"
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
```

#### BentoML Service
```yaml
bentoService:
  image:
    repository: ghcr.io/the-dmitry-s-volkov/bento-video-service
    tag: "latest"
  resources:
    limits:
      nvidia.com/gpu: 1
      memory: 16Gi
  autoscaling:
    minReplicas: 0  # Scale to zero
    maxReplicas: 3
```

#### Storage Configuration
```yaml
storage:
  pvc:
    size: 100Gi
    storageClass: "fast-ssd"
    accessMode: ReadWriteMany
```

## Verification

### Check Deployment Status
```bash
# Check all resources
kubectl get all -n text-to-video-app

# Check specific components
kubectl get pods -n text-to-video-app
kubectl get services -n text-to-video-app
kubectl get inferenceservices -n text-to-video-app
kubectl get pvc -n text-to-video-app
```

### Test the API
```bash
# Get service endpoint
export SERVICE_IP=$(kubectl get svc -n text-to-video-app text-to-video-fastapi -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Submit test job
curl -X POST "http://$SERVICE_IP/api/v1/generate-video" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A robot painting a masterpiece, cinematic style"}'

# Check API documentation
curl "http://$SERVICE_IP/docs"
```

### Monitor Logs
```bash
# FastAPI Gateway logs
kubectl logs -f deployment/text-to-video-fastapi -n text-to-video-app

# BentoML Service logs
kubectl logs -f -l serving.kserve.io/inferenceservice=text-to-video-bento -n text-to-video-app

# Redis logs
kubectl logs -f statefulset/text-to-video-redis-master -n text-to-video-app
```

## Scaling Operations

### Manual Scaling
```bash
# Scale FastAPI Gateway
kubectl scale deployment text-to-video-fastapi --replicas=5 -n text-to-video-app

# Update BentoML autoscaling
kubectl patch inferenceservice text-to-video-bento -n text-to-video-app --type='merge' -p='{"metadata":{"annotations":{"autoscaling.knative.dev/maxScale":"5"}}}'
```

### Resource Updates
```bash
# Update resource limits
helm upgrade text-to-video helm/text-to-video \
  --reuse-values \
  --set bentoService.resources.limits.memory=32Gi \
  --namespace text-to-video-app
```

## Troubleshooting

### Common Issues

#### GPU Not Available
```bash
# Check GPU node labels
kubectl get nodes -o yaml | grep -A 5 nvidia.com/gpu

# Check NVIDIA device plugin
kubectl get daemonset -n kube-system nvidia-device-plugin-daemonset
```

#### BentoML Service Not Starting
```bash
# Check inference service status
kubectl describe inferenceservice text-to-video-bento -n text-to-video-app

# Check Knative serving logs
kubectl logs -n knative-serving -l app=controller
```

#### Storage Issues
```bash
# Check PVC status
kubectl describe pvc shared-videos-pvc -n text-to-video-app

# Check storage class
kubectl get storageclass
```

### Debugging Commands
```bash
# Get pod logs with errors
kubectl logs --previous deployment/text-to-video-fastapi -n text-to-video-app

# Exec into pod for debugging
kubectl exec -it deployment/text-to-video-fastapi -n text-to-video-app -- /bin/bash

# Check resource usage
kubectl top pods -n text-to-video-app
kubectl top nodes
```

## Maintenance

### Updates and Upgrades
```bash
# Update to new version
helm upgrade text-to-video helm/text-to-video \
  --set fastapi.image.tag=v1.1.0 \
  --set bentoService.image.tag=v1.1.0 \
  --namespace text-to-video-app

# Rollback if needed
helm rollback text-to-video 1 -n text-to-video-app
```

### Backup and Recovery
```bash
# Backup Helm release
helm get values text-to-video -n text-to-video-app > backup-values.yaml

# Create PVC snapshot (depends on storage provider)
kubectl apply -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: shared-videos-snapshot
  namespace: text-to-video-app
spec:
  source:
    persistentVolumeClaimName: shared-videos-pvc
EOF
```

### Monitoring Setup
```bash
# Enable ServiceMonitor for Prometheus
helm upgrade text-to-video helm/text-to-video \
  --reuse-values \
  --set monitoring.enabled=true \
  --set monitoring.serviceMonitor.enabled=true \
  --namespace text-to-video-app
```
