"""Flux Dev GGUF workflow template for simple text-to-image generation."""

from __future__ import annotations

import random
from typing import Any


def build_workflow(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg: float = 1.0,
    seed: int | None = None,
) -> dict[str, Any]:
    """Build a Flux Dev GGUF workflow from simple parameters.

    Uses: UnetLoaderGGUF + DualCLIPLoaderGGUF + KSampler + VAEDecode + SaveImage
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    return {
        # Unet loader (GGUF)
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": "flux1-dev-Q4_K_S.gguf",
            },
        },
        # Dual CLIP loader (GGUF) - Flux uses two text encoders
        "2": {
            "class_type": "DualCLIPLoaderGGUF",
            "inputs": {
                "clip_name1": "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                "clip_name2": "clip_l.safetensors",
                "type": "flux",
            },
        },
        # VAE loader
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ae.safetensors",
            },
        },
        # Positive prompt
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["2", 0],
            },
        },
        # Negative prompt
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["2", 0],
            },
        },
        # Empty latent image
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        # KSampler
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        # VAE Decode
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0],
            },
        },
        # Save image
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "api_output",
            },
        },
    }
