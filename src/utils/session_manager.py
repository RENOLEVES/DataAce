import uuid
import pandas as pd
from typing import Optional
from models.schemas import ChatMessage


class Session:
    def __init__(self):
        self.id: str = str(uuid.uuid4())
        self.df: Optional[pd.DataFrame] = None
        self.original_filename: str = ""
        self.file_extension: str = ""
        self.history: list[ChatMessage] = []
        self.cleaned_df: Optional[pd.DataFrame] = None
        self.pending_operations: list[dict] = []
        self.applied_operations: list[dict] = []

    def add_message(self, role: str, content: str):
        self.history.append(ChatMessage(role=role, content=content))

    def get_history(self) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in self.history]


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session = Session()
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str):
        self._sessions.pop(session_id, None)


session_manager = SessionManager()