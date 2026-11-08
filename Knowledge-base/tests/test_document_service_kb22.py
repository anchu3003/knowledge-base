"""Test KB-2.2 ở tầng DocumentService: chunk ID ổn định, upsert idempotent, hậu xử lý hits.

Dùng fake collection/embeddings ⇒ không cần tải model hay ChromaDB thật.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from langchain_core.documents import Document

from app.services.document_service import DocumentService

SAGA_CHUNK = (
    "The Saga Pattern manages distributed transactions in microservices using "
    "compensatable transactions and event driven coordination for eventual consistency."
)
SAGA_NEAR_DUP = SAGA_CHUNK + " Extra trailing sentence about rollback."


class FakeCollection:
    """Ghi lại upsert theo id để test tính idempotent (upsert thay vì add)."""

    def __init__(self):
        self.store = {}

    def upsert(self, embeddings, documents, metadatas, ids):
        for index, chunk_id in enumerate(ids):
            self.store[chunk_id] = {"document": documents[index], "metadata": metadatas[index]}

    def count(self):
        return len(self.store)


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[0.0, 0.0, 0.0] for _ in texts]


def make_service(dedup_enabled: bool = True, max_chunks_per_file: int = 2) -> DocumentService:
    service = object.__new__(DocumentService)  # bỏ qua __init__ nặng
    service.settings = SimpleNamespace(
        pii_redact_ingest=False,
        embedding_batch_size=8,
        enable_bm25=False,
        dedup_enabled=dedup_enabled,
        dedup_jaccard_threshold=0.8,
        max_chunks_per_file=max_chunks_per_file,
    )
    service.collection = FakeCollection()
    service.embeddings = FakeEmbeddings()
    service.executor = ThreadPoolExecutor(max_workers=1)
    service._corpus_ids = []
    service._corpus_texts = []
    service._corpus_metas = []
    service._bm25 = None
    return service


def make_docs() -> list:
    return [
        Document(page_content="alpha chunk about caching", metadata={"source": "a.md", "chunk_index": 0}),
        Document(page_content="beta chunk about queues", metadata={"source": "a.md", "chunk_index": 1}),
    ]


def hit(content: str, source: str, score: float = 0.9) -> dict:
    return {"chunk_id": content[:4], "content": content, "metadata": {"source": source}, "score": score}


# -----------------------------
# Ingest: chunk ID + upsert
# -----------------------------
def test_make_chunk_id_is_deterministic_and_content_addressed():
    stable = DocumentService._make_chunk_id("a.md", 0, "text")
    assert stable == DocumentService._make_chunk_id("a.md", 0, "text")
    assert stable != DocumentService._make_chunk_id("a.md", 1, "text")
    assert stable != DocumentService._make_chunk_id("a.md", 0, "text changed")
    assert len(stable) == 16


def test_ingest_twice_does_not_duplicate_and_stores_chunk_id():
    service = make_service()

    asyncio.run(service._add_documents_to_db(make_docs()))
    first_ids = set(service.collection.store.keys())
    asyncio.run(service._add_documents_to_db(make_docs()))

    assert set(service.collection.store.keys()) == first_ids  # ID ổn định ⇒ upsert, không nhân đôi
    assert service.collection.count() == 2
    for chunk_id, record in service.collection.store.items():
        assert record["metadata"]["chunk_id"] == chunk_id


# -----------------------------
# Hậu xử lý hits
# -----------------------------
def test_postprocess_dedupes_and_caps_per_file():
    service = make_service()
    hits = [
        hit(SAGA_CHUNK, "saga.md", 0.9),
        hit(SAGA_CHUNK.upper(), "saga.md", 0.8),  # trùng sau normalize ⇒ bị bỏ
        hit("Distinct chunk about docker containers", "saga.md", 0.7),
        hit("Distinct chunk about react hooks", "saga.md", 0.6),
        hit("Unrelated chunk about SQL indexes", "index.md", 0.5),
    ]

    kept = service._postprocess_hits(hits)

    assert len(kept) == 3  # 1 chunk trùng bị bỏ + tối đa 2 chunk/file
    assert kept[0]["content"] == SAGA_CHUNK
    assert [h["metadata"]["source"] for h in kept] == ["saga.md", "saga.md", "index.md"]


def test_postprocess_can_disable_dedup_but_still_caps():
    service = make_service(dedup_enabled=False, max_chunks_per_file=2)
    hits = [hit("chunk a", "saga.md"), hit("chunk b", "saga.md"), hit("chunk c", "saga.md")]

    kept = service._postprocess_hits(hits)

    assert len(kept) == 2


def test_postprocess_with_cap_zero_keeps_all():
    service = make_service(max_chunks_per_file=0)
    hits = [hit("chunk a", "x.md"), hit("chunk b", "x.md"), hit("chunk c", "x.md")]

    assert len(service._postprocess_hits(hits)) == 3
