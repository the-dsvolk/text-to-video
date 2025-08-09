"""Mochi-1 based BentoML service for high-quality text-to-video generation."""

import os
import bentoml
from pathlib import Path

# Configuration - The path where the PersistentVolume is mounted
VIDEO_STORAGE_PATH = os.getenv("SHARED_VOLUME_PATH", "/data/videos")


@bentoml.service(
    resources={"gpu": 2, "gpu_type": "h100-80gb", "memory": "32Gi"},  # 2 H100 80GB GPUs per replica
    traffic={"timeout": 1200},  # 20-minute timeout for Mochi generation
)
class TextToVideoGeneratorMochi:
    """High-quality Text-to-Video generation service using Mochi-1 (bfloat16 variant for memory efficiency)."""

    def __init__(self) -> None:
        """Load Mochi-1 model into memory when the service first starts."""
        # Import dependencies at runtime
        import torch
        from diffusers import MochiPipeline
        from diffusers.utils import export_to_video

        # Store imports as instance variables for use in other methods
        self.torch = torch
        self.export_to_video = export_to_video

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.video_storage_path = Path(VIDEO_STORAGE_PATH)
        self.video_storage_path.mkdir(parents=True, exist_ok=True)

        print("Loading Mochi-1 model... This may take several minutes.")
        print("Using bfloat16 variant optimized for H100 80GB (abundant VRAM available)")

        # Load Mochi-1 Pipeline with bfloat16 - could use full precision on H100
        self.pipe = MochiPipeline.from_pretrained(
            "genmo/mochi-1-preview",
            variant="bf16",
            torch_dtype=torch.bfloat16
        )

        # Enable memory savings
        print("Enabling CPU offload and VAE tiling for memory optimization...")
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_vae_tiling()

        print("Mochi-1 model loaded successfully with memory optimizations enabled.")
        print("Ready for high-quality video generation!")

    def _export_video_mochi(self, frames, output_path, job_id, fps=30):
        """Export video using Mochi's built-in export functionality."""
        try:
            print(f"[{job_id}] Exporting video with Mochi built-in export (fps={fps})...")

            # Use diffusers export_to_video utility
            self.export_to_video(frames, str(output_path), fps=fps)

            print(f"[{job_id}] Video exported successfully to {output_path}")
            return True

        except Exception as e:
            print(f"[{job_id}] Mochi video export failed: {e}")
            return False

    @bentoml.api
    def generate(self, prompt: str, job_id: str, num_frames: int = 84) -> dict:
        """Generate video from text prompt using Mochi-1.

        Args:
            prompt: Text description for video generation
            job_id: Unique identifier for this generation job
            num_frames: Number of frames to generate (default: 84 for ~2.8s at 30fps)

        Returns:
            Dict with generation status and output path
        """
        print(f"[{job_id}] Starting Mochi-1 generation for prompt: '{prompt}'")
        print(f"[{job_id}] Generating {num_frames} frames (~{num_frames/30:.1f}s at 30fps)")

        try:
            # Generate video with Mochi-1 using autocast for memory efficiency
            print(f"[{job_id}] Running Mochi-1 inference...")
            with self.torch.autocast("cuda", self.torch.bfloat16, cache_enabled=False):
                frames = self.pipe(prompt, num_frames=num_frames).frames[0]

            print(f"[{job_id}] Generated {len(frames)} frames successfully.")

            # Export video to shared volume
            output_path = self.video_storage_path / f"{job_id}.mp4"
            print(f"[{job_id}] Exporting video to {output_path}...")

            # Export using Mochi's built-in export functionality
            success = self._export_video_mochi(frames, output_path, job_id, fps=30)

            if not success:
                raise RuntimeError("Mochi video export failed")

            print(f"[{job_id}] Video saved successfully.")

            return {
                "status": "complete",
                "success": True,
                "job_id": job_id,
                "output_path": str(output_path),
                "num_frames": len(frames),
                "duration_seconds": len(frames) / 30,
                "fps": 30,
                "message": "High-quality video generated successfully with Mochi-1",
            }

        except Exception as e:
            print(f"[{job_id}] Error during Mochi-1 generation: {e}")
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
            "service": "text-to-video-generator-mochi-1",
            "model": "genmo/mochi-1-preview",
            "variant": "bf16",
            "device": self.device,
            "cuda_available": self.torch.cuda.is_available(),
            "video_export_method": "mochi_built_in",
            "memory_optimizations": {
                "cpu_offload": True,
                "vae_tiling": True,
                "autocast": True
            }
        }

        if self.torch.cuda.is_available():
            info.update(
                {
                    "gpu_name": self.torch.cuda.get_device_name(0),
                    "gpu_memory_total": self.torch.cuda.get_device_properties(0).total_memory,
                    "gpu_memory_allocated": self.torch.cuda.memory_allocated(0),
                    "recommended_vram": "22GB minimum (80GB available on H100)",
                }
            )

        return info
