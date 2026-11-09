"""Test `ChatService._initial_retrieval` — multi-query (KB-5.4).

Fake `DocumentService` đếm query nhận vào ⇒ biết chắc có multi-query hay không, không cần model.
"""

import asyncio
from types import SimpleNamespace

from app.services.chat_service import ChatService


def hit(chunk_id: str, score: float) -> dict:
    return {"chunk_id": chunk_id, "content": f"nội dung {chunk_id}", "metadata": {}, "score": score}


class RecordingDocumentService:
    """Trả hit khác nhau theo query; ghi lại query đã nhận + `rerank_top_n` override."""

    def __init__(self, results=None, error_for=None):
        self.calls = []
        self.results = results or {}
        self.error_for = error_for or set()

    async def search_similar_documents(self, query, k=None, rerank_top_n=None):
        self.calls.append({"query": query, "k": k, "rerank_top_n": rerank_top_n})
        if query in self.error_for:
            raise RuntimeError("retrieval down")
        return self.results.get(query, [hit(f"{query[:6]}", 0.5)])


def make_service(*, enabled=True, max_parts=3, doc_service=None) -> ChatService:
    service = object.__new__(ChatService)  # bỏ qua __init__ (LLM client thật)
    service.settings = SimpleNamespace(
        retrieval_k=3,
        rerank_top_n=8,
        multi_query_enabled=enabled,
        multi_query_max_parts=max_parts,
    )
    service.document_service = doc_service or RecordingDocumentService()
    return service


def call(service: ChatService, query: str):
    return asyncio.run(service._initial_retrieval(query))


def test_flag_off_uses_single_query():
    docs = RecordingDocumentService()
    service = make_service(enabled=False, doc_service=docs)

    hits, parts = call(service, "Kafka là gì và RabbitMQ khác gì?")

    assert parts == []
    assert len(docs.calls) == 1
    assert docs.calls[0]["query"] == "Kafka là gì và RabbitMQ khác gì?"
    assert docs.calls[0]["rerank_top_n"] is None  # dùng default, không giảm top-N
    assert hits


def test_single_intent_behaves_like_before():
    docs = RecordingDocumentService()
    service = make_service(doc_service=docs)

    _, parts = call(service, "Saga pattern là gì?")

    assert parts == []
    assert len(docs.calls) == 1


def test_multi_intent_retrieves_each_part_in_parallel():
    docs = RecordingDocumentService(results={
        "Kafka là gì": [hit("kafka-1", 0.9)],
        "RabbitMQ khác gì": [hit("rabbit-1", 0.95), hit("kafka-1", 0.5)],
    })
    service = make_service(doc_service=docs)

    hits, parts = call(service, "Kafka là gì và RabbitMQ khác gì?")

    assert len(parts) == 2
    assert [c["query"] for c in docs.calls] == parts
    # Mỗi phần chỉ chấm nửa top-N để latency không nhân N
    assert all(c["rerank_top_n"] == 4 for c in docs.calls)
    # Gộp: giữ điểm cao nhất cho chunk trùng (kafka-1: 0.9 > 0.5), sort giảm dần
    assert [item["chunk_id"] for item in hits] == ["rabbit-1", "kafka-1"]
    assert hits[1]["score"] == 0.9


def test_caps_merged_result_at_retrieval_k():
    docs = RecordingDocumentService(results={
        "A là gì": [hit("a1", 0.9), hit("a2", 0.8)],
        "B là gì": [hit("b1", 0.7), hit("b2", 0.6)],
    })
    service = make_service(doc_service=docs)

    hits, _ = call(service, "A là gì và B là gì?")

    assert len(hits) == service.settings.retrieval_k == 3


def test_falls_back_to_single_query_when_all_parts_fail():
    query = "A là gì và B là gì?"
    docs = RecordingDocumentService(error_for={"A là gì", "B là gì"})
    service = make_service(doc_service=docs)

    hits, parts = call(service, query)

    # 2 lần cho 2 phần (lỗi) + 1 lần fallback nguyên câu
    assert len(docs.calls) == 3
    assert docs.calls[-1]["query"] == query
    assert parts == []
    assert hits


def test_partial_failure_still_merges_successful_parts():
    docs = RecordingDocumentService(error_for={"B là gì"})
    service = make_service(doc_service=docs)

    hits, parts = call(service, "A là gì và B là gì?")

    assert len(parts) == 2
    assert hits  # dùng phần A, không fallback


def test_max_parts_respected():
    docs = RecordingDocumentService()
    service = make_service(max_parts=2, doc_service=docs)

    _, parts = call(service, "A là gì và B là gì và C là gì?")

    assert len(parts) == 2
    assert len(docs.calls) == 2


def test_retrieve_returns_hits_only():
    service = make_service()

    hits = asyncio.run(service.retrieve("Kafka là gì?"))

    assert hits and "chunk_id" in hits[0]
