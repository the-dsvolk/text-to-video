# Kubernetes Setup Commands

## Prerequisites Installation

### 1. Install KServe
```bash
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.2/kserve.yaml
```
**Purpose**: Install KServe CRDs and controller for BentoML inference service deployment

### 2. Install cert-manager
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.3/cert-manager.yaml
```
**Purpose**: Install cert-manager which is required dependency for KServe certificate management

### 3. Wait for cert-manager
```bash
kubectl wait --for=condition=Available deployment/cert-manager-webhook -n cert-manager --timeout=300s
```
**Purpose**: Ensure cert-manager webhook is ready before proceeding with KServe installation
