from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


# ------------------------------
# Health Check
# ------------------------------
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    message: str
    version: str


# ------------------------------
# Liveness / readiness (KB-3.4)
# ------------------------------
class HealthStatusResponse(BaseModel):
    """Liveness (`GET /health`) — không phụ thuộc Chroma/provider."""
    status: str = Field(..., description="Luôn 'ok' khi process còn sống")
    version: str
    uptime_seconds: float = Field(..., description="Giây kể từ lúc lifespan start")


class ReadinessCheck(BaseModel):
    """Một check của readiness: `ok` + mô tả ngắn (không chứa secret)."""
    ok: bool
    detail: str


class ReadinessResponse(BaseModel):
    """Readiness (`GET /ready`): `ok` (200) · `degraded` (200, thiếu tài liệu) · `error` (503)."""
    status: str = Field(..., description="ok | degraded | error")
    checks: Dict[str, ReadinessCheck]


# ------------------------------
# Document Upload
# ------------------------------
class DocumentSyncResponse(BaseModel):
    """Kết quả `POST /documents/sync` (KB-5.1) — index tăng dần từ folder."""

    success: bool
    message: str
    added: List[str] = []
    updated: List[str] = []
    removed: List[str] = []
    skipped: List[Dict[str, Any]] = []
    unchanged: int = 0
    total_chunks: int = 0
    removed_chunks: int = 0
    elapsed_ms: int = 0
    details: Optional[List[str]] = None


class DocumentUploadResponse(BaseModel):
    """Response model for document upload"""
    success: bool
    message: str
    processed_files: int
    total_chunks: int
    details: Optional[List[Dict[str, Any]]] = None


class ConversationMessage(BaseModel):
    """1 message trong lịch sử hội thoại (KB-5.2).

    `content` là bản **đã redact PII** khi lưu (xem `ChatService._update_conversation`).
    """

    role: str
    content: str
    timestamp: str
    interrupted: bool = False


class ConversationSummary(BaseModel):
    """1 dòng trong `GET /conversations` (không kèm messages)."""

    id: str
    title: str = ""
    created_at: str = ""
    updated_at: str = ""
    message_count: int = 0


class ConversationListResponse(BaseModel):
    """`GET /conversations` — mới nhất trước."""

    conversations: List[ConversationSummary] = []
    total: int = 0


class ConversationDetail(BaseModel):
    """`GET /conversations/{id}` — kèm toàn bộ messages."""

    id: str
    title: str = ""
    created_at: str = ""
    updated_at: str = ""
    messages: List[ConversationMessage] = []



# ------------------------------
# Chat
# ------------------------------
class ChatRequest(BaseModel):
    """Request model for chat.

    KB-9.1: `max_tokens`/`temperature` mặc định **None** (không hard-code 1000/0.7 ở đây).
    Trước đây default nằm ở schema ⇒ Pydantic luôn điền 1000/0.7 khi client không gửi ⇒ service thấy
    "có giá trị" và **bỏ qua** `DEFAULT_MAX_TOKENS`/`DEFAULT_TEMPERATURE` trong env (2 biến đó thành chết).
    """
    message: str = Field(..., description="The user's message")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for context")
    max_tokens: Optional[int] = Field(
        None, ge=64, le=8000, description="Maximum tokens in response (mặc định: DEFAULT_MAX_TOKENS)",
    )
    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Temperature for response generation (mặc định: DEFAULT_TEMPERATURE)",
    )



class ChatResponse(BaseModel):
    """Response model for chat"""
    response: str
    conversation_id: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ------------------------------
# Document Source (for RAG)
# ------------------------------
class DocumentSource(BaseModel):
    """Model for document source information"""
    file_path: str
    chunk_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: float = Field(..., description="Relevance score")


# ------------------------------
# Conversation Message
# ------------------------------

class ConversationMessage(BaseModel):
    """Model for a conversation message"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ------------------------------
# Error contract (KB-3.1)
# ------------------------------

class ErrorDetail(BaseModel):
    """Chi tiết một lỗi: `code` hằng số + message chung + `request_id` để tra log."""
    code: str = Field(..., description="Stable snake_case error code, e.g. provider_rate_limited")
    message: str = Field(..., description="Safe, generic message (no internal details)")
    request_id: str = Field(..., description="Request id, matches the X-Request-ID response header")
    details: Optional[List[Dict[str, Any]]] = Field(
        None, description="Optional field-level details (only for validation errors)"
    )


class ErrorResponse(BaseModel):
    """Envelope lỗi duy nhất của API: `{"error": {code, message, request_id}}`."""
    error: ErrorDetail

