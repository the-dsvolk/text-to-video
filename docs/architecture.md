# Architecture Overview

## System Architecture

The Text-to-Video generation system is built as a cloud-native microservices architecture on Kubernetes, leveraging modern AI/ML frameworks and container orchestration.

## Components

### 1. FastAPI Gateway Service
- **Purpose**: Public-facing API gateway for video generation requests
- **Technology**: FastAPI, Python 3.12
- **Features**:
  - RESTful API endpoints
  - Job management and status tracking
  - File serving for video downloads
  - Horizontal autoscaling
  - Health checks and monitoring

### 2. BentoML Inference Service
- **Purpose**: AI/ML inference service for text-to-video generation
- **Technology**: BentoML, Hugging Face transformers, PyTorch
- **Features**:
  - GPU-accelerated inference
  - Serverless autoscaling with KServe
  - Scale-to-zero capabilities
  - Model management and caching

### 3. Shared Storage
- **Purpose**: Persistent storage for generated video files
- **Technology**: Kubernetes PersistentVolume (ReadWriteMany)
- **Features**:
  - Shared between FastAPI and BentoML services
  - Scalable storage backend
  - High-performance file access

### 4. Redis Cache
- **Purpose**: Job status management and caching
- **Technology**: Redis with Bitnami Helm chart
- **Features**:
  - Fast job status lookups
  - Distributed caching
  - High availability with replicas

## AI/ML Pipeline

### Text-to-Video Generation Flow

1. **Text-to-Image**: Stable Diffusion XL (SDXL)
   - Input: Text prompt
   - Output: High-quality 1024x576 initial image
   - Model: `stabilityai/stable-diffusion-xl-base-1.0`

2. **Image-to-Video**: Stable Video Diffusion (SVD)
   - Input: Generated image
   - Output: Video sequence (25 frames)
   - Model: `stabilityai/stable-video-diffusion-img2vid-xt`

3. **Video Encoding**: ImageIO with FFmpeg
   - Input: Frame sequence
   - Output: MP4 video file
   - Codec: H.264 with optimized settings

## Deployment Architecture

### Kubernetes Resources

```
Namespace: text-to-video-app
├── FastAPI Gateway
│   ├── Deployment (2-10 replicas)
│   ├── Service (LoadBalancer)
│   ├── HorizontalPodAutoscaler
│   └── Ingress (optional)
├── BentoML Service
│   ├── InferenceService (KServe)
│   ├── GPU node assignment
│   └── Serverless autoscaling
├── Storage
│   ├── PersistentVolume
│   └── PersistentVolumeClaim
└── Redis
    ├── Master (1 replica)
    └── Replica (1-2 replicas)
```

### Network Flow

1. **External Request** → Load Balancer → FastAPI Gateway
2. **FastAPI Gateway** → Redis (job status)
3. **FastAPI Gateway** → BentoML Service (async inference)
4. **BentoML Service** → Shared Storage (video output)
5. **FastAPI Gateway** → Shared Storage (video serving)

## Scalability Design

### Horizontal Scaling
- **FastAPI Gateway**: 2-20 replicas based on CPU utilization
- **BentoML Service**: 0-5 replicas with scale-to-zero
- **Redis**: Master-replica setup for read scaling

### Vertical Scaling
- **GPU Resources**: 1-2 GPUs per BentoML pod
- **Memory**: 8-32GB for inference workloads
- **Storage**: Auto-expanding persistent volumes

### Auto-scaling Triggers
- **CPU Utilization**: 70-80% threshold
- **Memory Utilization**: 80% threshold
- **Request Queue**: Queue depth monitoring
- **Scale-to-Zero**: 5-10 minute timeout

## Security Architecture

### Container Security
- **Non-root containers**: All services run as non-root users
- **Security contexts**: Restricted filesystem access
- **Image scanning**: Trivy security scans in CI/CD
- **Minimal base images**: Alpine/slim base images

### Network Security
- **Service mesh**: Optional Istio integration
- **Network policies**: Pod-to-pod traffic control
- **TLS encryption**: HTTPS/TLS for external traffic
- **Secrets management**: Kubernetes secrets for credentials

### Access Control
- **RBAC**: Kubernetes role-based access control
- **Service accounts**: Dedicated service accounts per component
- **Image pull secrets**: Private registry authentication

## Monitoring and Observability

### Metrics
- **Application metrics**: FastAPI/BentoML custom metrics
- **Infrastructure metrics**: CPU, memory, GPU utilization
- **Business metrics**: Generation success rate, latency

### Logging
- **Structured logging**: JSON format for all services
- **Centralized collection**: Fluentd/Fluent Bit
- **Log aggregation**: ELK stack or similar

### Tracing
- **Distributed tracing**: OpenTelemetry integration
- **Request correlation**: End-to-end request tracking
- **Performance profiling**: Latency breakdown analysis

## Disaster Recovery

### Backup Strategy
- **Storage backups**: Regular PV snapshots
- **Redis persistence**: RDB/AOF backups
- **Configuration backups**: Helm chart versioning

### High Availability
- **Multi-zone deployment**: AZ-aware pod scheduling
- **Database clustering**: Redis Sentinel/Cluster
- **Load balancing**: Multiple gateway replicas

### Recovery Procedures
- **Automated failover**: Kubernetes self-healing
- **Manual recovery**: Documented procedures
- **Data recovery**: Backup restoration processes