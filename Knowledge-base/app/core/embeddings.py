"""Embedding configuration helpers (KB-6.2).

Pure helpers so the model choice is configurable via env and unit-testable
without downloading any model or importing torch.
"""
from __future__ import annotations

from typing import Any, Dict

from app.core.config import Settings

#: Giá trị "để model tự quyết" — không truyền `torch_dtype` xuống sentence-transformers.
_NO_DTYPE_OVERRIDE = {"", "default", "auto", "none"}


def build_embedding_params(settings: Settings) -> Dict[str, Any]:
    """Build kwargs for langchain's HuggingFaceEmbeddings.

    - model from `settings.embedding_model` (env `EMBEDDING_MODEL`)
    - runs on local CPU
    - normalizes vectors (cosine similarity), recommended for Qwen3-Embedding
    - **`torch_dtype`** from `EMBEDDING_TORCH_DTYPE` (TD-14): CPU **không** có kernel bf16 nhanh ⇒ ép
      `float32` nhanh hơn ~4,3× khi embed. `torch_dtype` phải nằm trong `model_kwargs` **lồng trong**
      `model_kwargs` của LangChain vì nó được truyền tiếp cho `SentenceTransformer(model_kwargs=...)`.
    - **`batch_size`** from `EMBEDDING_BATCH_SIZE` (đã có trong config nhưng trước đây không được dùng).
    """
    dtype = str(getattr(settings, "embedding_torch_dtype", "float32") or "").strip().lower()
    model_kwargs: Dict[str, Any] = {"device": "cpu"}
    if dtype not in _NO_DTYPE_OVERRIDE:
        model_kwargs["model_kwargs"] = {"torch_dtype": dtype}

    raw_batch = getattr(settings, "embedding_batch_size", 64)
    batch_size = int(raw_batch) if raw_batch is not None else 64
    return {
        "model_name": settings.embedding_model,
        "model_kwargs": model_kwargs,
        "encode_kwargs": {"normalize_embeddings": True, "batch_size": max(1, batch_size)},
    }


