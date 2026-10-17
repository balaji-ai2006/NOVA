"""
NOVA Memory — SQLite-backed long-term storage
---------------------------------------------
Two kinds of memory:
  1. Short-term: handled by OllamaClient's _history list (in RAM, lost on restart).
  2. Long-term : explicit entries the user approves, stored in SQLite.
                 These are loaded into context when NOVA starts.

Privacy note:
  - Camera frames and voice recordings are NEVER stored here.
  - Only text the user explicitly asks NOVA to remember is saved.
  - All data is local; nothing leaves the device.

Raspberry Pi note:
  SQLite works identically on Pi; just ensure the data/ directory is writable.
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Optional

from app.core.config import MEMORY_DB_PATH
from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content     TEXT    NOT NULL,
    tags        TEXT    DEFAULT '',       -- comma-separated tags
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
"""


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    Simple interface to NOVA's long-term memory database.

    Usage
    -----
    >>> store = MemoryStore()
    >>> store.save("My name is Balaji")
    1
    >>> store.list_all()
    [{'id': 1, 'content': 'My name is Balaji', ...}]
    >>> store.delete(1)
    """

    def __init__(self, db_path: Path = MEMORY_DB_PATH):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _get_conn(self) -> sqlite3.Connection:
        """Open a new connection (thread-safe; one connection per call)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row   # return dict-like rows
        return conn

    def _init_db(self) -> None:
        """Create the table if it doesn't exist yet."""
        with self._get_conn() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()
        logger.info("Memory DB ready at %s", self.db_path)

    @staticmethod
    def _now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ------------------------------------------------------------------ #
    # Sensitivity Filter & Safety
    # ------------------------------------------------------------------ #

    @staticmethod
    def is_sensitive(text: str) -> bool:
        """
        Check if text looks like sensitive credentials or personal secrets:
        passwords, secret keys, bearer tokens, private keys, credit cards.
        """
        import re
        patterns = [
            r"(?i)\b(password|passwd|secret|api[_-]?key|bearer\s+[a-z0-9_\-\.]{10,}|auth[_-]?token)\b\s*(?:is|[:=])\s*\S+",
            r"(?i)\b(my\s+password|my\s+secret|my\s+token)\b",
            r"-----BEGIN\s+(?:RSA|OPENSSH|EC|PRIVATE)?\s*KEY-----",
            r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b", # JWT
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b", # Credit cards
        ]
        return any(re.search(p, text) for p in patterns)

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def save(self, content: str, tags: str = "", allow_sensitive: bool = False) -> int:
        """
        Store a new memory and return its id.
        Rejects sensitive credentials unless explicitly allowed.
        """
        text = content.strip()
        if not text:
            raise ValueError("Memory content cannot be empty.")

        if not allow_sensitive and self.is_sensitive(text):
            logger.warning("Rejected saving memory containing sensitive information.")
            raise ValueError("Sensitive information (passwords, tokens, keys) cannot be saved in memory.")

        now = self._now()
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO memories (content, tags, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (text, tags.strip(), now, now),
            )
            conn.commit()
            new_id = cur.lastrowid
        logger.info("Memory saved (id=%s): %s", new_id, text[:60])
        return new_id  # type: ignore[return-value]

    def list_all(self) -> list[dict]:
        """Return all memories as a list of dicts (newest first)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, content, tags, created_at FROM memories ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str) -> list[dict]:
        """Simple case-insensitive substring search across content and tags."""
        pattern = f"%{query}%"
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, content, tags, created_at FROM memories "
                "WHERE LOWER(content) LIKE LOWER(?) OR LOWER(tags) LIKE LOWER(?) "
                "ORDER BY id DESC",
                (pattern, pattern),
            ).fetchall()
        return [dict(r) for r in rows]

    def retrieve_relevant(self, query: str, max_items: int = 5) -> list[dict]:
        """
        Retrieve memories most relevant to the given query.
        Splits query into keywords, scores matches, and falls back to newest memories.
        """
        if not query or not query.strip():
            return self.list_all()[:max_items]

        import re
        # Extract meaningful words (length >= 3, alphanumeric)
        words = [w.lower() for w in re.findall(r"\b[A-Za-z0-9_\u0900-\u097F]{3,}\b", query)]
        # Filter common stopwords
        stop_words = {
            "what", "where", "when", "which", "who", "whom", "this", "that", "these",
            "those", "have", "with", "from", "about", "your", "tell", "please", "help",
            "kya", "kaise", "kaha", "kiti", "ahe", "hota", "hoti",
        }
        keywords = [w for w in words if w not in stop_words]

        all_memories = self.list_all()
        if not keywords or not all_memories:
            return all_memories[:max_items]

        scored: list[tuple[int, dict]] = []
        for mem in all_memories:
            target = f"{mem['content']} {mem['tags']}".lower()
            score = sum(1 for kw in keywords if kw in target)
            if score > 0:
                scored.append((score, mem))

        # Sort by relevance score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        relevant = [m for _, m in scored[:max_items]]

        # If not enough keyword matches, supplement with recent preferences
        if len(relevant) < max_items:
            existing_ids = {m["id"] for m in relevant}
            for m in all_memories:
                if m["id"] not in existing_ids:
                    relevant.append(m)
                    if len(relevant) >= max_items:
                        break

        return relevant

    def delete(self, memory_id: int) -> bool:
        """Delete a memory by id. Returns True if a row was deleted."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
        deleted = cur.rowcount > 0
        if deleted:
            logger.info("Memory deleted (id=%s)", memory_id)
        return deleted

    def clear_all(self) -> int:
        """Delete every memory. Returns count of deleted rows."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM memories")
            conn.commit()
        logger.warning("All memories cleared (%d rows)", cur.rowcount)
        return cur.rowcount

    def as_context_string(self, query: Optional[str] = None, max_items: int = 5) -> str:
        """
        Produce a formatted string of relevant memories suitable for
        injecting into the LLM context window.
        """
        if query:
            items = self.retrieve_relevant(query, max_items=max_items)
        else:
            items = self.list_all()[:max_items]

        if not items:
            return ""
        lines = ["[Saved Personal Memories & Preferences]"]
        for item in items:
            lines.append(f"- {item['content']}")
        return "\n".join(lines)
