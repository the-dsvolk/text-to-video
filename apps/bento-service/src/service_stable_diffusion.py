"""Stable Diffusion based BentoML service for text-to-video generation."""

import os
import bentoml
from pathlib import Path

# Configuration - The path where the PersistentVolume is mounted
VIDEO_STORAGE_PATH = os.getenv("SHARED_VOLUME_PATH", "/data/videos")


@bentoml.service(
    resources={"gpu": 1, "gpu_type": "nvidia-l4", "memory": "16Gi"},
    traffic={"timeout": 900},  # 15-minute timeout for long generation jobs
)
class TextToVideoGeneratorStableDiffusion:
    """Memory-optimized Text-to-Video generation service using Tiny-SD + SVD pipeline."""

    def __init__(self) -> None:
        """Load all models into memory when the service first starts."""
        # Import dependencies at runtime
        import torch
        from diffusers import StableDiffusionPipeline, StableVideoDiffusionPipeline
        import numpy as np

        # Try to import imageio
        try:
            import imageio
            self.imageio = imageio
            self.has_imageio = True
            print("✅ Using imageio for video export")
        except ImportError as e:
            print(f"⚠️ imageio not available ({e}), will use ffmpeg fallback")
            self.imageio = None
            self.has_imageio = False

        # Store imports as instance variables for use in other methods
        self.torch = torch
        self.StableDiffusionPipeline = StableDiffusionPipeline
        self.StableVideoDiffusionPipeline = StableVideoDiffusionPipeline
        self.np = np

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

    def _export_video_with_imageio(self, video_frames, output_path, job_id):
        """Export video using imageio - preferred method."""
        try:
            print(f"[{job_id}] Using imageio for video export...")

            # Convert PIL images to numpy arrays if needed
            if hasattr(video_frames[0], 'convert'):  # PIL Image
                video_frames = [self.np.array(frame.convert('RGB')) for frame in video_frames]

            # Export using imageio
            with self.imageio.get_writer(str(output_path), fps=7) as writer:
                for frame in video_frames:
                    writer.append_data(frame)

            print(f"[{job_id}] Video exported successfully with imageio")
            return True

        except Exception as e:
            print(f"[{job_id}] imageio export failed: {e}")
            return False

    def _export_video_with_ffmpeg(self, video_frames, output_path, job_id):
        """Export video using system ffmpeg - fallback method."""
        import subprocess
        import shutil

        # Create temp directory for frames
        temp_dir = self.video_storage_path / f"temp_{job_id}"
        temp_dir.mkdir(exist_ok=True)

        try:
            print(f"[{job_id}] Using ffmpeg fallback for video export...")
            print(f"[{job_id}] Saving {len(video_frames)} frames to temp directory...")

            # Save frames as PNG files
            for i, frame in enumerate(video_frames):
                frame_path = temp_dir / f"frame_{i:04d}.png"
                if hasattr(frame, 'save'):  # PIL Image
                    frame.save(frame_path)
                else:  # numpy array
                    from PIL import Image
                    Image.fromarray(frame).save(frame_path)

            print(f"[{job_id}] Creating video with ffmpeg...")

            # Use system ffmpeg to create video
            cmd = [
                "ffmpeg", "-y", "-r", "7",
                "-i", str(temp_dir / "frame_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "23",  # Good quality
                str(output_path)
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"[{job_id}] Video created successfully with ffmpeg")
            return True

        except subprocess.CalledProcessError as e:
            print(f"[{job_id}] FFmpeg error: {e}")
            print(f"[{job_id}] FFmpeg stderr: {e.stderr}")
            raise RuntimeError(f"Video export failed: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found. Please install ffmpeg.")
        finally:
            # Clean up temp files
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                print(f"[{job_id}] Cleaned up temporary files")

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

            # Step 3: Save to shared volume
            output_path = self.video_storage_path / f"{job_id}.mp4"
            print(f"[{job_id}] Exporting video to {output_path}...")

            # Try imageio first, fallback to ffmpeg
            success = False
            if self.has_imageio:
                success = self._export_video_with_imageio(video_frames, output_path, job_id)

            if not success:
                success = self._export_video_with_ffmpeg(video_frames, output_path, job_id)

            if not success:
                raise RuntimeError("Both imageio and ffmpeg export methods failed")

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
            "service": "text-to-video-generator-stable-diffusion",
            "device": self.device,
            "cuda_available": self.torch.cuda.is_available(),
            "video_export_method": "imageio" if self.has_imageio else "ffmpeg",
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
