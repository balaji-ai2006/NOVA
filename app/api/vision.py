"""
NOVA Vision API
---------------
POST /api/vision/capture        — capture a webcam frame, return base64 JPEG
POST /api/vision/analyse        — capture + analyse with vision LLM
POST /api/vision/analyse-upload — analyse an uploaded image
GET  /api/vision/status         — camera + vision model availability
"""

import base64
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional

from app.vision.camera import get_camera, get_vision
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AnalyseRequest(BaseModel):
    question: str = "What do you see in this image? Describe it in detail."


@router.post("/capture")
async def capture_frame():
    """
    Capture a single frame from the webcam and return it as base64 JPEG.
    No image is saved to disk.
    """
    cam = get_camera()
    if not cam.is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Camera not available. Make sure:\n"
                "1. opencv-python is installed: pip install opencv-python\n"
                "2. No other app is using the webcam."
            ),
        )
    try:
        b64 = cam.capture_base64()
        return {"image_base64": b64, "format": "jpeg"}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyse")
async def analyse_frame(req: AnalyseRequest):
    """
    Capture a webcam frame and ask the vision LLM a question about it.
    Falls back to basic OpenCV analysis if moondream is not installed.
    """
    cam = get_camera()
    vis = get_vision()

    if not cam.is_available():
        raise HTTPException(status_code=503, detail="Camera not available.")

    try:
        jpeg_bytes = cam.capture_frame()
        b64        = base64.b64encode(jpeg_bytes).decode("utf-8")
        answer     = vis.analyse(jpeg_bytes, question=req.question)
        return {
            "image_base64": b64,
            "answer":       answer,
            "model":        vis.model if vis.is_model_available() else "basic-analysis",
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyse-upload")
async def analyse_uploaded_image(
    question: str = "What do you see in this image?",
    file: UploadFile = File(...),
):
    """Analyse a user-uploaded image file."""
    vis          = get_vision()
    jpeg_bytes   = await file.read()
    answer       = vis.analyse(jpeg_bytes, question=question)
    b64          = base64.b64encode(jpeg_bytes).decode("utf-8")
    return {
        "image_base64": b64,
        "answer":       answer,
        "model":        vis.model if vis.is_model_available() else "basic-analysis",
    }


@router.get("/status")
async def vision_status():
    """Return camera and vision model availability."""
    cam = get_camera()
    vis = get_vision()
    return {
        "camera_available":  cam.is_available(),
        "vision_model":      vis.model,
        "vision_llm_ready":  vis.is_model_available(),
        "pull_hint": (
            f"Run: ollama pull {vis.model}" if not vis.is_model_available() else None
        ),
    }
