"""Improved FastAPI Gateway - combining best practices from both implementations."""

import os
import uuid
from typing import Dict
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# --- Configuration ---
# The internal Kubernetes URL for the KServe inference service
KSERVE_URL = os.environ.get(
    "KSERVE_URL",
    "http://text-to-video-generator.text-to-video-app.svc.cluster.local/v1/models/text-to-video-generator:predict",
)
# The path where the PersistentVolume is mounted inside this pod
VIDEO_STORAGE_PATH = os.environ.get("SHARED_VOLUME_PATH", "/data/videos")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Text-to-Video API Gateway",
    description="Gateway service for text-to-video generation using BentoML and KServe",
    version="0.1.0",
)

# --- Pydantic Models ---


class GenerationRequest(BaseModel):
    """Request model for video generation."""

    prompt: str = Field(
        ...,
        description="Text prompt for video generation",
        min_length=1,
        max_length=1000,
        examples=["A robot painting a masterpiece, cinematic style"],
    )


class JobResponse(BaseModel):
    """Response model for job submission."""

    message: str = Field(..., examples=["Job submitted successfully."])
    job_id: str = Field(..., examples=["123e4567-e89b-12d3-a456-426614174000"])


class JobStatus(BaseModel):
    """Response model for job status."""

    status: str = Field(..., examples=["processing"])


# Ensure the directory for storing videos exists
os.makedirs(VIDEO_STORAGE_PATH, exist_ok=True)


# --- Helper Function to call Inference Service ---
def call_inference_service(prompt: str, job_id: str) -> None:
    """
    Sends a request to the KServe/BentoML service to start video generation.
    This is a blocking call that will run in a background task.
    """
    print(f"[{job_id}] Sending request to inference service for prompt: '{prompt}'")
    try:
        payload = {"prompt": prompt, "job_id": job_id}
        response = requests.post(KSERVE_URL, json=payload, timeout=900)  # 15 minute timeout
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            print(f"[{job_id}] Inference service call completed successfully.")
        else:
            print(f"[{job_id}] Inference service returned error: {result.get('error', 'Unknown error')}")
    except requests.exceptions.RequestException as e:
        print(f"[{job_id}] Error calling inference service: {e}")
        # You could implement a mechanism to mark the job as 'failed' here
        # For now, we just log the error. The status will remain 'processing'.


# --- API Endpoints ---
@app.post("/generate-video/", response_model=JobResponse, status_code=202)
async def submit_generation_job(request: GenerationRequest, background_tasks: BackgroundTasks) -> JobResponse:
    """
    Accepts a prompt, generates a unique job ID, and starts the video
    generation process in the background.
    """
    job_id = str(uuid.uuid4())
    print(f"Received job {job_id} for prompt: '{request.prompt}'")

    # Add the long-running video generation task to the background
    background_tasks.add_task(call_inference_service, request.prompt, job_id)
    return JobResponse(message="Job submitted successfully.", job_id=job_id)


@app.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    """
    Checks if the video file for a given job ID has been created.
    Returns the current status of the generation job.
    """
    video_path = Path(VIDEO_STORAGE_PATH) / f"{job_id}.mp4"

    if video_path.exists():
        return JobStatus(status="complete")
    else:
        # Could add more sophisticated status tracking here
        # For now, we assume if file doesn't exist, it's still processing
        return JobStatus(status="processing")


@app.get("/download/{job_id}")
async def download_video(job_id: str) -> FileResponse:
    """
    Serves the generated video file for download if it exists.
    """
    video_path = Path(VIDEO_STORAGE_PATH) / f"{job_id}.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found or is still processing.")

    return FileResponse(path=str(video_path), media_type="video/mp4", filename=f"video_{job_id}.mp4")


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "fastapi-gateway", "version": "0.1.0"}


@app.get("/")
async def read_root() -> Dict[str, str]:
    """Root endpoint with API information."""
    return {
        "message": "Welcome to the Text-to-Video API Gateway",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# --- For development ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
