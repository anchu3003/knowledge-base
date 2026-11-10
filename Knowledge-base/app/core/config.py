from typing import List, Optional

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict, BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    app_name: str = "RAG Chatbot API"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="DEBUG")

    # OpenAI Settings
    openai_api_key: SecretStr = SecretStr(Field(..., alias="OPENAI_API_KEY"))
    openai_base_url: str = Field(..., alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-3.5-turbo", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-ada-002", alias="OPENAI_EMBEDDING_MODEL")
    openai_api_type: str = Field(default="openai", alias="OPENAI_API_TYPE")
    openai_api_version: str = Field(default="2023-05-15", alias="OPENAI_API_VERSION")

    # Embedding model (local sentence-transformers). Changing this requires re-indexing
    # the vector store because the embedding dimension may differ (KB-6.2).
    # Default: Qwen3-Embedding-0.6B — multilingual (VN + EN), 1024-dim.
    embedding_model: str = Field(default="Qwen/Qwen3-Embedding-0.6B", alias="EMBEDDING_MODEL")

    # Kiểu số thực khi chạy embedding trên CPU (TD-14). Model Qwen3 mặc định bf16, nhưng **CPU không có
    # kernel bf16 nhanh** — đo 2026-11-10 (64 chunk, cùng model): bf16 **1,87 chunk/s** vs float32
    # **8,11 chunk/s** ⇒ nhanh **4,3×** (601 chunk ~22 phút → ~1,3 phút).
    # Đổi giá trị này ⇒ **phải re-index toàn bộ** (`DELETE /documents/clear` rồi `POST /documents/sync`):
    # vector float32 và bfloat16 khác nhau về số ⇒ trộn 2 loại trong 1 collection làm retrieval lệch.
    embedding_torch_dtype: str = Field(default="float32", alias="EMBEDDING_TORCH_DTYPE")

    # ChromaDB Settings
    chroma_db_path: str = Field(default="./chroma_db", alias="CHROMA_DB_PATH")
    collection_name: str = Field(default="documents", alias="COLLECTION_NAME")

    # Document Processing Settings
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")
    embedding_batch_size: int = Field(default=64, alias="EMBEDDING_BATCH_SIZE")

    # Supported file types
    supported_extensions: List[str] = Field(
        default=[".md", ".docx", ".pdf", ".txt", ".json"],
        alias="SUPPORTED_EXTENSIONS"
    )

    # Document folder settings
    documents_folder: str = Field(default="Interview", alias="DOCUMENTS_FOLDER")
    auto_load_on_startup: bool = Field(default=True, alias="AUTO_LOAD_ON_STARTUP")

    # Lịch sử hội thoại bền (KB-5.2): 1 file SQLite. Đặt trong volume `./data` để sống qua restart.
    # Để rỗng (`CHAT_DB_PATH=`) ⇒ tắt persistence, quay lại hành vi in-memory (chỉ dùng khi debug).
    chat_db_path: str = Field(default="./data/chat.db", alias="CHAT_DB_PATH")
    # Giữ tối đa bao nhiêu session trong DB (Q&A KB-5.2 Q3 = 200). Vượt ⇒ xoá session cũ nhất.
    max_conversations: int = Field(default=200, alias="MAX_CONVERSATIONS")


    # Index sync lúc khởi động (TD-25): chạy **nền** ⇒ app lên healthy ngay, trạng thái xem ở `/ready`
    # (`checks.startup_sync`). Đặt `false` để quay lại hành vi cũ (await sync trong lifespan).
    startup_sync_background: bool = Field(default=True, alias="STARTUP_SYNC_BACKGROUND")

    # Rate limit phía server (TD-20): chặn 1 IP gọi dồn dập `/chat` + `/chat/stream` (mỗi câu tốn
    # rerank CPU + quota provider). Cờ **TẮT mặc định** (như `AUTH_ENABLED`) ⇒ hành vi không đổi;
    # bật khi mở ra LAN/VPS, đi cùng KB-5.5 auth.
    rate_limit_enabled: bool = Field(default=False, alias="RATE_LIMIT_ENABLED")
    rate_limit_max_requests: int = Field(default=30, alias="RATE_LIMIT_MAX_REQUESTS")
    rate_limit_window_seconds: float = Field(default=60.0, alias="RATE_LIMIT_WINDOW_SECONDS")

    # CORS (KB-4.7): danh sách origin của FE, phân tách bằng dấu phẩy.
    # Mặc định gồm port dev 3000 và port compose 3010 (dời port để không trùng project khác).
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:3010,http://127.0.0.1:3000,http://127.0.0.1:3010",
        alias="ALLOWED_ORIGINS",
    )

    # RAG Settings
    # RETRIEVAL_K=3: chốt bằng số đo KB-2.5 (grid 10 cấu hình) — precision@k 0.533 vs 0.347 ở k=5,
    # `MRR` 1.0 giữ nguyên, `distinct_file_ratio` 0.756 (tốt nhất trong nhóm rerank on).
    retrieval_k: int = Field(default=3, alias="RETRIEVAL_K")
    # Ngưỡng cosine tối thiểu cho **dense candidates** (0 = tắt). Chỉ áp cho dense vì score hybrid
    # đã min-max normalize còn rerank là logits cross-encoder (khác scale, không so được với cosine).
    # Đo/chốt giá trị thật ở KB-2.5 — đừng đặt số khi chưa đo.
    similarity_threshold: float = Field(default=0.0, alias="SIMILARITY_THRESHOLD")

    # Hậu xử lý kết quả retrieval (KB-2.2)
    # Bỏ chunk gần trùng nội dung (Jaccard shingle 3-gram >= ngưỡng) trước khi cắt top-k.
    dedup_enabled: bool = Field(default=True, alias="DEDUP_ENABLED")
    dedup_jaccard_threshold: float = Field(default=0.8, alias="DEDUP_JACCARD_THRESHOLD")
    # Tối đa số chunk của cùng 1 file trong top-k (0 = tắt). Chống "5 tài liệu giống nhau".
    max_chunks_per_file: int = Field(default=2, alias="MAX_CHUNKS_PER_FILE")

    # Query Rewriting Settings
    enable_query_rewrite: bool = Field(default=True, alias="ENABLE_QUERY_REWRITE")
    rewrite_min_results: int = Field(default=2, alias="REWRITE_MIN_RESULTS")
    rewrite_min_top_score: float = Field(default=0.3, alias="REWRITE_MIN_TOP_SCORE")
    rewrite_max_attempts: int = Field(default=2, alias="REWRITE_MAX_ATTEMPTS")

    # Multi-query (KB-5.4): tách câu hỏi nhiều ý bằng **heuristic** (0 token LLM) rồi retrieve từng phần
    # và gộp kết quả. Tắt bằng `MULTI_QUERY_ENABLED=false` để quay lại hành vi 1 bước (A/B + rollback).
    multi_query_enabled: bool = Field(default=True, alias="MULTI_QUERY_ENABLED")
    multi_query_max_parts: int = Field(default=3, alias="MULTI_QUERY_MAX_PARTS")

    # Hybrid Retrieval and Re-ranking
    enable_bm25: bool = Field(default=True, alias="ENABLE_BM25")
    enable_hybrid: bool = Field(default=True, alias="ENABLE_HYBRID")
    hybrid_alpha: float = Field(default=0.5, alias="HYBRID_ALPHA")  # weight for dense vs. sparse
    hybrid_candidate_k: int = Field(default=20, alias="HYBRID_CANDIDATE_K")
    enable_rerank: bool = Field(default=True, alias="ENABLE_RERANK")
    # KB-5.3 (trả TD-15) + KB-5.8 (trả TD-29): đo bằng `eval/run_eval.py`, bộ vàng v3 = **20 câu**, cache TẮT.
    # | # | Cấu hình (20 câu)                    | hit@k | MRR   | precision@k | distinct | p50      |
    # | 1 | top-8, multi-query OFF (baseline)    | 1.0   | 0.975 | 0.533       | 0.784    | 9.702 s  |
    # | 2 | top-8, multi-query ON (đang chạy)    | 1.0   | 0.975 | 0.617       | 0.750    | 6.500 s  |
    # | 3 | top-6, multi-query OFF               | 1.0   | 1.000 | 0.567       | 0.750    | 3.321 s  |
    # | 4 | top-6, multi-query ON, parts=top//2  | 1.0   | 0.975 | 0.567 (−8%) | 0.750    | 1.883 s  |
    # | 5 | **top-6, multi-query ON, parts=full**| 1.0   | 0.975 | **0.617**   | 0.783    | **3.439 s** |
    # | 6 | top-4, multi-query OFF               | 1.0   | 1.000 | 0.550       | 0.767    | 2.002 s  |
    # | 7 | top-4, multi-query ON, parts=top//2  | 1.0   | 0.883 | 0.483       | 0.867    | 1.115 s  |
    # Chốt **6** (#5): mọi metric chất lượng **bằng hoặc tốt hơn** cấu hình đang chạy (#2), p50 **−47%**.
    # #4 và #7 nhanh hơn nhưng mỗi phần chỉ chấm `top//2` ⇒ precision tụt >5% (đó là lý do phần nay chấm đủ top-N).
    rerank_top_n: int = Field(default=6, alias="RERANK_TOP_N")
    # KB-9.4: ngưỡng điểm rerank — dưới ngưỡng thì **bỏ nguồn** (coi như không liên quan).
    # Đo trên bộ vàng 28 câu (2026-11-10): câu ngoài phạm vi có score <= 0,0003; chunk đúng thấp nhất
    # 0,0031 (p10 0,0278). Chọn 0,02 ⇒ giữ 20/23 nguồn đúng, bỏ ~80% nhiễu, diệt 100% câu ngoài phạm vi.
    # 0 = tắt lọc. Đổi lúc chạy được qua `PUT /settings`.
    relevance_min_score: float = Field(default=0.02, alias="RELEVANCE_MIN_SCORE")
    rerank_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANK_MODEL")

    # Cache điểm rerank trong RAM (KB-5.3 — trả TD-15). Khoá = query + index_version + tham số ⇒
    # sync/refresh tài liệu là tự vô hiệu. TTL chặn kết quả cũ ám quá lâu.
    rerank_cache_enabled: bool = Field(default=True, alias="RERANK_CACHE_ENABLED")
    rerank_cache_ttl_seconds: int = Field(default=3600, alias="RERANK_CACHE_TTL_SECONDS")
    rerank_cache_max_entries: int = Field(default=256, alias="RERANK_CACHE_MAX_ENTRIES")

    # Chat Settings
    default_temperature: float = Field(default=0.7, alias="DEFAULT_TEMPERATURE")
    default_max_tokens: int = Field(default=1000, alias="DEFAULT_MAX_TOKENS")
    max_conversation_length: int = Field(default=10, alias="MAX_CONVERSATION_LENGTH")

    # Provider resilience (KB-3.2) — Groq free tier TPM 8000: retry có ngân sách + serialize call.
    # Timeout đẩy thẳng vào SDK (`ChatOpenAI(timeout=…)`); retry do `ProviderThrottle` quyết định
    # (`ChatOpenAI(max_retries=0)`) để chỉ có MỘT tầng retry. Q&A KB-3.2: 2 retry (~6s) + concurrency 1.
    provider_timeout_seconds: float = Field(default=60.0, alias="PROVIDER_TIMEOUT_SECONDS")
    provider_max_retries: int = Field(default=2, alias="PROVIDER_MAX_RETRIES")
    provider_retry_base_delay: float = Field(default=2.0, alias="PROVIDER_RETRY_BASE_DELAY")
    provider_max_concurrency: int = Field(default=1, alias="PROVIDER_MAX_CONCURRENCY")

    # SSE (KB-3.3): gửi comment `: ping` nếu quá N giây không có token, để proxy/idle timeout
    # không cắt kết nối khi LLM chậm (rerank ~8s + LLM ~2s). Client SSE bỏ qua comment an toàn.
    sse_heartbeat_seconds: float = Field(default=15.0, alias="SSE_HEARTBEAT_SECONDS")

    # Prompt Settings
    # Path to the system prompt template file. The template may contain a `{context}` placeholder.
    # Auth tối giản (KB-5.5) — **mặc định TẮT** để hành vi local không đổi; bật khi mở LAN/VPS:
    #   AUTH_ENABLED=true + API_TOKEN=<chuỗi dài>   (client gửi header `X-API-Key`)
    # Bật mà `API_TOKEN` rỗng ⇒ **fail-closed** (chặn tất cả), không phải "cho qua".
    # Endpoint công khai khi bật: `/` và `/health` (healthcheck Docker KB-3.4).
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    api_token: str = Field(default="", alias="API_TOKEN")

    # KB-5.9 (trả TD-18): level cho logger `app.*` (INFO thấy được log thật thay vì chỉ print).
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    system_prompt_path: str = Field(default="./prompts/system_prompt.txt", alias="SYSTEM_PROMPT_PATH")
    # Path to the query rewrite system prompt. No placeholders required.
    rewrite_system_prompt_path: str = Field(default="./prompts/rewrite_system_prompt.txt",
                                            alias="REWRITE_SYSTEM_PROMPT_PATH")
    # Tổng budget ký tự của context đưa vào prompt (KB-2.3). Cắt theo budget tổng thay vì
    # cắt cứng 500 ký tự/chunk (bản cũ làm mất nửa bằng chứng với chunk_size=1000).
    context_max_chars: int = Field(default=6000, alias="CONTEXT_MAX_CHARS")

    # PII / secret redaction (see .clinerules/30-pii-safety.md)
    enable_pii_redaction: bool = Field(default=True, alias="ENABLE_PII_REDACTION")
    pii_placeholder: str = Field(default="[REDACTED:{type}]", alias="PII_PLACEHOLDER")
    # Whether to redact PII in document chunks before indexing (KB-1.2)
    pii_redact_ingest: bool = Field(default=False, alias="PII_REDACT_INGEST")

    # Read .env for local development; real env vars still take precedence.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", env_file_encoding="utf-8",
                                      extra="ignore")


# ---------------------------
# Singleton pattern helpers
# ---------------------------

_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton pattern).

    Provider is configured entirely via env / .env (see ADR-0001). Do NOT hard-code
    a base URL here — it would override the environment.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)"""
    global _settings
    _settings = None
