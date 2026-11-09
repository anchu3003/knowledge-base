"""Cache kết quả rerank trong RAM (KB-5.3 — giảm latency, trả TD-15).

Vì sao cần: cross-encoder `bge-reranker-v2-m3` chạy CPU tốn **~8–13 s/query**; khi ôn tập bạn hay hỏi
lại **đúng câu cũ** ⇒ lần 2 không cần chấm lại.

Vì sao in-process (không Redis): 1 người dùng, 1 process uvicorn (AGENTS.md §3.4 — không thêm hạ tầng).
Mất khi restart là chấp nhận được vì đây chỉ là cache, không phải nguồn sự thật.

Khoá cache = `index_version + k + top_n + config fingerprint + query đã normalize`:
- **`index_version`** tăng mỗi khi index đổi (`ingest`/`delete`/`clear`/`sync`) ⇒ sync tài liệu xong là
  cache cũ tự vô hiệu, **không** cần hook xoá thủ công ở từng chỗ.
- `k`/`top_n`/config: cùng câu hỏi nhưng khác tham số ⇒ kết quả khác, phải là phần của khoá.
- Query normalize (strip + gộp whitespace) ⇒ "Kafka  là gì?" và "Kafka là gì?" dùng chung entry.

TTL (mặc định 1h) chặn trường hợp kết quả cũ ám quá lâu khi index không đổi nhưng ta muốn đo lại.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional

#: Số entry tối đa (mỗi entry ~ vài chục float ⇒ không đáng kể bộ nhớ).
DEFAULT_MAX_ENTRIES = 256
#: Thời gian sống mặc định của 1 entry.
DEFAULT_TTL_SECONDS = 3600


def normalize_query(query: str) -> str:
    """Chuẩn hoá câu hỏi trước khi băm (khác whitespace/hoa-thường không tạo entry mới)."""
    return " ".join((query or "").split()).lower()


def make_cache_key(
    *,
    query: str,
    index_version: int,
    k: int,
    top_n: int,
    config_fingerprint: str = "",
) -> str:
    """Băm mọi thứ ảnh hưởng tới tập ứng viên được rerank."""
    raw = f"{index_version}|{k}|{top_n}|{config_fingerprint}|{normalize_query(query)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class RerankCache:
    """LRU + TTL cache cho điểm rerank (thread-safe: rerank chạy trong executor)."""

    def __init__(
        self,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_entries = max(1, int(max_entries))
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self._clock = clock
        self._entries: "OrderedDict[str, tuple[float, List[float]]]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    # ------------------------------------------------------------------ API

    def get(self, key: str) -> Optional[List[float]]:
        """Trả điểm đã cache, `None` nếu miss hoặc hết hạn."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None

            stored_at, scores = entry
            if self.ttl_seconds and (self._clock() - stored_at) > self.ttl_seconds:
                # Hết hạn ⇒ xoá luôn, không giữ rác
                self._entries.pop(key, None)
                self.misses += 1
                return None

            # LRU: entry vừa dùng chuyển về cuối
            self._entries.move_to_end(key)
            self.hits += 1
            return list(scores)

    def set(self, key: str, scores: List[float]) -> None:
        with self._lock:
            self._entries[key] = (self._clock(), list(scores))
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
                self.evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._entries),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
            }
