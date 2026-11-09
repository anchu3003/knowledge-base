"""Builder dùng chung cho test BE (KB-5.9 — trả TD-27).

Vấn đề: nhiều test dựng service bằng `object.__new__(ChatService)` + `SimpleNamespace(...)` chỉ có **một phần**
field. Mỗi lần thêm attribute mới vào service/settings, hàng loạt test vỡ bằng `AttributeError` — đã xảy ra
**3 lần** (`conversation_store` KB-5.2, `_index_version` KB-5.3, `multi_query_*` KB-5.4).

Cách sửa gốc: mọi field cần cho test sống ở **một chỗ** — file này. Khi thêm setting mới, thêm vào
`BASE_SETTINGS` (một dòng) thay vì sửa 3–5 file test.

Lưu ý: đây là **fake tối thiểu**, không phải `Settings` thật (không đọc `.env`), để test nhanh và không cần key.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any, Dict, Optional

from app.services.chat_service import ChatService
from app.services.document_service import DocumentService

#: Field tối thiểu để `ChatService` + `DocumentService` chạy được trong test.
BASE_SETTINGS: Dict[str, Any] = {
    # --- Chat ---
    "default_max_tokens": 128,
    "default_temperature": 0.0,
    "max_conversation_length": 10,
    "system_prompt_path": None,
    "context_max_chars": 6000,
    "openai_model": "fake-model",
    "openai_base_url": "",
    # --- PII ---
    "enable_pii_redaction": True,
    "pii_placeholder": "[REDACTED:{type}]",
    # --- Retrieval ---
    "retrieval_k": 3,
    "hybrid_candidate_k": 20,
    "enable_hybrid": False,
    "hybrid_alpha": 0.5,
    "enable_bm25": False,
    "collection_name": "documents",
    "similarity_threshold": 0.0,
    "dedup_enabled": False,
    "dedup_jaccard_threshold": 0.8,
    "max_chunks_per_file": 10,
    # --- Rerank (KB-5.3/5.4) ---
    "enable_rerank": False,
    "rerank_top_n": 8,
    "rerank_model": "fake-reranker",
    "rerank_cache_enabled": False,
    # --- Query rewrite / multi-query (KB-5.4) ---
    "enable_query_rewrite": False,
    "rewrite_system_prompt_path": None,
    "rewrite_min_results": 2,
    "rewrite_min_top_score": 0.3,
    "rewrite_max_attempts": 2,
    "multi_query_enabled": False,
    "multi_query_max_parts": 3,
    # --- Provider throttle / SSE (KB-3.2/3.3) ---
    "provider_timeout_seconds": 60.0,
    "provider_max_retries": 0,
    "provider_retry_base_delay": 2.0,
    "provider_max_concurrency": 1,
    "sse_heartbeat_seconds": 15.0,
    # --- Logging (KB-5.9) ---
    "log_level": "WARNING",
}


def make_settings(**overrides: Any) -> SimpleNamespace:
    """`Settings` giả có **đủ** field — thêm setting mới thì thêm vào `BASE_SETTINGS`."""
    values = dict(BASE_SETTINGS)
    values.update(overrides)
    return SimpleNamespace(**values)


def make_chat_service(llm: Any = None, *, settings: Optional[SimpleNamespace] = None, **overrides: Any) -> ChatService:
    """`ChatService` dựng không qua `__init__` (tránh tạo client thật), settings đầy đủ."""
    resolved = settings or make_settings(**overrides)
    service = object.__new__(ChatService)
    service.settings = resolved
    service.document_service = _make_noop_document_service()
    service.conversations = {}
    service.conversation_store = None
    service.pii = _make_redactor(resolved)
    service.provider = _make_noop_provider()
    if llm is not None:
        service.llm = llm
    return service


def make_document_service(*, settings: Optional[SimpleNamespace] = None, **overrides: Any) -> DocumentService:
    """`DocumentService` dựng không qua `__init__` (không Chroma/model), settings đầy đủ."""
    resolved = settings or make_settings(**overrides)
    service = object.__new__(DocumentService)
    service.settings = resolved
    service.executor = ThreadPoolExecutor(max_workers=1)
    service._corpus_ids = []
    service._corpus_texts = []
    service._corpus_metas = []
    service._bm25 = None
    service._cross_encoder = None
    service._index_version = 0
    service._rerank_cache = None
    service._config_fingerprint = "test"
    return service


def _make_noop_document_service():
    """Document service rỗng: có `search_similar_documents` để `chat()`/`stream_chat()` không vỡ."""

    class _NoopDocumentService:
        async def search_similar_documents(self, query, k=None, rerank_top_n=None):
            return []

    return _NoopDocumentService()


def _make_redactor(settings: SimpleNamespace):
    from app.services.pii_service import PIIRedactor

    return PIIRedactor(settings)


def _make_noop_provider():
    """Throttle giả: chạy hàm được giao ngay, không retry (test hành vi retry có file riêng).

    Có **cả `run` và `stream`** — `ChatService` dùng `provider.stream(...)` cho `/chat/stream` (KB-3.3), thiếu
    `stream` sẽ làm test SSE vỡ bằng `AttributeError` (đúng lỗi đã gặp khi tách builder — KB-5.9).
    """

    class _NoopProvider:
        async def run(self, call, op: str = "chat", retry: bool = True):
            return await call()

        async def stream(self, make_stream, op: str = "stream"):
            async for chunk in make_stream():
                yield chunk

    return _NoopProvider()
