"""In-memory, process-local store of session data keyed by a generated id."""
import uuid
from typing import Any, Dict


class SessionStore:
    """Class-level dict store of sessions; not persisted across processes."""
    _sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def create(cls, data: Dict[str, Any]) -> str:
        """Store ``data`` under a fresh uuid and return that session id."""
        session_id = str(uuid.uuid4())
        cls._sessions[session_id] = data
        return session_id

    @classmethod
    def get(cls, session_id: str) -> Dict[str, Any]:
        """Return the stored data for ``session_id`` (None if absent)."""
        return cls._sessions.get(session_id)

    @classmethod
    def update(cls, session_id: str, data: Dict[str, Any]):
        """Merge ``data`` into an existing session; no-op if it is absent."""
        if session_id in cls._sessions:
            cls._sessions[session_id].update(data)

    @classmethod
    def delete(cls, session_id: str):
        """Remove ``session_id`` from the store if present."""
        cls._sessions.pop(session_id, None)
