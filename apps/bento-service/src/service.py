"""BentoML service for Text-to-Video generation using Mochi-1 model."""

import os
import bentoml
from pathlib import Path
from typing import Dict, Any

# Configuration - The path where the PersistentVolume is mounted
VIDEO_STORAGE_PATH = os.getenv("SHARED_VOLUME_PATH", "/data/videos")


@bentoml.service(
    resources={"gpu": 2, "gpu_type": "h100-80gb", "memory": "32Gi"},
    traffic={"timeout": 1200},  # 20-minute timeout for Mochi generation
)
class TextToVideoGenerator:
    """Text-to-Video generation service using Mochi-1 model."""

    def __init__(self) -> None:
        """Load Mochi-1 model when the service starts."""
        # Import Mochi dependencies at runtime
        from genmo.mochi_preview.pipelines import (
            DecoderModelFactory,
            DitModelFactory,
            MochiSingleGPUPipeline,
            T5ModelFactory,
            linear_quadratic_schedule,
        )
        from genmo.lib.utils import save_video

        # Store imports for later use
        self.linear_quadratic_schedule = linear_quadratic_schedule
        self.save_video = save_video

        self.video_storage_path = Path(VIDEO_STORAGE_PATH)
        self.video_storage_path.mkdir(parents=True, exist_ok=True)

        # Model directory - assuming weights are in /workspace/weights/
        self.mochi_dir = Path("/workspace/weights")

        print("Loading Mochi-1 model using official API...")
        self.pipeline = MochiSingleGPUPipeline(
            text_encoder_factory=T5ModelFactory(),
            dit_factory=DitModelFactory(
                model_path=str(self.mochi_dir / "dit.safetensors"),
                model_dtype="bf16"
            ),
            decoder_factory=DecoderModelFactory(
                model_path=str(self.mochi_dir / "vae.safetensors"),
                model_stats_path=str(self.mochi_dir / "vae_stats.json"),
            ),
            cpu_offload=True,
            decode_type="tiled_full",
        )
        print("Mochi-1 model loaded successfully!")

    @bentoml.api
    def generate(self, prompt: str, job_id: str, num_frames: int = 31) -> Dict[str, Any]:
        """Generate video from text prompt using Mochi-1.

        Args:
            prompt: Text description for video generation
            job_id: Unique identifier for this generation job
            num_frames: Number of frames to generate (default 31)

        Returns:
            Dict with generation status and output path
        """
        print(f"[{job_id}] Starting Mochi-1 generation for prompt: '{prompt}'")

        try:
            # Generate video using Mochi-1 pipeline
            print(f"[{job_id}] Generating {num_frames}-frame video...")

            video = self.pipeline(
                height=480,
                width=848,
                num_frames=num_frames,
                num_inference_steps=64,
                sigma_schedule=self.linear_quadratic_schedule(64, 0.025),
                cfg_schedule=[4.5] * 64,
                batch_cfg=False,
                prompt=prompt,
                negative_prompt="",
                seed=12345,  # Fixed seed for reproducibility
            )

            print(f"[{job_id}] Video generation complete, saving...")

            # Save video to shared volume
            output_path = self.video_storage_path / f"{job_id}.mp4"
            self.save_video(video[0], str(output_path))

            print(f"[{job_id}] Video saved successfully to {output_path}")

            return {
                "status": "complete",
                "success": True,
                "job_id": job_id,
                "output_path": str(output_path),
                "message": f"Video with {num_frames} frames generated successfully using Mochi-1",
                "num_frames": num_frames,
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
    def health(self) -> Dict[str, Any]:
        """Health check endpoint for Mochi-1 service."""
        import torch

        info = {
            "status": "healthy",
            "service": "text-to-video-generator-mochi",
            "model": "Mochi-1",
            "model_directory": str(self.mochi_dir),
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
