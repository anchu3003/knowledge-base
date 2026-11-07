"""Embedding configuration helpers (KB-6.2).

Pure helpers so the model choice is configurable via env and unit-testable
without downloading any model or importing torch.
"""
from __future__ import annotations

from typing import Any, Dict

from app.core.config import Settings


def build_embedding_params(settings: Settings) -> Dict[str, Any]:
    """Build kwargs for langchain's HuggingFaceEmbeddings.

    - model from `settings.embedding_model` (env `EMBEDDING_MODEL`)
    - runs on local CPU
    - normalizes vectors (cosine similarity), recommended for Qwen3-Embedding
    """
    return {
        "model_name": settings.embedding_model,
        "model_kwargs": {"device": "cpu"},
        "encode_kwargs": {"normalize_embeddings": True},
    }
