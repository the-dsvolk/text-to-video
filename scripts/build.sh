#!/bin/bash

# Build script for Text-to-Video project
# This script builds both FastAPI Gateway and BentoML Service containers

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="${REGISTRY:-ghcr.io}"
REPO_OWNER="${GITHUB_REPOSITORY_OWNER:-the-dmitry-volkov}"
TAG="${TAG:-latest}"
PLATFORM="${PLATFORM:-linux/amd64,linux/arm64}"

# Image names
FASTAPI_IMAGE="${REGISTRY}/${REPO_OWNER}/fastapi-video-gateway"
BENTO_IMAGE="${REGISTRY}/${REPO_OWNER}/bento-video-service"

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
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v bentoml &> /dev/null; then
        log_warn "BentoML is not installed. Installing..."
        pip install bentoml==1.1.11
    fi
    
    if ! docker buildx version &> /dev/null; then
        log_error "Docker Buildx is not available"
        exit 1
    fi
    
    log_success "All dependencies are available"
}

build_fastapi() {
    log_info "Building FastAPI Gateway image..."
    
    cd apps/fastapi-gateway
    
    docker buildx build \
        --platform "$PLATFORM" \
        --tag "${FASTAPI_IMAGE}:${TAG}" \
        --push \
        .
    
    cd ../..
    log_success "FastAPI Gateway image built: ${FASTAPI_IMAGE}:${TAG}"
}

build_bento() {
    log_info "Building BentoML Service..."
    
    cd apps/bento-service
    
    # Choose build method
    if [[ "${BENTO_BUILD_METHOD:-bentoml}" == "docker" ]]; then
        log_info "Using direct Docker build method..."
        docker buildx build \
            --platform "$PLATFORM" \
            --tag "${BENTO_IMAGE}:${TAG}" \
            --push \
            .
    else
        log_info "Using BentoML containerize method..."
        
        # Build Bento
        log_info "Building Bento package..."
        bentoml build
        
        # Get the latest Bento tag
        BENTO_TAG=$(bentoml list text_to_video_generator -o json | jq -r '.[0].tag')
        log_info "Built Bento: $BENTO_TAG"
        
        # Containerize Bento
        log_info "Containerizing Bento..."
        TEMP_TAG="temp-bento:latest"
        bentoml containerize "$BENTO_TAG" -t "$TEMP_TAG"
        
        # Multi-platform build (if supported)
        if [[ "$PLATFORM" == *","* ]]; then
            log_warn "Multi-platform build for BentoML requires manual setup"
            log_info "Building for linux/amd64 only..."
            docker tag "$TEMP_TAG" "${BENTO_IMAGE}:${TAG}"
            docker push "${BENTO_IMAGE}:${TAG}"
        else
            docker tag "$TEMP_TAG" "${BENTO_IMAGE}:${TAG}"
            docker push "${BENTO_IMAGE}:${TAG}"
        fi
    fi
    
    cd ../..
    log_success "BentoML Service image built: ${BENTO_IMAGE}:${TAG}"
}

build_all() {
    log_info "Starting build process..."
    log_info "Registry: $REGISTRY"
    log_info "Repository Owner: $REPO_OWNER"
    log_info "Tag: $TAG"
    log_info "Platform: $PLATFORM"
    
    check_dependencies
    
    # Check if we should build specific components
    if [[ "${1:-all}" == "fastapi" ]]; then
        build_fastapi
    elif [[ "${1:-all}" == "bento" ]]; then
        build_bento
    else
        build_fastapi
        build_bento
    fi
    
    log_success "Build completed successfully!"
    log_info "Images built:"
    log_info "  - ${FASTAPI_IMAGE}:${TAG}"
    log_info "  - ${BENTO_IMAGE}:${TAG}"
}

# Docker login helper
docker_login() {
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        log_info "Logging in to GitHub Container Registry..."
        echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
    elif [[ -n "${DOCKER_PASSWORD:-}" ]]; then
        log_info "Logging in to Docker registry..."
        echo "$DOCKER_PASSWORD" | docker login "$REGISTRY" -u "$DOCKER_USERNAME" --password-stdin
    else
        log_warn "No authentication token provided. Make sure you're logged in to the registry."
    fi
}

# Main script
main() {
    case "${1:-all}" in
        "fastapi")
            docker_login
            build_fastapi
            ;;
        "bento")
            docker_login
            build_bento
            ;;
        "all")
            docker_login
            build_all
            ;;
        "login")
            docker_login
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [fastapi|bento|all|login|help]"
            echo ""
            echo "Commands:"
            echo "  fastapi  Build only FastAPI Gateway image"
            echo "  bento    Build only BentoML Service image"
            echo "  all      Build all images (default)"
            echo "  login    Login to container registry"
            echo "  help     Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  REGISTRY             Container registry (default: ghcr.io)"
            echo "  REPO_OWNER          Repository owner (default: the-dmitry-volkov)"
            echo "  TAG                 Image tag (default: latest)"
            echo "  PLATFORM            Build platform (default: linux/amd64,linux/arm64)"
            echo "  BENTO_BUILD_METHOD  BentoML build method: 'bentoml' or 'docker' (default: bentoml)"
            echo "  GITHUB_TOKEN        GitHub token for ghcr.io authentication"
            echo "  DOCKER_USERNAME     Docker registry username"
            echo "  DOCKER_PASSWORD     Docker registry password"
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