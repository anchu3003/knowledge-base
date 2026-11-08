import logging
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Suppress ChromaDB telemetry warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*telemetry.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*capture.*")

# Configure logging
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("chromadb.telemetry").setLevel(logging.ERROR)

from app.core.config import get_settings
from app.core.errors import (
    AppError,
    DocumentStoreError,
    ServiceUnavailableError,
    error_body,
    http_status_error,
)
from app.core.middleware import RequestIDMiddleware, get_request_id
from app.core.sse import SSE_HEADERS, sse_event_stream
from app.services.document_service import DocumentService
from app.services.chat_service import ChatService
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentUploadResponse,
    HealthResponse
)

# Global service instances
document_service: Optional[DocumentService] = None
chat_service: Optional[ChatService] = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize services on startup and cleanup on shutdown"""
    global document_service, chat_service

    document_service = None
    chat_service = None

    try:
        setting = get_settings()
        # Initialize services
        try:
            print("Initializing document service...")
            document_service = DocumentService(setting)
            print("Document service initialized")
        except Exception as e:
            print(f"Failed to initialize document service: {str(e)}")
            raise

        try:
            print("Initializing chat service...")
            chat_service = ChatService(setting, document_service)
            print("Chat service initialized")
        except Exception as e:
            print(f"Failed to initialize chat service: {str(e)}")
            raise

        # Auto-load documents if enabled
        if setting.auto_load_on_startup:
            print("Auto-loading documents from 'documents' folder...")
            try:
                result = await document_service.auto_load_documents()
                if result["processed_files"] > 0:
                    print(f"Auto-loaded {result['processed_files']} files, {result['total_chunks']} chunks")
                else:
                    print("No documents found to auto-load")
            except Exception as e:
                print(f"Warning: Error auto-loading documents: {str(e)}")
                print("Continuing startup without auto-loaded documents...")

        print("RAG Chatbot API initialized successfully")
    except Exception as e:
        print(f"Fatal error during startup: {str(e)}")
        import traceback
        traceback.print_exc()
        # Re-raise to prevent the app from starting in an invalid state
        # But wrap it to provide better error context
        raise RuntimeError(f"Failed to initialize application: {str(e)}") from e

    try:
        yield  # --- app runs here ---
    finally:
        # Cleanup
        try:
            if document_service:
                await document_service.cleanup()
            print("RAG Chatbot API shutdown complete")
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="RAG Chatbot API",
    description="A RAG (Retrieval-Augmented Generation) chatbot API for project documentation and source code analysis.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)
origins = [
    "http://localhost:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of allowed origins
    allow_credentials=True,  # Allow cookies, authorization headers
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all HTTP headers
)

# request_id cho mọi request (KB-3.1): thêm SAU CORS để middleware này là lớp ngoài cùng
# ⇒ response lỗi (kể cả 500 của ServerErrorMiddleware) vẫn có header X-Request-ID.
app.add_middleware(RequestIDMiddleware)

logger = logging.getLogger(__name__)


# ------------------------------
# Global error handlers (KB-3.1)
# ------------------------------
# Contract lỗi duy nhất: {"error": {"code", "message", "request_id"}}.
# Chi tiết nội bộ (`str(e)`, host provider, path, traceback) **chỉ** vào log, không ra response.
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Serialize `AppError` (taxonomy của service) thành response lỗi chuẩn."""
    request_id = get_request_id(request)
    if exc.http_status >= 500:
        logger.error(
            "request_id=%s code=%s status=%s internal=%s",
            request_id, exc.code, exc.http_status, exc.internal_detail, exc_info=True,
        )
    else:
        logger.warning(
            "request_id=%s code=%s status=%s internal=%s",
            request_id, exc.code, exc.http_status, exc.internal_detail,
        )
    return JSONResponse(
        status_code=exc.http_status,
        content=error_body(exc.code, exc.public_message, request_id),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 cùng envelope; chỉ trả `loc` + `msg`, **không** echo lại giá trị client gửi."""
    request_id = get_request_id(request)
    details = [
        {
            "loc": ".".join(str(part) for part in error.get("loc", ())),
            "msg": error.get("msg", "Invalid value."),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    logger.warning("request_id=%s code=validation_error errors=%s", request_id, len(details))
    body = error_body("validation_error", "Request body is invalid.", request_id)
    body["error"]["details"] = details
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """404/405… do framework raise cũng dùng envelope lỗi chung (không để `{"detail"}` lẻ)."""
    request_id = get_request_id(request)
    mapped = http_status_error(exc.status_code, internal_detail=str(exc.detail))
    logger.warning("request_id=%s code=%s status=%s", request_id, mapped.code, mapped.http_status)
    return JSONResponse(
        status_code=mapped.http_status,
        content=error_body(mapped.code, mapped.public_message, request_id),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback 500: log stack kèm request_id, client chỉ nhận `internal_error`."""
    request_id = get_request_id(request)
    logger.error(
        "request_id=%s code=internal_error unhandled=%s", request_id, type(exc).__name__, exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "Internal server error.", request_id),
    )


# Dependency injection for FastAPI
def get_document_service() -> DocumentService:
    """Dependency to get document service"""
    if document_service is None:
        raise ServiceUnavailableError("document_service is not initialized")
    return document_service


def get_chat_service() -> ChatService:
    """Dependency to get chat service"""
    if chat_service is None:
        raise ServiceUnavailableError("chat_service is not initialized")
    return chat_service


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with API information"""
    return HealthResponse(
        status="healthy",
        message="RAG Chatbot API is running",
        version="1.0.0"
    )


@app.post("/documents/refresh", response_model=DocumentUploadResponse)
async def refresh_documents(
        service: DocumentService = Depends(get_document_service)
):
    """
    Refresh documents by re-loading from the default documents folder.
    This will clear existing documents and reload everything.
    """
    try:
        # Clear existing documents first
        await service.clear_database()

        # Auto-load documents again
        result = await service.auto_load_documents()

        return DocumentUploadResponse(
            success=True,
            message=f"Successfully refreshed {result['processed_files']} documents",
            processed_files=result["processed_files"],
            total_chunks=result["total_chunks"],
            details=result.get("details", [])
        )

    except AppError:
        raise
    except Exception as e:
        raise DocumentStoreError(f"refresh_documents: {type(e).__name__}: {e}") from e


@app.get("/documents/folder-info")
async def get_documents_folder_info():
    """Get information about the documents folder"""
    try:
        setting = get_settings()
        docs_folder = Path(setting.documents_folder)

        if not docs_folder.exists():
            return {
                "folder_path": str(docs_folder.absolute()),
                "exists": False,
                "files_count": 0,
                "supported_files": [],
            }

        # Count files by extension
        files_info = {}
        total_files = 0
        supported_files = []

        for file_path in docs_folder.rglob("*"):
            if file_path.is_file():
                total_files += 1
                ext = file_path.suffix.lower()
                files_info[ext] = files_info.get(ext, 0) + 1

                if ext in settings.supported_extensions:
                    supported_files.append({
                        "name": file_path.name,
                        "path": str(file_path.relative_to(docs_folder)),
                        "size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
                        "extension": ext
                    })

        return {
            "folder_path": str(docs_folder.absolute()),
            "exists": True,
            "total_files": total_files,
            "files_by_extension": files_info,
            "supported_files_count": len(supported_files),
            "supported_files": supported_files[:20],  # Limit to first 20 for display
            "auto_load_enabled": settings.auto_load_on_startup
        }

    except AppError:
        raise
    except Exception as e:
        raise AppError(f"folder_info: {type(e).__name__}: {e}") from e


@app.post("/chat", response_model=ChatResponse)
async def chat(
        request: ChatRequest,
        service: ChatService = Depends(get_chat_service)
):
    """
    Chat with the RAG system about the uploaded documents.
    The system will retrieve relevant context and generate responses.
    """
    response = await service.chat(
        message=request.message,
        conversation_id=request.conversation_id,
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )

    return ChatResponse(
        response=response["answer"],
        conversation_id=response["conversation_id"],
        sources=response.get("sources", []),
        metadata=response.get("metadata", {})
    )


@app.post("/chat/stream")
async def chat_stream(
        payload: ChatRequest,
        http_request: Request,
        service: ChatService = Depends(get_chat_service),
):
    """Stream chat responses as Server-Sent Events (SSE) — KB-3.3.

    Contract: `start → token* → (end | error)`.

    - event `error` = `{"type": "error", "error": {code, message, request_id}}` (cùng schema `/chat`);
    - heartbeat comment `: ping` nếu quá `SSE_HEARTBEAT_SECONDS` không có token;
    - header chống buffer của proxy (`X-Accel-Buffering: no`) + `Cache-Control: no-cache`;
    - client disconnect ⇒ generator dừng sạch (lưu partial answer, xem `ChatService.stream_chat`).
    """
    request_id = get_request_id(http_request)
    settings = get_settings()

    events = service.stream_chat(
        message=payload.message,
        conversation_id=payload.conversation_id,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
        request_id=request_id,
    )

    return StreamingResponse(
        sse_event_stream(events, request_id=request_id, heartbeat_seconds=settings.sse_heartbeat_seconds),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/documents/status")
async def get_document_status(
        service: DocumentService = Depends(get_document_service)
):
    """Get the status of the document database"""
    try:
        status_info = await service.get_status()
        return JSONResponse(content=status_info)
    except AppError:
        raise
    except Exception as e:
        raise DocumentStoreError(f"get_status: {type(e).__name__}: {e}") from e


@app.delete("/documents/clear")
async def clear_documents(
        service: DocumentService = Depends(get_document_service)
):
    """Clear all documents from the vector database"""
    try:
        await service.clear_database()
        return JSONResponse(content={"message": "Document database cleared successfully"})
    except AppError:
        raise
    except Exception as e:
        raise DocumentStoreError(f"clear_database: {type(e).__name__}: {e}") from e


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000, reload=True)
