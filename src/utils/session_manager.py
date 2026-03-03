import uuid
import pandas as pd
from typing import Optional
from models.schemas import ChatMessage, ScanReport


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
        self.scan_report: Optional[ScanReport] = None

        # undo/redo feature
        self.df_history: list[pd.DataFrame] = []   # past states for undo
        self.df_future: list[pd.DataFrame] = []    # future states for redo
        self.operation_history: list[str] = []     # descriptions of operations for undo/redo

    # We need to save the state of the DataFrame before applying any cleaning operation, 
    # so we can implement undo/redo functionality.
    def snapshot(self, description: str):
        # To prevent memory issues, we can limit the history to 10 steps. Drop older steps if we exceed the limit.
        MAX_HISTORY = 10

        # Only save a snapshot if there's a cleaned DataFrame to save, 
        # otherwise we might be saving the original uncleaned state multiple times.
        if self.cleaned_df is not None:

            # Append a copy of the current cleaned DataFrame to the history stack before applying the new operation.
            self.df_history.append(self.cleaned_df.copy())

            # Append the description of the operation to the operation history, so we can show it in the UI or use it for undo/redo.
            self.operation_history.append(description)

            # clear future states on new operation
            self.df_future.clear()  

            # Drop older step if we exceed the max history limit
            if len(self.df_history) > MAX_HISTORY:
                self.df_history.pop(0)
                self.operation_history.pop(0)

    def undo(self) -> bool:
        if not self.df_history:
            return False
        self.df_future.append(self.cleaned_df.copy())
        self.cleaned_df = self.df_history.pop()

        # pop the last operation description since we're undoing it
        if self.operation_history:
            self.operation_history.pop()
        return True

    def redo(self) -> bool:
        if not self.df_future:
            return False
        self.df_history.append(self.cleaned_df.copy())
        self.cleaned_df = self.df_future.pop()
        return True

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