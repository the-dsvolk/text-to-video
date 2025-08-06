#!/bin/bash

# API testing script for Text-to-Video project
# This script tests the deployed API endpoints

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-}"
NAMESPACE="${NAMESPACE:-text-to-video-app}"
SERVICE_NAME="${SERVICE_NAME:-text-to-video-fastapi}"
POLL_INTERVAL="${POLL_INTERVAL:-10}"
MAX_WAIT_TIME="${MAX_WAIT_TIME:-300}"

# Test prompts
declare -a TEST_PROMPTS=(
    "A robot painting a masterpiece, cinematic style"
    "A cat playing piano in a jazz club, vintage style"
    "Ocean waves crashing on a rocky shore at sunset"
    "A space station orbiting Earth, sci-fi style"
    "A magical forest with glowing mushrooms, fantasy style"
)

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

get_api_url() {
    if [[ -n "$API_BASE_URL" ]]; then
        echo "$API_BASE_URL"
        return
    fi
    
    log_info "Auto-detecting API URL..."
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found and API_BASE_URL not set"
        exit 1
    fi
    
    # Get service type and endpoint
    local service_type=$(kubectl get svc "$SERVICE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.type}' 2>/dev/null || echo "")
    
    if [[ -z "$service_type" ]]; then
        log_error "Service $SERVICE_NAME not found in namespace $NAMESPACE"
        exit 1
    fi
    
    case "$service_type" in
        "LoadBalancer")
            local external_ip=$(kubectl get svc "$SERVICE_NAME" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
            if [[ -n "$external_ip" ]]; then
                echo "http://$external_ip"
            else
                log_error "LoadBalancer IP not available yet"
                exit 1
            fi
            ;;
        "NodePort")
            local node_port=$(kubectl get svc "$SERVICE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
            local node_ip=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')
            echo "http://$node_ip:$node_port"
            ;;
        "ClusterIP")
            log_error "ClusterIP service detected. Use port-forward or set API_BASE_URL"
            log_info "Run: kubectl port-forward svc/$SERVICE_NAME 8080:80 -n $NAMESPACE"
            log_info "Then set: export API_BASE_URL=http://localhost:8080"
            exit 1
            ;;
        *)
            log_error "Unknown service type: $service_type"
            exit 1
            ;;
    esac
}

test_health() {
    local base_url="$1"
    
    log_info "Testing health endpoint..."
    
    local response=$(curl -s -w "%{http_code}" -o /tmp/health_response "$base_url/health")
    local http_code="${response: -3}"
    
    if [[ "$http_code" == "200" ]]; then
        log_success "Health check passed"
        cat /tmp/health_response | jq '.' 2>/dev/null || cat /tmp/health_response
        return 0
    else
        log_error "Health check failed with HTTP $http_code"
        cat /tmp/health_response
        return 1
    fi
}

submit_job() {
    local base_url="$1"
    local prompt="$2"
    
    log_info "Submitting job with prompt: '$prompt'"
    
    local payload=$(jq -n --arg prompt "$prompt" '{prompt: $prompt}')
    local response=$(curl -s -w "%{http_code}" -o /tmp/submit_response \
        -X POST "$base_url/api/v1/generate-video" \
        -H "Content-Type: application/json" \
        -d "$payload")
    
    local http_code="${response: -3}"
    
    if [[ "$http_code" == "200" ]]; then
        local job_id=$(cat /tmp/submit_response | jq -r '.job_id')
        log_success "Job submitted successfully: $job_id"
        echo "$job_id"
        return 0
    else
        log_error "Job submission failed with HTTP $http_code"
        cat /tmp/submit_response
        return 1
    fi
}

check_job_status() {
    local base_url="$1"
    local job_id="$2"
    
    local response=$(curl -s -w "%{http_code}" -o /tmp/status_response "$base_url/api/v1/status/$job_id")
    local http_code="${response: -3}"
    
    if [[ "$http_code" == "200" ]]; then
        local status=$(cat /tmp/status_response | jq -r '.status')
        echo "$status"
        return 0
    else
        log_error "Status check failed with HTTP $http_code"
        cat /tmp/status_response
        return 1
    fi
}

wait_for_completion() {
    local base_url="$1"
    local job_id="$2"
    
    log_info "Waiting for job completion: $job_id"
    
    local start_time=$(date +%s)
    local max_end_time=$((start_time + MAX_WAIT_TIME))
    
    while true; do
        local current_time=$(date +%s)
        if [[ $current_time -gt $max_end_time ]]; then
            log_error "Timeout waiting for job completion ($MAX_WAIT_TIME seconds)"
            return 1
        fi
        
        local status=$(check_job_status "$base_url" "$job_id")
        local elapsed=$((current_time - start_time))
        
        echo -ne "\r${BLUE}[INFO]${NC} Status: $status (elapsed: ${elapsed}s)"
        
        case "$status" in
            "complete")
                echo ""
                log_success "Job completed successfully"
                return 0
                ;;
            "failed")
                echo ""
                log_error "Job failed"
                return 1
                ;;
            "processing"|"pending")
                sleep "$POLL_INTERVAL"
                ;;
            *)
                echo ""
                log_error "Unknown status: $status"
                return 1
                ;;
        esac
    done
}

download_video() {
    local base_url="$1"
    local job_id="$2"
    local output_file="${3:-video_${job_id}.mp4}"
    
    log_info "Downloading video: $output_file"
    
    local response=$(curl -s -w "%{http_code}" -o "$output_file" "$base_url/api/v1/download/$job_id")
    local http_code="${response: -3}"
    
    if [[ "$http_code" == "200" ]]; then
        local file_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null || echo "unknown")
        log_success "Video downloaded: $output_file (size: $file_size bytes)"
        return 0
    else
        log_error "Download failed with HTTP $http_code"
        rm -f "$output_file"
        return 1
    fi
}

test_api_docs() {
    local base_url="$1"
    
    log_info "Testing API documentation endpoints..."
    
    # Test Swagger UI
    local response=$(curl -s -w "%{http_code}" -o /dev/null "$base_url/docs")
    local http_code="${response: -3}"
    
    if [[ "$http_code" == "200" ]]; then
        log_success "Swagger UI accessible at $base_url/docs"
    else
        log_warn "Swagger UI not accessible (HTTP $http_code)"
    fi
    
    # Test OpenAPI schema
    response=$(curl -s -w "%{http_code}" -o /dev/null "$base_url/openapi.json")
    http_code="${response: -3}"
    
    if [[ "$http_code" == "200" ]]; then
        log_success "OpenAPI schema accessible at $base_url/openapi.json"
    else
        log_warn "OpenAPI schema not accessible (HTTP $http_code)"
    fi
}

run_single_test() {
    local base_url="$1"
    local prompt="$2"
    
    echo ""
    log_info "=== Running single test ==="
    
    # Submit job
    local job_id=$(submit_job "$base_url" "$prompt")
    if [[ $? -ne 0 ]]; then
        return 1
    fi
    
    # Wait for completion
    if ! wait_for_completion "$base_url" "$job_id"; then
        return 1
    fi
    
    # Download video
    if ! download_video "$base_url" "$job_id" "test_video.mp4"; then
        return 1
    fi
    
    log_success "Single test completed successfully"
    return 0
}

run_load_test() {
    local base_url="$1"
    local num_jobs="${2:-3}"
    
    echo ""
    log_info "=== Running load test with $num_jobs concurrent jobs ==="
    
    local job_ids=()
    
    # Submit multiple jobs
    for i in $(seq 1 "$num_jobs"); do
        local prompt_index=$((i % ${#TEST_PROMPTS[@]}))
        local prompt="${TEST_PROMPTS[$prompt_index]}"
        
        local job_id=$(submit_job "$base_url" "$prompt")
        if [[ $? -eq 0 ]]; then
            job_ids+=("$job_id")
        fi
        
        sleep 1 # Small delay between submissions
    done
    
    log_info "Submitted ${#job_ids[@]} jobs"
    
    # Wait for all jobs to complete
    local completed=0
    local failed=0
    
    for job_id in "${job_ids[@]}"; do
        if wait_for_completion "$base_url" "$job_id"; then
            ((completed++))
            download_video "$base_url" "$job_id" "load_test_${job_id}.mp4" || true
        else
            ((failed++))
        fi
    done
    
    log_info "Load test results: $completed completed, $failed failed"
    
    if [[ $failed -eq 0 ]]; then
        log_success "Load test completed successfully"
        return 0
    else
        log_error "Load test had failures"
        return 1
    fi
}

# Main script
main() {
    # Check dependencies
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed"
        exit 1
    fi
    
    # Get API URL
    local base_url=$(get_api_url)
    log_info "Using API URL: $base_url"
    
    case "${1:-health}" in
        "health")
            test_health "$base_url"
            ;;
        "docs")
            test_api_docs "$base_url"
            ;;
        "single")
            local prompt="${2:-${TEST_PROMPTS[0]}}"
            run_single_test "$base_url" "$prompt"
            ;;
        "load")
            local num_jobs="${2:-3}"
            run_load_test "$base_url" "$num_jobs"
            ;;
        "full")
            test_health "$base_url" && \
            test_api_docs "$base_url" && \
            run_single_test "$base_url" "${TEST_PROMPTS[0]}" && \
            run_load_test "$base_url" "2"
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [health|docs|single|load|full|help] [args...]"
            echo ""
            echo "Commands:"
            echo "  health              Test health endpoint"
            echo "  docs                Test API documentation endpoints"
            echo "  single [prompt]     Run single video generation test"
            echo "  load [num_jobs]     Run load test with multiple jobs"
            echo "  full                Run all tests"
            echo "  help                Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  API_BASE_URL        Base URL for API (auto-detected if not set)"
            echo "  NAMESPACE           Kubernetes namespace (default: text-to-video-app)"
            echo "  SERVICE_NAME        Kubernetes service name (default: text-to-video-fastapi)"
            echo "  POLL_INTERVAL       Status polling interval in seconds (default: 10)"
            echo "  MAX_WAIT_TIME       Maximum wait time for job completion (default: 300)"
            echo ""
            echo "Examples:"
            echo "  $0 health"
            echo "  $0 single 'A cat playing piano'"
            echo "  $0 load 5"
            echo "  API_BASE_URL=http://localhost:8080 $0 full"
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