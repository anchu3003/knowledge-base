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

    # Hybrid Retrieval and Re-ranking
    enable_bm25: bool = Field(default=True, alias="ENABLE_BM25")
    enable_hybrid: bool = Field(default=True, alias="ENABLE_HYBRID")
    hybrid_alpha: float = Field(default=0.5, alias="HYBRID_ALPHA")  # weight for dense vs. sparse
    hybrid_candidate_k: int = Field(default=20, alias="HYBRID_CANDIDATE_K")
    enable_rerank: bool = Field(default=True, alias="ENABLE_RERANK")
    rerank_top_n: int = Field(default=20, alias="RERANK_TOP_N")
    rerank_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANK_MODEL")

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
