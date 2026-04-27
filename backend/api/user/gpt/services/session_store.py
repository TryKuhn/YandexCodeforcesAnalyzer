import uuid
from typing import Any, Dict


class SessionStore:
    _sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def create(cls, data: Dict[str, Any]) -> str:
        session_id = str(uuid.uuid4())
        cls._sessions[session_id] = data
        return session_id

    @classmethod
    def get(cls, session_id: str) -> Dict[str, Any]:
        return cls._sessions.get(session_id)

    @classmethod
    def update(cls, session_id: str, data: Dict[str, Any]):
        if session_id in cls._sessions:
            cls._sessions[session_id].update(data)

    @classmethod
    def delete(cls, session_id: str):
        cls._sessions.pop(session_id, None)
