"""Hybrid Mochi-1 BentoML service - official API style with HuggingFace integration."""

import os
import uuid
from pathlib import Path
from typing import Dict, Any
import torch
import bentoml
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
VIDEO_STORAGE_PATH = os.getenv("SHARED_VOLUME_PATH", "/data/videos")

@bentoml.service(
    resources={"gpu": 1, "gpu_type": "h100-80gb", "memory": "32Gi"},
    traffic={"timeout": 1200},  # 20-minute timeout
)
class MochiVideoGeneratorHybrid:
    """Hybrid Mochi-1 service using official API patterns with HuggingFace models."""

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Video storage setup
        self.video_storage_path = Path(VIDEO_STORAGE_PATH)
        self.video_storage_path.mkdir(parents=True, exist_ok=True)

        logger.info("Loading Mochi-1 model (hybrid approach)...")

        try:
            # Try to use official Mochi API if available
            try:
                from genmo.mochi_preview.pipelines import (
                    DecoderModelFactory,
                    DitModelFactory,
                    MochiSingleGPUPipeline,
                    T5ModelFactory,
                    linear_quadratic_schedule,
                )

                # Check if weights exist locally (official repo style)
                weights_path = Path("weights")
                if weights_path.exists() and (weights_path / "dit.safetensors").exists():
                    logger.info("Using official Mochi API with local weights")
                    self.pipeline_type = "official"
                    self.linear_quadratic_schedule = linear_quadratic_schedule

                    self.pipeline = MochiSingleGPUPipeline(
                        text_encoder_factory=T5ModelFactory(),
                        dit_factory=DitModelFactory(
                            model_path="weights/dit.safetensors",
                            model_dtype="bf16"
                        ),
                        decoder_factory=DecoderModelFactory(
                            model_path="weights/decoder.safetensors",
                        ),
                        cpu_offload=True,
                        decode_type="tiled_spatial",
                    )
                else:
                    raise FileNotFoundError("Local weights not found")

            except (ImportError, FileNotFoundError):
                # Fallback to diffusers (current approach)
                logger.info("Falling back to diffusers MochiPipeline")
                from diffusers import MochiPipeline
                from diffusers.utils import export_to_video
                from transformers import AutoTokenizer

                self.pipeline_type = "diffusers"
                self.export_to_video = export_to_video

                # Pre-load tokenizer to avoid lazy loading issues
                logger.info("Loading T5 tokenizer...")
                tokenizer = AutoTokenizer.from_pretrained(
                    "google/t5-v1_1-xxl",
                    trust_remote_code=True
                )

                # Load Mochi-1 Pipeline
                logger.info("Loading Mochi-1 pipeline from HuggingFace...")
                self.pipeline = MochiPipeline.from_pretrained(
                    "genmo/mochi-1-preview",
                    variant="bf16",
                    torch_dtype=torch.bfloat16,
                    trust_remote_code=True,
                    use_safetensors=True
                )

                # Enable memory savings
                logger.info("Enabling memory optimizations...")
                self.pipeline.enable_model_cpu_offload()
                self.pipeline.enable_vae_tiling()

            logger.info(f"Mochi-1 model loaded successfully using {self.pipeline_type} approach!")

        except Exception as e:
            logger.error(f"Failed to load Mochi-1 model: {e}")
            raise

    @bentoml.api
    def generate(self, prompt: str, job_id: str = None, num_frames: int = 31) -> Dict[str, Any]:
        """Generate video using the best available Mochi API.

        Args:
            prompt: Text description for video generation
            job_id: Optional job identifier
            num_frames: Number of frames (31 for official API, 84 for diffusers)

        Returns:
            Dict with generation results
        """
        if not job_id:
            job_id = uuid.uuid4().hex[:8]

        try:
            logger.info(f"[{job_id}] Generating video with {self.pipeline_type}: {prompt}")

            if self.pipeline_type == "official":
                # Use official Mochi API
                video = self.pipeline(
                    height=480,
                    width=848,
                    num_frames=num_frames,
                    num_inference_steps=64,
                    sigma_schedule=self.linear_quadratic_schedule(64, 0.025),
                    cfg_schedule=[6.0] * 64,
                    batch_cfg=False,
                    prompt=prompt,
                    negative_prompt="",
                    seed=12345,
                )

                # Save video (implementation depends on official API return format)
                video_filename = f"{job_id}_{uuid.uuid4().hex[:8]}.mp4"
                video_path = self.video_storage_path / video_filename

                # TODO: Implement video saving for official API
                logger.info(f"[{job_id}] Video generated with official API")

            else:
                # Use diffusers approach
                with torch.autocast("cuda", torch.bfloat16, cache_enabled=False):
                    frames = self.pipeline(prompt, num_frames=num_frames).frames[0]

                # Save video using diffusers export
                video_filename = f"{job_id}_{uuid.uuid4().hex[:8]}.mp4"
                video_path = self.video_storage_path / video_filename

                self.export_to_video(frames, str(video_path), fps=30)
                logger.info(f"[{job_id}] Video saved: {video_path}")

            return {
                "status": "success",
                "job_id": job_id,
                "video_filename": video_filename,
                "video_path": str(video_path),
                "prompt": prompt,
                "num_frames": num_frames,
                "model": f"mochi-1-{self.pipeline_type}",
                "api_version": "hybrid"
            }

        except Exception as e:
            logger.error(f"[{job_id}] Video generation failed: {e}")
            return {
                "status": "error",
                "job_id": job_id,
                "error": str(e),
                "model": f"mochi-1-{self.pipeline_type}"
            }

    @bentoml.api
    def health(self) -> Dict[str, Any]:
        """Health check endpoint with system information."""
        try:
            info = {
                "status": "healthy",
                "service": "mochi-video-generator-hybrid",
                "pipeline_type": getattr(self, 'pipeline_type', 'unknown'),
                "device": self.device,
                "cuda_available": torch.cuda.is_available(),
                "api_source": "hybrid (official + diffusers)"
            }

            if torch.cuda.is_available():
                info.update({
                    "gpu_name": torch.cuda.get_device_name(0),
                    "gpu_memory_total": torch.cuda.get_device_properties(0).total_memory,
                    "gpu_memory_allocated": torch.cuda.memory_allocated(0),
                })

            return info

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "service": "mochi-video-generator-hybrid"
            }
