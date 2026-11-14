"""Test tầng `DocumentService`: cache rerank + invalidation (KB-5.3 — trả TD-15).

Không load model thật: `_cross_encoder` là fake đếm số lần `predict()` ⇒ đo được "có gọi rerank hay
không" thay vì chỉ đo thời gian (nhanh, ổn định).
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from app.services.document_service import DocumentService
from app.services.rerank_cache import RerankCache

DOCS = [
    ("id-1", "Kafka là message broker phân tán.", {"source": "Kafka.md"}, 0.1),
    ("id-2", "RabbitMQ là broker dùng queue.", {"source": "RabbitMQ.md"}, 0.2),
    ("id-3", "Kafka Streams xử lý dữ liệu luồng.", {"source": "Streams.md"}, 0.3),
]


class FakeCollection:
    def __init__(self, docs=DOCS):
        self.docs = docs

    def query(self, query_embeddings, n_results, include):
        return {
            "ids": [[doc[0] for doc in self.docs]],
            "documents": [[doc[1] for doc in self.docs]],
            "metadatas": [[doc[2] for doc in self.docs]],
            "distances": [[doc[3] for doc in self.docs]],
        }

    def count(self):
        return len(self.docs)

    def get(self, where=None, include=None, limit=None):
        return {"ids": [doc[0] for doc in self.docs]}


class FakeEmbeddings:
    def embed_query(self, text):
        return [0.0, 0.0, 0.0]

    def embed_documents(self, texts):
        return [[0.0, 0.0, 0.0] for _ in texts]


class CountingCrossEncoder:
    def __init__(self):
        self.calls = 0

    def predict(self, pairs):
        self.calls += 1
        # Điểm nghịch đảo thứ tự để thấy rerank thật sự chạy
        return [float(index) for index in range(len(pairs))]


def make_service(*, enable_cache: bool = True, rerank_top_n: int = 8) -> DocumentService:
    service = object.__new__(DocumentService)  # bỏ qua __init__ (nặng: Chroma + model)
    service.settings = SimpleNamespace(
        retrieval_k=3,
        hybrid_candidate_k=20,
        collection_name="documents",
        enable_hybrid=False,
        hybrid_alpha=0.5,
        enable_rerank=True,
        rerank_top_n=rerank_top_n,
        rerank_model="fake-reranker",
        similarity_threshold=0.0,
        enable_bm25=False,
        dedup_enabled=False,
        dedup_jaccard_threshold=0.8,
        max_chunks_per_file=10,
    )
    service.collection = FakeCollection()
    service.embeddings = FakeEmbeddings()
    service.executor = ThreadPoolExecutor(max_workers=1)
    service._corpus_ids = []
    service._corpus_texts = []
    service._corpus_metas = []
    service._bm25 = None
    service._cross_encoder = CountingCrossEncoder()
    service._index_version = 0
    service._config_fingerprint = "test"
    service._rerank_cache = RerankCache() if enable_cache else None
    return service


def search(service: DocumentService, query: str, k: int = None):
    return asyncio.run(service.search_similar_documents(query=query, k=k))


def test_second_identical_query_skips_rerank():
    service = make_service()

    first = search(service, "Kafka là gì?")
    second = search(service, "Kafka là gì?")

    assert service._cross_encoder.calls == 1          # chỉ chấm 1 lần
    assert [hit["chunk_id"] for hit in first] == [hit["chunk_id"] for hit in second]
    assert [hit["score"] for hit in first] == [hit["score"] for hit in second]
    assert service._rerank_cache.stats()["hits"] == 1


def test_whitespace_and_case_variants_hit_same_entry():
    service = make_service()

    search(service, "Kafka  LÀ gì?")
    search(service, " kafka là gì? ")

    assert service._cross_encoder.calls == 1


def test_different_query_is_not_cached():
    service = make_service()

    search(service, "Kafka là gì?")
    search(service, "RabbitMQ là gì?")

    assert service._cross_encoder.calls == 2


def test_index_change_invalidates_cache():
    """Sync/ingest/clear ⇒ `_mark_index_changed()` ⇒ câu cũ phải rerank lại (dữ liệu đã khác)."""
    service = make_service()
    search(service, "Kafka là gì?")

    service._mark_index_changed()
    search(service, "Kafka là gì?")

    assert service._cross_encoder.calls == 2
    assert service._index_version == 1
    assert service._rerank_cache.stats()["size"] == 1  # entry cũ đã bị clear, chỉ còn entry mới


def test_cache_disabled_always_reranks():
    service = make_service(enable_cache=False)

    search(service, "Kafka là gì?")
    search(service, "Kafka là gì?")

    assert service._cross_encoder.calls == 2


def test_top_n_changes_cache_key():
    """Đổi `rerank_top_n` ⇒ tập ứng viên khác ⇒ không được dùng lại điểm cũ."""
    service = make_service(rerank_top_n=2)
    search(service, "Kafka là gì?")

    service.settings.rerank_top_n = 3
    search(service, "Kafka là gì?")

    assert service._cross_encoder.calls == 2


def test_zero_scores_are_not_cached():
    """Encoder lỗi (toàn 0.0) không được làm bẩn cache — lần sau vẫn phải thử lại."""

    class BrokenEncoder:
        def __init__(self):
            self.calls = 0

        def predict(self, pairs):
            self.calls += 1
            return [0.0] * len(pairs)

    service = make_service()
    broken = BrokenEncoder()
    service._cross_encoder = broken

    search(service, "Kafka là gì?")
    search(service, "Kafka là gì?")

    assert broken.calls == 2
    assert service._rerank_cache.stats()["size"] == 0


def test_status_reports_index_version_and_cache_stats():
    service = make_service()
    search(service, "Kafka là gì?")
    search(service, "Kafka là gì?")

    status = asyncio.run(service.get_status())

    assert status["index_version"] == 0
    assert status["rerank_cache"]["hits"] == 1
    assert status["rerank_cache"]["size"] == 1
