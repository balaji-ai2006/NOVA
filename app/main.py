"""
NOVA FastAPI Application — Main Entry Point
-------------------------------------------
Mounts all API routers and serves the static UI.

Start with:  python main.py
             or
             uvicorn app.main:app --host 127.0.0.1 --port 7860 --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.config import APP_NAME, APP_VERSION, APP_TAGLINE, UI_DIR
from app.core.logger import get_logger
from app.api import chat, voice, vision, memory, tools, status

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("  %s v%s  — %s", APP_NAME, APP_VERSION, APP_TAGLINE)
    logger.info("=" * 60)
    logger.info("API docs available at: http://127.0.0.1:7860/api/docs")
    yield
    # Shutdown
    logger.info("NOVA shutting down. Goodbye!")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_TAGLINE,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(chat.router,   prefix="/api/chat",   tags=["Chat"])
app.include_router(voice.router,  prefix="/api/voice",  tags=["Voice"])
app.include_router(vision.router, prefix="/api/vision", tags=["Vision"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
app.include_router(tools.router,  prefix="/api/tools",  tags=["Tools"])
app.include_router(status.router, prefix="/api/status", tags=["Status"])

# ---------------------------------------------------------------------------
# Static files (UI)
# ---------------------------------------------------------------------------
STATIC_DIR = UI_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve the main UI HTML page."""
    return FileResponse(str(UI_DIR / "templates" / "index.html"))

