# API Documentation

## Overview

The Text-to-Video API provides RESTful endpoints for generating videos from text prompts using AI models. The service follows an asynchronous pattern where jobs are submitted, processed, and results are retrieved via separate endpoints.

## Base URL

```
http://<SERVICE_IP>/api/v1
```

## Authentication

Currently, the API does not require authentication. In production environments, consider implementing:
- API keys
- JWT tokens
- OAuth 2.0
- Rate limiting

## Endpoints

### Health Check

#### `GET /health`

Check the health status of the FastAPI Gateway service.

**Response:**
```json
{
  "status": "healthy",
  "service": "fastapi-gateway"
}
```

### Video Generation

#### `POST /api/v1/generate-video`

Submit a text-to-video generation job.

**Request Body:**
```json
{
  "prompt": "A robot painting a masterpiece, cinematic style",
  "duration": 3.0,
  "fps": 24,
  "width": 512,
  "height": 512
}
```

**Parameters:**
- `prompt` (required): Text description for video generation (1-1000 characters)
- `duration` (optional): Video duration in seconds (1.0-10.0, default: 3.0)
- `fps` (optional): Frames per second (12-30, default: 24)
- `width` (optional): Video width in pixels (256-1024, default: 512)
- `height` (optional): Video height in pixels (256-1024, default: 512)

**Response:**
```json
{
  "message": "Job submitted successfully.",
  "job_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Status Codes:**
- `200 OK`: Job submitted successfully
- `400 Bad Request`: Invalid request parameters
- `500 Internal Server Error`: Server error

### Job Status

#### `GET /api/v1/status/{job_id}`

Check the status of a video generation job.

**Path Parameters:**
- `job_id`: Unique job identifier returned from the generation request

**Response:**
```json
{
  "status": "processing"
}
```

**Status Values:**
- `pending`: Job is queued and waiting to start
- `processing`: Job is currently being processed
- `complete`: Job completed successfully
- `failed`: Job failed with an error

**Status Codes:**
- `200 OK`: Status retrieved successfully
- `404 Not Found`: Job ID not found

### Video Download

#### `GET /api/v1/download/{job_id}`

Download the generated video file.

**Path Parameters:**
- `job_id`: Unique job identifier for the completed job

**Response:**
- **Content-Type:** `video/mp4`
- **Content-Disposition:** `attachment; filename="video_{job_id}.mp4"`

**Status Codes:**
- `200 OK`: Video file returned
- `202 Accepted`: Video still processing
- `404 Not Found`: Job not found
- `500 Internal Server Error`: Video file not found (system error)

## API Usage Examples

### Python Example

```python
import requests
import time
import json

# API base URL
BASE_URL = "http://your-service-ip/api/v1"

def generate_video(prompt):
    """Generate a video from text prompt."""
    
    # Submit generation job
    response = requests.post(
        f"{BASE_URL}/generate-video",
        json={"prompt": prompt}
    )
    response.raise_for_status()
    
    job_data = response.json()
    job_id = job_data["job_id"]
    print(f"Job submitted: {job_id}")
    
    # Poll for completion
    while True:
        status_response = requests.get(f"{BASE_URL}/status/{job_id}")
        status_response.raise_for_status()
        
        status = status_response.json()["status"]
        print(f"Status: {status}")
        
        if status == "complete":
            break
        elif status == "failed":
            raise Exception("Job failed")
        
        time.sleep(10)  # Wait 10 seconds before checking again
    
    # Download video
    video_response = requests.get(f"{BASE_URL}/download/{job_id}")
    video_response.raise_for_status()
    
    with open(f"video_{job_id}.mp4", "wb") as f:
        f.write(video_response.content)
    
    print(f"Video saved: video_{job_id}.mp4")
    return job_id

# Example usage
job_id = generate_video("A robot painting a masterpiece, cinematic style")
```

### JavaScript Example

```javascript
async function generateVideo(prompt) {
    const baseUrl = 'http://your-service-ip/api/v1';
    
    // Submit generation job
    const response = await fetch(`${baseUrl}/generate-video`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt })
    });
    
    const jobData = await response.json();
    const jobId = jobData.job_id;
    console.log(`Job submitted: ${jobId}`);
    
    // Poll for completion
    while (true) {
        const statusResponse = await fetch(`${baseUrl}/status/${jobId}`);
        const statusData = await statusResponse.json();
        
        console.log(`Status: ${statusData.status}`);
        
        if (statusData.status === 'complete') {
            break;
        } else if (statusData.status === 'failed') {
            throw new Error('Job failed');
        }
        
        await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10 seconds
    }
    
    // Download video
    const videoResponse = await fetch(`${baseUrl}/download/${jobId}`);
    const videoBlob = await videoResponse.blob();
    
    // Create download link
    const url = window.URL.createObjectURL(videoBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `video_${jobId}.mp4`;
    a.click();
    
    console.log('Video downloaded');
    return jobId;
}

// Example usage
generateVideo('A robot painting a masterpiece, cinematic style');
```

### cURL Examples

```bash
# Submit job
curl -X POST "http://your-service-ip/api/v1/generate-video" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A robot painting a masterpiece, cinematic style"}'

# Check status
curl "http://your-service-ip/api/v1/status/123e4567-e89b-12d3-a456-426614174000"

# Download video
curl -o video.mp4 "http://your-service-ip/api/v1/download/123e4567-e89b-12d3-a456-426614174000"
```

## Rate Limiting

Currently, there are no enforced rate limits. However, consider these guidelines:

- **Concurrent Jobs**: Limit to 2-3 concurrent jobs per client
- **Request Rate**: Maximum 10 requests per minute for job submission
- **Polling Frequency**: Check status every 10-30 seconds, not more frequently

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": [
    {
      "loc": ["body", "prompt"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

#### 404 Not Found
```json
{
  "detail": "Job not found"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

### Best Practices

1. **Always check HTTP status codes** before processing responses
2. **Implement exponential backoff** for status polling
3. **Handle network timeouts** gracefully
4. **Validate input parameters** before sending requests
5. **Store job IDs** for later retrieval

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://your-service-ip/docs`
- **ReDoc**: `http://your-service-ip/redoc`
- **OpenAPI Schema**: `http://your-service-ip/openapi.json`

## Monitoring and Metrics

### Health Endpoints

- **FastAPI Health**: `GET /health`
- **BentoML Health**: Available through KServe inference service

### Custom Metrics

The API exposes Prometheus metrics at `/metrics` (if monitoring is enabled):

- `video_generation_requests_total`: Total number of generation requests
- `video_generation_duration_seconds`: Time taken for video generation
- `video_generation_errors_total`: Total number of failed generations
- `active_jobs_gauge`: Number of currently active jobs

## Webhooks (Future Enhancement)

Consider implementing webhooks for job completion notifications:

```json
{
  "event": "job_completed",
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "complete",
  "download_url": "http://your-service-ip/api/v1/download/123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2024-01-15T10:30:00Z"
}
```