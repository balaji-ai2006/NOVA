"""
NOVA Hardware Compatibility & Model Recommendation Engine
-----------------------------------------------------------
Detects hardware specifications (CPU, RAM, GPU/VRAM, OS) on Windows systems
and provides tailored local AI model recommendations and safe feature thresholds.
Keeps hardware-specific logic isolated for maintainability and future portability.
"""

import os
import shutil
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


@dataclass
class HardwareProfile:
    os_name: str
    os_version: str
    architecture: str
    cpu_cores_logical: int
    cpu_cores_physical: int
    ram_total_gb: float
    ram_available_gb: float
    gpu_name: Optional[str] = None
    vram_mb: Optional[int] = None
    hardware_tier: str = "balanced"  # "entry", "balanced", "high_performance"
    recommended_llm: str = "llama3.2:3b"
    alternate_llms: Optional[List[str]] = None
    vision_supported: bool = False
    cuda_available: bool = False


def detect_nvidia_gpu() -> tuple[Optional[str], Optional[int]]:
    """Detect NVIDIA GPU name and VRAM in MB via nvidia-smi if available."""
    if not shutil.which("nvidia-smi"):
        return None, None
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split("\n")[0].split(",")
            if len(parts) >= 2:
                name = parts[0].strip()
                vram = int(float(parts[1].strip()))
                return name, vram
    except Exception:
        pass
    return None, None


def get_hardware_profile() -> HardwareProfile:
    """Analyze current system specs and compute model recommendations."""
    os_name = platform.system()
    os_ver = platform.version()
    arch = platform.machine()

    cpu_logical = os.cpu_count() or 4
    cpu_physical = cpu_logical
    ram_total = 8.0
    ram_avail = 4.0

    if psutil:
        try:
            cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
            mem = psutil.virtual_memory()
            ram_total = round(mem.total / (1024**3), 1)
            ram_avail = round(mem.available / (1024**3), 1)
        except Exception:
            pass

    gpu_name, vram_mb = detect_nvidia_gpu()
    cuda_avail = bool(gpu_name and vram_mb)

    # Determine Tier & Recommendations
    # High Performance: >= 16 GB RAM and (>= 8 GB VRAM or strong CPU)
    if (vram_mb and vram_mb >= 7500) or (ram_total >= 24.0):
        tier = "high_performance"
        recommended_llm = "llama3.1:8b"
        alternates = ["mistral:7b", "llama3.2:3b", "qwen2.5:7b"]
        vision_supported = True
    # Balanced / Capable: 8-16 GB RAM or 4-6 GB VRAM (e.g. RTX 3050 6GB)
    elif (vram_mb and vram_mb >= 3500) or (ram_total >= 11.5):
        tier = "balanced"
        recommended_llm = "llama3.2:3b"
        alternates = ["phi3:mini", "llama3.2:1b", "qwen2.5:3b"]
        vision_supported = bool(vram_mb and vram_mb >= 4000) or (ram_total >= 16.0)
    # Entry Level: < 8 GB RAM and no dedicated high VRAM GPU
    else:
        tier = "entry"
        recommended_llm = "llama3.2:1b"
        alternates = ["qwen2.5:1.5b", "phi3:mini"]
        vision_supported = False

    return HardwareProfile(
        os_name=os_name,
        os_version=os_ver,
        architecture=arch,
        cpu_cores_logical=cpu_logical,
        cpu_cores_physical=cpu_physical,
        ram_total_gb=ram_total,
        ram_available_gb=ram_avail,
        gpu_name=gpu_name,
        vram_mb=vram_mb,
        hardware_tier=tier,
        recommended_llm=recommended_llm,
        alternate_llms=alternates,
        vision_supported=vision_supported,
        cuda_available=cuda_avail,
    )
