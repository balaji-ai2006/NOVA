"""
NOVA Vision — Webcam Capture + Local Visual Understanding
----------------------------------------------------------
Two modes:
  1. Capture-only   : Grabs a frame from the webcam → returns base64 JPEG.
  2. Vision LLM     : Sends image + question to Ollama's moondream model
                      for real image understanding (requires `ollama pull moondream`).

Privacy:
  - Camera is ONLY activated when the user explicitly clicks the camera button.
  - Frames are NEVER saved to disk automatically.
  - The status bar shows a red indicator whenever the camera is active.

Fallback behaviour:
  - If moondream is not installed, NOVA describes the frame using basic
    OpenCV analysis (brightness, colour histogram) and clearly labels the
    response as a "basic analysis" — it never pretends to have understood the image.

Raspberry Pi:
  Replace CAMERA_INDEX=0 with the Pi Camera index (usually 0).
  libcamera-based Picam2 would require a different capture path (future work).
"""

import base64
import io
import json
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import (
    VISION_MODEL,
    VISION_ENABLED,
    CAMERA_INDEX,
    OLLAMA_BASE_URL,
    LLM_TIMEOUT,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Camera capture
# ---------------------------------------------------------------------------

class CameraCapture:
    """
    Opens the webcam, captures a single frame, releases immediately.

    Why release immediately?
      Privacy — we only hold the camera while the user has actively requested capture.
    """

    def __init__(self, index: int = CAMERA_INDEX):
        self.index = index

    def is_available(self) -> bool:
        """Return True if opencv-python is installed and the camera can be opened."""
        try:
            import cv2
            cap = cv2.VideoCapture(self.index)
            ok = cap.isOpened()
            cap.release()
            return ok
        except ImportError:
            return False
        except Exception:
            return False

    def capture_frame(self) -> bytes:
        """
        Capture one JPEG frame from the webcam.

        Returns
        -------
        JPEG bytes of the captured image.

        Raises
        ------
        RuntimeError if OpenCV is missing or the camera cannot be opened.
        """
        try:
            import cv2
        except ImportError:
            raise RuntimeError(
                "opencv-python is not installed.\nRun:  pip install opencv-python"
            )

        cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            raise RuntimeError(
                f"Camera index {self.index} could not be opened.\n"
                "Check that no other app is using the webcam."
            )
        try:
            # Discard a few frames to let auto-exposure settle
            for _ in range(3):
                cap.read()
            ret, frame = cap.read()
            if not ret or frame is None:
                raise RuntimeError("Failed to read frame from camera.")
            # Encode as JPEG in memory
            success, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not success:
                raise RuntimeError("Failed to encode frame as JPEG.")
            return bytes(buf)
        finally:
            cap.release()

    def capture_base64(self) -> str:
        """Capture a frame and return it as a base64 string (for JSON transport)."""
        return base64.b64encode(self.capture_frame()).decode("utf-8")


# ---------------------------------------------------------------------------
# Basic analysis fallback (no vision LLM needed)
# ---------------------------------------------------------------------------

def basic_image_analysis(jpeg_bytes: bytes) -> str:
    """
    Produce a very simple description using OpenCV pixel statistics.
    This is clearly labelled as a basic analysis, NOT real understanding.

    Used when the moondream vision model is not installed.
    """
    try:
        import cv2
        import numpy as np

        data  = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if frame is None:
            return "[Basic analysis] Could not decode the image."

        h, w = frame.shape[:2]
        brightness = float(np.mean(frame))
        hsv   = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hue   = float(np.mean(hsv[:, :, 0]))

        br_label = "dark" if brightness < 80 else ("bright" if brightness > 170 else "moderate")
        hue_label = (
            "red/orange" if hue < 20 or hue > 160
            else "yellow-green" if hue < 60
            else "green"       if hue < 90
            else "blue/cyan"   if hue < 130
            else "purple/pink"
        )

        return (
            f"[Basic analysis — moondream model not installed]\n"
            f"Resolution: {w}×{h}px | Brightness: {br_label} ({brightness:.0f}/255) | "
            f"Dominant hue: {hue_label}.\n"
            f"For real image understanding, run: ollama pull {VISION_MODEL}"
        )
    except Exception as exc:
        return f"[Basic analysis failed: {exc}]"


# ---------------------------------------------------------------------------
# Vision LLM via Ollama
# ---------------------------------------------------------------------------

class VisionAnalyser:
    """
    Sends an image + question to Ollama's moondream model for local understanding.

    moondream2 is a ~1.8 GB vision-language model that runs well on the RTX 3050.
    Pull it once with:  ollama pull moondream
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = VISION_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model    = model

    def is_model_available(self) -> bool:
        """Check if the vision model is pulled in Ollama."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return any(m.startswith(self.model.split(":")[0]) for m in models)
        except Exception:
            return False

    def analyse(self, jpeg_bytes: bytes, question: str = "What do you see in this image?") -> str:
        """
        Ask the vision model about the image.

        Parameters
        ----------
        jpeg_bytes : Raw JPEG image bytes.
        question   : The question to ask about the image.

        Returns
        -------
        Model's text answer.
        """
        if not self.is_model_available():
            logger.warning("Vision model '%s' not found — using basic analysis.", self.model)
            return basic_image_analysis(jpeg_bytes)

        img_b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
        payload  = {
            "model":  self.model,
            "prompt": question,
            "images": [img_b64],
            "stream": False,
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=LLM_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except httpx.ConnectError:
            return "[Vision error] Ollama is not running. Start it with: ollama serve"
        except Exception as exc:
            logger.error("Vision LLM error: %s", exc)
            return f"[Vision error] {exc}"


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
_camera: Optional[CameraCapture]  = None
_vision: Optional[VisionAnalyser] = None


def get_camera() -> CameraCapture:
    global _camera
    if _camera is None:
        _camera = CameraCapture()
    return _camera


def get_vision() -> VisionAnalyser:
    global _vision
    if _vision is None:
        _vision = VisionAnalyser()
    return _vision
