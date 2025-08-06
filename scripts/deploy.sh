#!/bin/bash

# Deploy script for Text-to-Video project
# This script deploys the application to Kubernetes using Helm

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-text-to-video-app}"
RELEASE_NAME="${RELEASE_NAME:-text-to-video}"
CHART_PATH="${CHART_PATH:-helm/text-to-video}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
TIMEOUT="${TIMEOUT:-600s}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed or not in PATH"
        exit 1
    fi
    
    # Check kubectl connectivity
    if ! kubectl version --client &> /dev/null; then
        log_error "kubectl is not properly configured"
        exit 1
    fi
    
    log_success "All dependencies are available"
}

check_cluster() {
    log_info "Checking cluster connectivity..."
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check if we can list nodes
    if ! kubectl get nodes &> /dev/null; then
        log_error "Cannot access cluster nodes. Check permissions."
        exit 1
    fi
    
    log_success "Cluster connectivity verified"
}

check_gpu_support() {
    log_info "Checking GPU support..."
    
    GPU_NODES=$(kubectl get nodes -l accelerator -o name 2>/dev/null | wc -l)
    if [[ $GPU_NODES -eq 0 ]]; then
        log_warn "No GPU nodes found. BentoML service may not work properly."
        log_warn "Make sure you have GPU-enabled nodes with proper labels."
    else
        log_success "Found $GPU_NODES GPU-enabled nodes"
    fi
}

check_kserve() {
    log_info "Checking KServe installation..."
    
    if ! kubectl get crd inferenceservices.serving.kserve.io &> /dev/null; then
        log_error "KServe is not installed. BentoML service requires KServe."
        log_error "Install KServe: kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml"
        exit 1
    fi
    
    log_success "KServe is installed"
}

prepare_namespace() {
    log_info "Preparing namespace: $NAMESPACE"
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Creating namespace: $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
    else
        log_info "Namespace $NAMESPACE already exists"
    fi
}

deploy_app() {
    local env="$1"
    local values_file="$CHART_PATH/values-${env}.yaml"
    
    log_info "Deploying Text-to-Video application..."
    log_info "Environment: $env"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"
    
    # Check if values file exists
    if [[ ! -f "$values_file" ]]; then
        log_warn "Values file not found: $values_file"
        log_info "Using default values.yaml"
        values_file="$CHART_PATH/values.yaml"
    fi
    
    # Prepare Helm command
    local helm_cmd=(
        helm upgrade --install "$RELEASE_NAME" "$CHART_PATH"
        --namespace "$NAMESPACE"
        --create-namespace
        --values "$values_file"
        --timeout "$TIMEOUT"
        --wait
    )
    
    # Add custom image tags if provided
    if [[ -n "${FASTAPI_TAG:-}" ]]; then
        helm_cmd+=(--set "fastapi.image.tag=$FASTAPI_TAG")
    fi
    
    if [[ -n "${BENTO_TAG:-}" ]]; then
        helm_cmd+=(--set "bentoService.image.tag=$BENTO_TAG")
    fi
    
    # Add custom registry if provided
    if [[ -n "${REGISTRY:-}" ]]; then
        helm_cmd+=(--set "global.imageRegistry=$REGISTRY")
    fi
    
    # Execute deployment
    log_info "Executing: ${helm_cmd[*]}"
    "${helm_cmd[@]}"
    
    log_success "Deployment completed successfully!"
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Wait for pods to be ready
    log_info "Waiting for pods to be ready..."
    kubectl wait --for=condition=Ready pods -l app.kubernetes.io/instance="$RELEASE_NAME" -n "$NAMESPACE" --timeout=300s
    
    # Check deployment status
    log_info "Checking deployment status..."
    kubectl get all -n "$NAMESPACE" -l app.kubernetes.io/instance="$RELEASE_NAME"
    
    # Check inference services
    if kubectl get inferenceservices -n "$NAMESPACE" &> /dev/null; then
        log_info "InferenceServices status:"
        kubectl get inferenceservices -n "$NAMESPACE"
    fi
    
    log_success "Deployment verification completed"
}

get_service_info() {
    log_info "Getting service information..."
    
    # Get service endpoint
    local service_name="${RELEASE_NAME}-fastapi"
    local service_type=$(kubectl get svc "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.type}')
    
    echo ""
    log_info "Service Information:"
    echo "  Service Name: $service_name"
    echo "  Service Type: $service_type"
    
    case "$service_type" in
        "LoadBalancer")
            local external_ip=$(kubectl get svc "$service_name" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
            if [[ -n "$external_ip" ]]; then
                echo "  External IP: $external_ip"
                echo "  API URL: http://$external_ip/api/v1"
                echo "  Docs: http://$external_ip/docs"
            else
                log_warn "LoadBalancer IP is still pending..."
                echo "  Check with: kubectl get svc $service_name -n $NAMESPACE"
            fi
            ;;
        "NodePort")
            local node_port=$(kubectl get svc "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
            local node_ip=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')
            echo "  Node IP: $node_ip"
            echo "  Node Port: $node_port"
            echo "  API URL: http://$node_ip:$node_port/api/v1"
            echo "  Docs: http://$node_ip:$node_port/docs"
            ;;
        "ClusterIP")
            echo "  Cluster IP: $(kubectl get svc "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')"
            echo "  Port: $(kubectl get svc "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')"
            log_info "Use port-forward for external access:"
            echo "  kubectl port-forward svc/$service_name 8080:80 -n $NAMESPACE"
            ;;
    esac
    echo ""
}

cleanup() {
    log_info "Cleaning up deployment..."
    
    helm uninstall "$RELEASE_NAME" -n "$NAMESPACE"
    
    if [[ "${DELETE_NAMESPACE:-false}" == "true" ]]; then
        log_info "Deleting namespace: $NAMESPACE"
        kubectl delete namespace "$NAMESPACE"
    fi
    
    log_success "Cleanup completed"
}

show_logs() {
    log_info "Showing recent logs..."
    
    echo ""
    log_info "FastAPI Gateway logs:"
    kubectl logs -l app.kubernetes.io/component=fastapi-gateway -n "$NAMESPACE" --tail=20 || true
    
    echo ""
    log_info "BentoML Service logs:"
    kubectl logs -l app.kubernetes.io/component=bento-service -n "$NAMESPACE" --tail=20 || true
    
    echo ""
    log_info "Redis logs:"
    kubectl logs -l app.kubernetes.io/name=redis -n "$NAMESPACE" --tail=10 || true
}

# Main script
main() {
    case "${1:-deploy}" in
        "deploy")
            check_dependencies
            check_cluster
            check_gpu_support
            check_kserve
            prepare_namespace
            deploy_app "$ENVIRONMENT"
            verify_deployment
            get_service_info
            ;;
        "verify")
            verify_deployment
            get_service_info
            ;;
        "info")
            get_service_info
            ;;
        "logs")
            show_logs
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [deploy|verify|info|logs|cleanup|help]"
            echo ""
            echo "Commands:"
            echo "  deploy   Deploy the application (default)"
            echo "  verify   Verify existing deployment"
            echo "  info     Show service information"
            echo "  logs     Show recent logs"
            echo "  cleanup  Remove the deployment"
            echo "  help     Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  NAMESPACE        Kubernetes namespace (default: text-to-video-app)"
            echo "  RELEASE_NAME     Helm release name (default: text-to-video)"
            echo "  CHART_PATH       Path to Helm chart (default: helm/text-to-video)"
            echo "  ENVIRONMENT      Environment (dev/prod) (default: dev)"
            echo "  TIMEOUT          Deployment timeout (default: 600s)"
            echo "  FASTAPI_TAG      FastAPI image tag override"
            echo "  BENTO_TAG        BentoML image tag override"
            echo "  REGISTRY         Container registry override"
            echo "  DELETE_NAMESPACE Delete namespace on cleanup (default: false)"
            ;;
        *)
            log_error "Unknown command: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi