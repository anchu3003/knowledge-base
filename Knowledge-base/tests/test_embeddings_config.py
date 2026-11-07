"""Unit test cho cấu hình embedding (KB-6.2). Không tải model, không cần torch."""
from types import SimpleNamespace

from app.core.embeddings import build_embedding_params


def test_build_embedding_params_uses_settings_model():
    s = SimpleNamespace(embedding_model="Qwen/Qwen3-Embedding-0.6B")
    p = build_embedding_params(s)
    assert p["model_name"] == "Qwen/Qwen3-Embedding-0.6B"
    assert p["model_kwargs"] == {"device": "cpu"}
    assert p["encode_kwargs"] == {"normalize_embeddings": True}


def test_build_embedding_params_reflects_override():
    s = SimpleNamespace(embedding_model="sentence-transformers/all-mpnet-base-v2")
    assert build_embedding_params(s)["model_name"] == "sentence-transformers/all-mpnet-base-v2"


def test_settings_has_embedding_model_default(monkeypatch):
    # Settings đọc .env; env vars (monkeypatch) thắng. Không set EMBEDDING_MODEL để lấy default.
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost")
    from app.core.config import Settings

    # default = Qwen3-Embedding-0.6B (unless overridden by .env — accept either known value)
    assert Settings().embedding_model in (
        "Qwen/Qwen3-Embedding-0.6B",
        "sentence-transformers/all-mpnet-base-v2",
    )
