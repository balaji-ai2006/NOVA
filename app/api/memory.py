"""
NOVA Memory API
---------------
GET    /api/memory/           — list all memories
POST   /api/memory/save       — save a new memory
DELETE /api/memory/{id}       — delete one memory
DELETE /api/memory/           — clear all memories
GET    /api/memory/context    — return memories formatted as LLM context
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.memory.store import MemoryStore
from app.core.logger import get_logger

router  = APIRouter()
logger  = get_logger(__name__)
_memory = MemoryStore()


class SaveMemoryRequest(BaseModel):
    content: str
    tags:    str = ""


@router.get("/")
async def list_memories():
    """Return all stored long-term memories."""
    return {"memories": _memory.list_all()}


@router.post("/save")
async def save_memory(req: SaveMemoryRequest):
    """Save a new memory (user-approved text only)."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Memory content cannot be empty.")
    new_id = _memory.save(req.content, req.tags)
    return {"status": "saved", "id": new_id, "content": req.content}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int):
    """Delete a single memory by its id."""
    deleted = _memory.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory id={memory_id} not found.")
    return {"status": "deleted", "id": memory_id}


@router.delete("/")
async def clear_all_memories():
    """Delete ALL memories. Irreversible."""
    count = _memory.clear_all()
    return {"status": "cleared", "deleted_count": count}


@router.get("/context")
async def memory_context():
    """Return memories as a formatted context string for LLM injection."""
    return {"context": _memory.as_context_string()}
