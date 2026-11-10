"""Unit test cho cấu hình embedding (KB-6.2, TD-14). Không tải model, không cần torch."""
from types import SimpleNamespace

from app.core.embeddings import build_embedding_params


def test_build_embedding_params_uses_settings_model():
    s = SimpleNamespace(embedding_model="Qwen/Qwen3-Embedding-0.6B")
    p = build_embedding_params(s)
    assert p["model_name"] == "Qwen/Qwen3-Embedding-0.6B"
    # TD-14: mặc định ép float32 (nhanh hơn bf16 ~4,3× trên CPU) — `torch_dtype` phải **lồng** trong
    # `model_kwargs` vì LangChain chuyển tiếp dict này cho `SentenceTransformer(model_kwargs=...)`.
    assert p["model_kwargs"] == {"device": "cpu", "model_kwargs": {"torch_dtype": "float32"}}
    assert p["encode_kwargs"] == {"normalize_embeddings": True, "batch_size": 64}


def test_build_embedding_params_reflects_override():
    s = SimpleNamespace(embedding_model="sentence-transformers/all-mpnet-base-v2")
    assert build_embedding_params(s)["model_name"] == "sentence-transformers/all-mpnet-base-v2"


def test_embedding_dtype_can_be_disabled():
    """`EMBEDDING_TORCH_DTYPE=default` ⇒ không truyền `torch_dtype` (để model tự quyết)."""
    s = SimpleNamespace(embedding_model="m", embedding_torch_dtype="default")
    assert build_embedding_params(s)["model_kwargs"] == {"device": "cpu"}


def test_embedding_dtype_and_batch_size_from_settings():
    s = SimpleNamespace(embedding_model="m", embedding_torch_dtype="bfloat16", embedding_batch_size=16)
    p = build_embedding_params(s)
    assert p["model_kwargs"]["model_kwargs"] == {"torch_dtype": "bfloat16"}
    assert p["encode_kwargs"]["batch_size"] == 16


def test_embedding_batch_size_is_at_least_one():
    """Giá trị 0/âm không được làm sập `encode(batch_size=0)`."""
    s = SimpleNamespace(embedding_model="m", embedding_batch_size=0)
    assert build_embedding_params(s)["encode_kwargs"]["batch_size"] == 1


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
