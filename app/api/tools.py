"""
NOVA Computer Tools API
------------------------
POST /api/tools/open-app    — open an allowed application
POST /api/tools/read-file   — read a user-specified text file
GET  /api/tools/system-info — system resource usage
GET  /api/tools/allowed-apps — list allowed applications

All actions require the user to have explicitly triggered the request;
no action is performed automatically from model output.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tools.computer import open_application, read_file, get_system_info
from app.core.config import ALLOWED_APPS
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class OpenAppRequest(BaseModel):
    app_name: str


class ReadFileRequest(BaseModel):
    file_path: str
    max_chars: int = 4000


@router.post("/open-app")
async def open_app(req: OpenAppRequest):
    """Open a pre-approved application by name."""
    try:
        result = open_application(req.app_name)
        return {"status": "ok", "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/read-file")
async def read_text_file(req: ReadFileRequest):
    """Read a text file the user has specified by path."""
    try:
        content = read_file(req.file_path, req.max_chars)
        return {"status": "ok", "content": content, "path": req.file_path}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/system-info")
async def system_info():
    """Return safe, non-sensitive system information."""
    return get_system_info()


@router.get("/allowed-apps")
async def allowed_apps():
    """List applications NOVA is allowed to open."""
    return {"allowed": list(ALLOWED_APPS.keys())}
