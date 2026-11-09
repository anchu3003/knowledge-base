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
    ConversationStoreError,
    DocumentStoreError,
    DocumentsFolderEmptyError,
    NotFoundError,
    ServiceUnavailableError,
    error_body,
    http_status_error,
)
from app.core.logging_setup import configure_logging
from app.core.middleware import RequestIDMiddleware, get_request_id
from app.core.sse import SSE_HEADERS, sse_event_stream
from app.services.document_service import DocumentService
from app.services.chat_service import ChatService
from app.services.conversation_store import ConversationStore
from app.services.health_service import HealthService
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    DocumentUploadResponse,
    DocumentSyncResponse,
    HealthResponse,
    HealthStatusResponse,
    ReadinessResponse,
)

# Global service instances
document_service: Optional[DocumentService] = None
chat_service: Optional[ChatService] = None
health_service: Optional[HealthService] = None
conversation_store: Optional[ConversationStore] = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize services on startup and cleanup on shutdown"""
    global document_service, chat_service, health_service, conversation_store

    document_service = None
    chat_service = None
    health_service = None
    conversation_store = None

    try:
        setting = get_settings()
        # KB-5.9 (trả TD-18): gắn handler cho logger `app.*` TRƯỚC khi service khởi tạo ⇒ log INFO hiện ra.
        log_level = configure_logging(getattr(setting, "log_level", "INFO"))
        logging.getLogger(__name__).info("logging configured: level=%s", logging.getLevelName(log_level))
        # `uptime_seconds` của /health tính từ đây (KB-3.4)
        health_service = HealthService(setting)
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
            # Lịch sử hội thoại bền (KB-5.2): SQLite trong `CHAT_DB_PATH`. Không mở được DB ⇒ vẫn chạy
            # (chat in-memory) thay vì chặn startup — mất lịch sử còn hơn không lên được.
            if setting.chat_db_path:
                try:
                    conversation_store = ConversationStore(
                        setting.chat_db_path, max_conversations=setting.max_conversations
                    )
                    print(
                        f"Conversation store ready: {setting.chat_db_path} "
                        f"({conversation_store.count()} session đã lưu, max={setting.max_conversations})"
                    )
                except Exception as e:
                    print(f"Warning: conversation store unavailable ({type(e).__name__}: {e}) — chat only in memory")
                    conversation_store = None
            chat_service = ChatService(setting, document_service, conversation_store=conversation_store)
            print("Chat service initialized")
        except Exception as e:
            print(f"Failed to initialize chat service: {str(e)}")
            raise

        # Index tăng dần lúc khởi động (KB-5.1, Q&A Q1 = nút Đồng bộ + tự động khi start)
        if setting.auto_load_on_startup:
            documents_folder = Path(setting.documents_folder)
            supported = count_supported_files(documents_folder, setting.supported_extensions)
            # Guard: folder rỗng/không tồn tại ⇒ KHÔNG sync (nếu sync, mọi file đang có index sẽ bị coi là "đã xoá"
            # và bị xoá khỏi vector store — đúng lỗi mất dữ liệu mà KB-4.10 đã chặn cho `/documents/refresh`).
            if not documents_folder.exists() or supported == 0:
                print(
                    f"Skip startup sync: folder '{documents_folder}' "
                    f"(exists={documents_folder.exists()}, supported_files={supported})"
                )
            else:
                print(f"Syncing documents from '{documents_folder}' ({supported} file hỗ trợ)...")
                try:
                    summary = await document_service.sync_documents()
                    print(
                        "Startup sync: "
                        f"+{len(summary['added'])} mới, ~{len(summary['updated'])} cập nhật, "
                        f"-{len(summary['removed'])} xoá, unchanged={summary['unchanged']}, "
                        f"chunks={summary['total_chunks']}, {summary['elapsed_ms']}ms"
                    )
                except Exception as e:
                    # Không chặn startup: app vẫn chạy được với index hiện có (chỉ thiếu file mới)
                    print(f"Warning: startup sync failed: {type(e).__name__}: {str(e)}")
                    print("Continuing startup with the existing index...")

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
            if conversation_store:
                conversation_store.close()
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
origins = [origin.strip() for origin in get_settings().allowed_origins.split(",") if origin.strip()]
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


def get_health_service() -> HealthService:
    """Dependency to get health service.

    Lazy (tạo từ settings nếu lifespan chưa chạy) ⇒ liveness probe vẫn trả lời được
    kể cả khi service nặng chưa init xong (đúng vai trò liveness).
    """
    global health_service
    if health_service is None:
        health_service = HealthService(get_settings())
    return health_service


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with API information"""
    return HealthResponse(
        status="healthy",
        message="RAG Chatbot API is running",
        version="1.0.0"
    )


@app.get("/health", response_model=HealthStatusResponse)
async def health(service: HealthService = Depends(get_health_service)):
    """Liveness probe (KB-3.4): process còn sống ⇒ **luôn 200**, không chạm Chroma/provider.

    Dùng cho Docker `HEALTHCHECK` / systemd / k8s livenessProbe.
    """
    return service.liveness()


@app.get("/ready", response_model=ReadinessResponse)
async def ready(
        deep: bool = False,
        service: HealthService = Depends(get_health_service),
):
    """Readiness probe (KB-3.4): app có đủ điều kiện trả lời không?

    - `ok` (200): provider config + prompt file + collection đều ổn;
    - `degraded` (200): collection rỗng/lỗi — vẫn nhận request (trả lời "không có trong knowledge base");
    - `error` (503): thiếu cấu hình provider / thiếu prompt file (`deep` mà provider không trả lời cũng 503).

    `deep=true` gọi provider **1 request `max_tokens=1`** (tốn quota) ⇒ **mặc định tắt**, chỉ dùng tay;
    **không** đưa vào `HEALTHCHECK` của Docker.
    """
    provider_probe = None
    if deep and chat_service is not None:
        provider_probe = chat_service.provider_probe

    payload, http_status = await service.readiness(
        document_service=document_service,
        provider_probe=provider_probe,
        deep=deep,
    )
    return JSONResponse(status_code=http_status, content=payload)


def count_supported_files(folder: Path, extensions) -> int:
    """Đếm file có extension được hỗ trợ trong folder (dùng cho guard của `/documents/refresh` — KB-4.10)."""
    if not folder.exists():
        return 0
    supported = {ext.lower() for ext in extensions}
    return sum(1 for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in supported)


@app.post("/documents/refresh", response_model=DocumentUploadResponse)
async def refresh_documents(
        service: DocumentService = Depends(get_document_service)
):
    """
    Refresh documents by re-loading from the default documents folder.
    This will clear existing documents and reload everything.
    """
    # KB-4.10: refresh = clear + auto-load. Nếu folder không tồn tại/rỗng thì clear xong sẽ **mất index**
    # mà không index lại được ⇒ chặn TRƯỚC khi clear.
    setting = get_settings()
    documents_path = Path(setting.documents_folder)
    supported = count_supported_files(documents_path, setting.supported_extensions)
    if not documents_path.exists() or supported == 0:
        raise DocumentsFolderEmptyError(
            f"refresh_documents: folder={documents_path} exists={documents_path.exists()} supported_files={supported}"
        )

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


@app.post("/documents/sync", response_model=DocumentSyncResponse)
async def sync_documents(
        service: DocumentService = Depends(get_document_service)
):
    """
    Index **tăng dần** (KB-5.1): so folder với index, chỉ embed file mới/đổi và xoá chunk của file đã bị xoá.

    Khác `/documents/refresh` (clear rồi index lại tất cả — ~22 phút với 601 chunk, TD-14): sync **không**
    xoá index hiện có nên chat vẫn trả lời được trong lúc chạy.
    """
    # Guard giống refresh: folder không tồn tại / 0 file hỗ trợ ⇒ coi như "mất nguồn" ⇒ KHÔNG sync.
    # Nếu bỏ guard này, sync sẽ thấy "index có 601 chunk mà folder rỗng" và **xoá sạch** index (mất dữ liệu).
    setting = get_settings()
    documents_path = Path(setting.documents_folder)
    supported = count_supported_files(documents_path, setting.supported_extensions)
    if not documents_path.exists() or supported == 0:
        raise DocumentsFolderEmptyError(
            f"sync_documents: folder={documents_path} exists={documents_path.exists()} supported_files={supported}"
        )

    try:
        result = await service.sync_documents()
        total_changes = len(result.get("added", [])) + len(result.get("updated", [])) + len(result.get("removed", []))
        message = (
            "Không có thay đổi nào trong folder tài liệu"
            if total_changes == 0
            else (
                f"+{len(result.get('added', []))} mới, ~{len(result.get('updated', []))} cập nhật, "
                f"-{len(result.get('removed', []))} xoá"
            )
        )
        return DocumentSyncResponse(success=True, message=message, **result)

    except AppError:
        raise
    except Exception as e:
        raise DocumentStoreError(f"sync_documents: {type(e).__name__}: {e}") from e


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

                if ext in setting.supported_extensions:
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
            "auto_load_enabled": setting.auto_load_on_startup
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


@app.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
        service: ChatService = Depends(get_chat_service)
):
    """Danh sách hội thoại đã lưu (mới nhất trước) — KB-5.2.

    Server là **nguồn sự thật** về lịch sử; FE dùng endpoint này lúc mở app và chỉ fallback
    `localStorage` khi request lỗi (BE tắt/mất mạng).
    """
    try:
        items = service.list_conversations()
        return ConversationListResponse(conversations=items, total=len(items))
    except AppError:
        raise
    except Exception as e:
        raise ConversationStoreError(f"list_conversations: {type(e).__name__}: {e}") from e


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
        conversation_id: str,
        service: ChatService = Depends(get_chat_service)
):
    """Chi tiết 1 hội thoại (kèm messages) — 404 nếu chưa từng có."""
    try:
        detail = service.get_conversation_detail(conversation_id)
        if detail is None:
            raise NotFoundError(f"Không tìm thấy hội thoại '{conversation_id}'")
        return ConversationDetail(**detail)
    except AppError:
        raise
    except Exception as e:
        raise ConversationStoreError(f"get_conversation: {type(e).__name__}: {e}") from e


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(
        conversation_id: str,
        service: ChatService = Depends(get_chat_service)
):
    """Xoá hội thoại (RAM + SQLite). 404 nếu không tồn tại — KHÔNG im lặng trả 200."""
    try:
        existed = service.get_conversation_detail(conversation_id) is not None
        if not existed:
            raise NotFoundError(f"Không tìm thấy hội thoại '{conversation_id}'")
        service.clear_conversation(conversation_id)
        return JSONResponse(content={"message": "Đã xoá hội thoại", "conversation_id": conversation_id})
    except AppError:
        raise
    except Exception as e:
        raise ConversationStoreError(f"delete_conversation: {type(e).__name__}: {e}") from e


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
