"""Improved BentoML service combining both implementations' best practices."""

import os
import bentoml
from pathlib import Path

# Lazy imports to avoid dependency issues during build
with bentoml.importing():
    import torch
    from diffusers import StableDiffusionXLPipeline, StableVideoDiffusionPipeline
    from diffusers.utils import export_to_video


# Configuration - The path where the PersistentVolume is mounted
VIDEO_STORAGE_PATH = os.getenv("SHARED_VOLUME_PATH", "/data/videos")


@bentoml.service(
    resources={"gpu": 1, "gpu_type": "nvidia-l4", "memory": "16Gi"},
    traffic={"timeout": 900},  # 15-minute timeout for long generation jobs
)
class TextToVideoGenerator:
    """Improved Text-to-Video generation service using SDXL + SVD pipeline."""

    def __init__(self) -> None:
        """Load all models into memory when the service first starts."""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.video_storage_path = Path(VIDEO_STORAGE_PATH)
        self.video_storage_path.mkdir(parents=True, exist_ok=True)

        print("Loading models... This may take a few minutes.")
        # Use float16 for memory efficiency
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        # Load Text-to-Image Model (SDXL)
        print("Loading Stable Diffusion XL model...")
        self.sdxl_pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=self.dtype,
            variant="fp16" if self.device == "cuda" else None,
            use_safetensors=True,
        )
        self.sdxl_pipe.to(self.device)

        # Enable memory efficient attention if available (safety check)
        if hasattr(self.sdxl_pipe, "enable_xformers_memory_efficient_attention"):
            try:
                self.sdxl_pipe.enable_xformers_memory_efficient_attention()
                print("XFormers memory efficient attention enabled for SDXL")
            except Exception as e:
                print(f"Could not enable XFormers: {e}")

        print("SDXL model loaded successfully.")

        # Load Image-to-Video Model (SVD)
        print("Loading Stable Video Diffusion model...")
        self.svd_pipe = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=self.dtype,
            variant="fp16" if self.device == "cuda" else None,
            use_safetensors=True,
        )
        self.svd_pipe.to(self.device)
        print("SVD model loaded successfully.")
        print("All models loaded successfully.")

    @bentoml.api
    def generate(self, prompt: str, job_id: str) -> dict:
        """Generate video from text prompt.

        Args:
            prompt: Text description for video generation
            job_id: Unique identifier for this generation job

        Returns:
            Dict with generation status and output path
        """
        print(f"[{job_id}] Starting generation for prompt: '{prompt}'")

        try:
            # Step 1: Generate keyframe with SDXL
            print(f"[{job_id}] Generating keyframe image...")
            image = self.sdxl_pipe(
                prompt=prompt,
                num_inference_steps=25,
                height=576,
                width=1024,
                guidance_scale=7.5,
            ).images[0]
            print(f"[{job_id}] Keyframe generated.")

            # Step 2: Animate with SVD
            print(f"[{job_id}] Animating image with SVD...")
            video_frames = self.svd_pipe(
                image,
                num_frames=25,
                decode_chunk_size=8,  # Memory optimization
            ).frames[0]
            print(f"[{job_id}] Animation complete.")

            # Step 3: Save to shared volume using diffusers' built-in export
            output_path = self.video_storage_path / f"{job_id}.mp4"
            print(f"[{job_id}] Exporting video to {output_path}...")
            export_to_video(video_frames, str(output_path), fps=7)
            print(f"[{job_id}] Video saved successfully.")

            return {
                "status": "complete",
                "success": True,
                "job_id": job_id,
                "output_path": str(output_path),
                "message": "Video generated successfully",
            }

        except Exception as e:
            print(f"[{job_id}] Error during generation: {e}")
            return {
                "status": "failed",
                "success": False,
                "job_id": job_id,
                "error": str(e),
            }

    @bentoml.api
    def health(self) -> dict:
        """Health check endpoint with detailed device information."""
        info = {
            "status": "healthy",
            "service": "text-to-video-generator",
            "device": self.device,
            "cuda_available": torch.cuda.is_available(),
        }

        if torch.cuda.is_available():
            info.update(
                {
                    "gpu_name": torch.cuda.get_device_name(0),
                    "gpu_memory_total": torch.cuda.get_device_properties(0).total_memory,
                    "gpu_memory_allocated": torch.cuda.memory_allocated(0),
                }
            )

        return info
