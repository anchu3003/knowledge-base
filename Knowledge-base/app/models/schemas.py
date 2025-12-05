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
# Document Upload
# ------------------------------
class DocumentUploadResponse(BaseModel):
    """Response model for document upload"""
    success: bool
    message: str
    processed_files: int
    total_chunks: int
    details: Optional[List[Dict[str, Any]]] = None


# ------------------------------
# Chat
# ------------------------------
class ChatRequest(BaseModel):
    """Request model for chat"""
    message: str = Field(..., description="The user's message")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for context")
    max_tokens: Optional[int] = Field(1000, description="Maximum tokens in response")
    temperature: Optional[float] = Field(0.7, description="Temperature for response generation")


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
