"""Chunk dedup + giới hạn chunk/file cho kết quả retrieval (KB-2.2).

Module **thuần** (không import torch/Chroma) để test không cần model.

Vì sao cần: `CHUNK_OVERLAP=200` với `CHUNK_SIZE=1000` làm 2 chunk liền nhau chia sẻ ~20% nội dung,
và trong KB cá nhân vài file lớn ("hub") chiếm hết top-k. Baseline KB-2.1 cho thấy
`distinct_file_ratio = 0.707` (≈1.5 hit lặp file/câu), cá biệt 5/5 hit cùng 1 file.

Hai lớp lọc:
1. `dedupe_hits` — bỏ chunk gần trùng nội dung (Jaccard shingle 3-gram ≥ ngưỡng).
2. `cap_per_file` — tối đa N chunk / 1 file, để top-k phủ nhiều tài liệu hơn.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

DEFAULT_JACCARD_THRESHOLD = 0.8
SHINGLE_SIZE = 3

_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase + gộp mọi khoảng trắng thành 1 space (để so khớp không phụ thuộc format)."""
    return _WS_RE.sub(" ", (text or "").lower()).strip()


def shingles(text: str, size: int = SHINGLE_SIZE) -> set:
    """Tập shingle word-level của text đã normalize."""
    tokens = normalize_text(text).split()
    if not tokens:
        return set()
    if len(tokens) < size:
        return {" ".join(tokens)}
    return {" ".join(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity; 0.0 nếu một trong hai rỗng."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def dedupe_hits(hits: Sequence[Dict[str, Any]], threshold: float = DEFAULT_JACCARD_THRESHOLD) -> List[Dict[str, Any]]:
    """Bỏ các hit gần trùng nội dung, **giữ hit xuất hiện trước** (hits đã sort theo score giảm dần)."""
    kept: List[Dict[str, Any]] = []
    kept_shingles: List[set] = []
    for hit in hits:
        current = shingles(hit.get("content", ""))
        if any(jaccard(current, existing) >= threshold for existing in kept_shingles):
            continue
        kept.append(hit)
        kept_shingles.append(current)
    return kept


def cap_per_file(hits: Sequence[Dict[str, Any]], max_per_file: int) -> List[Dict[str, Any]]:
    """Giới hạn số hit trên cùng 1 file (`metadata["source"]`); `max_per_file <= 0` = tắt."""
    if max_per_file <= 0:
        return list(hits)

    kept: List[Dict[str, Any]] = []
    per_file: Dict[str, int] = {}
    for hit in hits:
        source = str((hit.get("metadata") or {}).get("source", ""))
        count = per_file.get(source, 0)
        if count >= max_per_file:
            continue
        per_file[source] = count + 1
        kept.append(hit)
    return kept
