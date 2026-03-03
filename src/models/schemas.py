from pydantic import BaseModel
from typing import Optional, Any


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    download_ready: bool = False
    download_url: Optional[str] = None


class Operation(BaseModel):
    operation: str
    column: Optional[str] = None
    strategy: Optional[str] = None
    format: Optional[str] = None
    value: Optional[Any] = None
    scope: Optional[str] = None
    to: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None


class ParsedInstructions(BaseModel):
    operations: list[Operation]
    ambiguities: list[str] = []


class ScanIssue(BaseModel):
    column: str
    issue_type: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    affected_count: int
    suggestion: str


class ScanReport(BaseModel):
    total_rows: int
    total_columns: int
    issues: list[ScanIssue]