import asyncio
import logging
import time
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

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
from app.core import runtime_settings
from app.core.auth import ApiKeyMiddleware
from app.core.rate_limit import RateLimitMiddleware, SlidingWindowLimiter
from app.core.middleware import RequestIDMiddleware, get_request_id
from app.core.sse import SSE_HEADERS, sse_event_stream
from app.services.document_service import DocumentService
from app.services.chat_service import ChatService
from app.services.conversation_store import ConversationStore
from app.services.health_service import HealthService
from app.services.startup_sync import StartupSyncState

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
# TD-25: trạng thái job sync lúc khởi động (chạy nền) — đọc được từ `/ready` + `/documents/status`.
startup_sync_state: Optional[StartupSyncState] = None



async def _run_startup_sync(
        service: "DocumentService",
        state: StartupSyncState,
        supported: int,
) -> None:
    """Chạy index sync lúc khởi động **ở nền** (TD-25) và ghi trạng thái vào `state`.

    Không raise ra ngoài: lỗi sync không được làm chết app (index cũ vẫn dùng được — cùng nguyên tắc
    KB-4.10/KB-5.1). Trạng thái đọc qua `/ready` (`checks.startup_sync`) và `/documents/status`.
    """
    state.start()
    started = time.monotonic()
    try:
        summary = await service.sync_documents()
    except asyncio.CancelledError:
        # Shutdown giữa lúc sync ⇒ ghi lại để lần sau biết (index giữ nguyên, sync lại lúc restart).
        state.fail("CancelledError")
        logging.getLogger(__name__).warning("startup sync cancelled during shutdown")
        raise
    except Exception as exc:
        state.fail(type(exc).__name__)
        logging.getLogger(__name__).warning(
            "startup sync failed: %s: %s — vẫn phục vụ với index cũ",
            type(exc).__name__,
            exc,
        )
        return

    state.finish(summary)
    logging.getLogger(__name__).info(
        "startup sync done: files=%s +%s ~%s -%s unchanged=%s chunks=%s %.1fs",
        supported,
        len(summary.get("added") or []),
        len(summary.get("updated") or []),
        len(summary.get("removed") or []),
        summary.get("unchanged"),
        summary.get("total_chunks"),
        time.monotonic() - started,
    )



@asynccontextmanager
async def lifespan(application: FastAPI):

    """Initialize services on startup and cleanup on shutdown"""
    global document_service, chat_service, health_service, conversation_store, startup_sync_state

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
        # TD-25: mặc định chạy **nền** ⇒ app nhận request ngay, trạng thái xem ở `/ready`.
        startup_sync_state = StartupSyncState()
        application.state.startup_sync = startup_sync_state
        if setting.auto_load_on_startup:
            documents_folder = Path(setting.documents_folder)
            supported = count_supported_files(documents_folder, setting.supported_extensions)
            # Guard: folder rỗng/không tồn tại ⇒ KHÔNG sync (nếu sync, mọi file đang có index sẽ bị coi là "đã xoá"
            # và bị xoá khỏi vector store — đúng lỗi mất dữ liệu mà KB-4.10 đã chặn cho `/documents/refresh`).
            if not documents_folder.exists() or supported == 0:
                reason = f"folder không tồn tại hoặc 0 file hỗ trợ (exists={documents_folder.exists()})"
                startup_sync_state.skip(reason)
                print(f"Skip startup sync: {reason}")
            elif getattr(setting, "startup_sync_background", True):
                print(f"Startup sync chạy nền: '{documents_folder}' ({supported} file hỗ trợ)...")
                task = asyncio.create_task(
                    _run_startup_sync(document_service, startup_sync_state, supported),
                    name="startup-index-sync",
                )
                # Giữ tham chiếu để task không bị GC giữa đường (asyncio chỉ weak-ref task).
                application.state.startup_sync_task = task
            else:
                print(f"Syncing documents from '{documents_folder}' ({supported} file hỗ trợ)...")
                try:
                    summary = await document_service.sync_documents()
                    startup_sync_state.finish(summary)
                    print(
                        "Startup sync: "
                        f"+{len(summary['added'])} mới, ~{len(summary['updated'])} cập nhật, "
                        f"-{len(summary['removed'])} xoá, unchanged={summary['unchanged']}, "
                        f"chunks={summary['total_chunks']}, {summary['elapsed_ms']}ms"
                    )
                except Exception as e:
                    # Không chặn startup: app vẫn chạy được với index hiện có (chỉ thiếu file mới)
                    startup_sync_state.fail(type(e).__name__)
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
# KB-5.5: auth token tĩnh — thêm **TRƯỚC** RequestID để RequestID nằm ngoài cùng (Starlette: middleware thêm
# sau cùng là lớp ngoài). Nhờ vậy response 401 vẫn có `request_id` + header `X-Request-ID` do RequestID gắn.
# Mặc định `AUTH_ENABLED=false` ⇒ middleware trả qua ngay, hành vi không đổi.
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(RequestIDMiddleware)
# TD-20: rate limit per-IP cho `/chat` + `/chat/stream`. Thêm **trước** RequestID/ApiKey ⇒ nằm trong
# cùng (RequestID vẫn là lớp ngoài cùng để 429 có `request_id`). Cờ `RATE_LIMIT_ENABLED=false` mặc định
# ⇒ middleware trả qua ngay, hành vi không đổi.
_rate_limit_settings = get_settings()
_rate_limiter = SlidingWindowLimiter(
    int(getattr(_rate_limit_settings, "rate_limit_max_requests", 30) or 30),
    float(getattr(_rate_limit_settings, "rate_limit_window_seconds", 60.0) or 60.0),
)
app.add_middleware(RateLimitMiddleware, limiter=_rate_limiter)


def rate_limit_stats() -> dict:
    """Số liệu rate limit cho `/ready` (không lộ IP/key)."""
    return {
        "enabled": bool(getattr(get_settings(), "rate_limit_enabled", False)),
        "max_requests": _rate_limiter.max_requests,
        "window_seconds": _rate_limiter.window_seconds,
        "blocked": _rate_limiter.blocked,
    }



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
        startup_sync=startup_sync_state,
        rate_limit=rate_limit_stats(),
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


def _on_runtime_settings_change() -> None:
    """Đổi tham số ảnh hưởng retrieval ⇒ tính lại fingerprint + xoá cache rerank (ADR-0012)."""
    if document_service is not None:
        document_service.refresh_config_fingerprint()


@app.get("/settings")
async def get_settings_endpoint():
    """Tham số chỉnh được **lúc chạy** (KB-9.4) + giá trị mặc định của server.

    UI dựng control từ `tunables`; `values` là giá trị đang có hiệu lực, `defaults` là giá trị env lúc
    khởi động, `overridden` cho biết tham số nào người dùng đã đổi.
    """
    return JSONResponse(content=runtime_settings.describe(get_settings()))


@app.put("/settings")
async def update_settings_endpoint(payload: Dict[str, Any]):
    """Áp một phần tham số (partial update). Trả về giá trị sau khi áp.

    Chỉ nhận whitelist trong `app/core/runtime_settings.py`; tham số cần re-index (chunk size, embedding
    model…) **không** đổi được ở đây. Giá trị ngoài `min/max` ⇒ 422 theo envelope lỗi KB-3.1.
    """
    try:
        values = runtime_settings.apply_updates(
            get_settings(), payload, on_retrieval_change=_on_runtime_settings_change,
        )
    except ValueError as exc:
        raise AppError(str(exc), code="invalid_setting", http_status=422,
                       message="Cấu hình không hợp lệ.") from exc
    return JSONResponse(content={"values": values,
                                 "overridden": sorted(runtime_settings._overrides)})


@app.post("/settings/reset")
async def reset_settings_endpoint():
    """Trả mọi tham số về default của server (env)."""
    values = runtime_settings.reset(get_settings(), on_retrieval_change=_on_runtime_settings_change)
    return JSONResponse(content={"values": values, "overridden": []})


@app.get("/documents/status")

async def get_document_status(
        service: DocumentService = Depends(get_document_service)
):
    """Get the status of the document database"""
    try:
        status_info = await service.get_status()
        # TD-25: kèm trạng thái job sync lúc khởi động ⇒ biết "đang index nền" hay "đã xong/ lỗi"
        # mà không phải đọc log container.
        if startup_sync_state is not None:
            status_info["startup_sync"] = startup_sync_state.as_dict()
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
