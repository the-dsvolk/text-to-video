"""Improved BentoML service combining both implementations' best practices."""

import os
import bentoml
from pathlib import Path

# Import dependencies at runtime only


# Configuration - The path where the PersistentVolume is mounted
VIDEO_STORAGE_PATH = os.getenv("SHARED_VOLUME_PATH", "/data/videos")


@bentoml.service(
    resources={"gpu": 1, "gpu_type": "nvidia-l4", "memory": "16Gi"},
    traffic={"timeout": 900},  # 15-minute timeout for long generation jobs
)
class TextToVideoGenerator:
    """Memory-optimized Text-to-Video generation service using Tiny-SD + SVD pipeline."""

    def __init__(self) -> None:
        """Load all models into memory when the service first starts."""
        # Import dependencies at runtime
        import torch
        from diffusers import StableDiffusionPipeline, StableVideoDiffusionPipeline
        from diffusers.utils import export_to_video
        
        # Store imports as instance variables for use in other methods
        self.torch = torch
        self.StableDiffusionPipeline = StableDiffusionPipeline
        self.StableVideoDiffusionPipeline = StableVideoDiffusionPipeline
        self.export_to_video = export_to_video
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.video_storage_path = Path(VIDEO_STORAGE_PATH)
        self.video_storage_path.mkdir(parents=True, exist_ok=True)

        print("Loading models... This may take a few minutes.")
        # Use float16 for memory efficiency
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        # Load Text-to-Image Model (Tiny-SD - 55% smaller, much less memory)
        print("Loading Tiny-SD model (memory optimized)...")
        self.sd_pipe = self.StableDiffusionPipeline.from_pretrained(
            "segmind/tiny-sd",
            torch_dtype=self.dtype,
            use_safetensors=True,
        )
        self.sd_pipe.to(self.device)

        # Enable memory efficient attention if available (safety check)
        if hasattr(self.sd_pipe, "enable_xformers_memory_efficient_attention"):
            try:
                self.sd_pipe.enable_xformers_memory_efficient_attention()
                print("XFormers memory efficient attention enabled for Tiny-SD")
            except Exception as e:
                print(f"Could not enable XFormers: {e}")

        print("Tiny-SD model loaded successfully.")

        # Load Image-to-Video Model (SVD)
        print("Loading Stable Video Diffusion model...")
        self.svd_pipe = self.StableVideoDiffusionPipeline.from_pretrained(
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
            # Step 1: Generate keyframe with Tiny-SD (memory optimized)
            print(f"[{job_id}] Generating keyframe image...")
            image = self.sd_pipe(
                prompt=prompt,
                num_inference_steps=20,  # Reduced for faster generation
                height=512,              # Standard SD resolution (not XL)
                width=512,               # Standard SD resolution (not XL)
                guidance_scale=7.5,
            ).images[0]
            print(f"[{job_id}] Keyframe generated.")

            # Step 2: Animate with SVD (reduced settings for memory)
            print(f"[{job_id}] Animating image with SVD...")
            video_frames = self.svd_pipe(
                image,
                num_frames=14,           # Reduced from 25 to save memory
                decode_chunk_size=4,     # Reduced from 8 to save memory  
            ).frames[0]
            print(f"[{job_id}] Animation complete.")

            # Step 3: Save to shared volume using diffusers' built-in export
            output_path = self.video_storage_path / f"{job_id}.mp4"
            print(f"[{job_id}] Exporting video to {output_path}...")
            self.export_to_video(video_frames, str(output_path), fps=7)
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
            "cuda_available": self.torch.cuda.is_available(),
        }

        if self.torch.cuda.is_available():
            info.update(
                {
                    "gpu_name": self.torch.cuda.get_device_name(0),
                    "gpu_memory_total": self.torch.cuda.get_device_properties(0).total_memory,
                    "gpu_memory_allocated": self.torch.cuda.memory_allocated(0),
                }
            )

        return info
