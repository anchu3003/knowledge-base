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
    openai_base_url: str | None = Field(..., alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-3.5-turbo", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-ada-002", alias="OPENAI_EMBEDDING_MODEL")
    openai_api_type: str = Field(default="openai", alias="OPENAI_API_TYPE")
    openai_api_version: str = Field(default="2023-05-15", alias="OPENAI_API_VERSION")

    # ChromaDB Settings
    chroma_db_path: str = Field(default="./chroma_db", alias="CHROMA_DB_PATH")
    collection_name: str = Field(default="documents", alias="COLLECTION_NAME")

    # Document Processing Settings
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")

    # Supported file types
    supported_extensions: List[str] = Field(
        default=[".py", ".md", ".txt", ".json", ".yml", ".docx", ".pdf"],
        alias="SUPPORTED_EXTENSIONS"
    )

    # Document folder settings
    documents_folder: str = Field(default="./documents", alias="DOCUMENTS_FOLDER")
    auto_load_on_startup: bool = Field(default=True, alias="AUTO_LOAD_ON_STARTUP")

    # RAG Settings
    retrieval_k: int = Field(default=5, alias="RETRIEVAL_K")
    similarity_threshold: float = Field(default=0.7, alias="SIMILARITY_THRESHOLD")

    # Chat Settings
    default_temperature: float = Field(default=0.7, alias="DEFAULT_TEMPERATURE")
    default_max_tokens: int = Field(default=1000, alias="DEFAULT_MAX_TOKENS")
    max_conversation_length: int = Field(default=10, alias="MAX_CONVERSATION_LENGTH")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", env_file_encoding="utf-8")


# ---------------------------
# Singleton pattern helpers
# ---------------------------

_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton pattern)"""
    global _settings
    if _settings is None:
        _settings = Settings(OPENAI_BASE_URL="")
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)"""
    global _settings
    _settings = None
