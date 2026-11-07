"""Integration test cho KB-1.2: hook redaction trong DocumentService._add_documents_to_db.

Dùng fake collection/embeddings để KHÔNG cần tải model hay ChromaDB thật.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from langchain_core.documents import Document

from app.services.document_service import DocumentService
from app.services.pii_service import PIIRedactor


class FakeCollection:
    def __init__(self):
        self.added = []

    def add(self, embeddings, documents, metadatas, ids):
        self.added.append({"embeddings": embeddings, "documents": documents,
                           "metadatas": metadatas, "ids": ids})


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[0.0, 0.0, 0.0] for _ in texts]


def make_service(redact_ingest: bool) -> DocumentService:
    svc = object.__new__(DocumentService)  # bỏ qua __init__ nặng
    svc.settings = SimpleNamespace(
        pii_redact_ingest=redact_ingest,
        embedding_batch_size=8,
        enable_bm25=False,
    )
    svc.pii = PIIRedactor(SimpleNamespace(enable_pii_redaction=True,
                                         pii_placeholder="[REDACTED:{type}]"))
    svc.collection = FakeCollection()
    svc.embeddings = FakeEmbeddings()
    svc.executor = ThreadPoolExecutor(max_workers=1)
    svc._corpus_ids = []
    svc._corpus_texts = []
    svc._corpus_metas = []
    return svc


def test_add_documents_redacts_pii_when_enabled():
    svc = make_service(redact_ingest=True)
    docs = [Document(page_content="email john.doe@gmail.com now", metadata={"source": "a.md"})]

    asyncio.run(svc._add_documents_to_db(docs))

    stored = svc.collection.added[0]
    assert "john.doe@gmail.com" not in stored["documents"][0]
    assert "[REDACTED:EMAIL]" in stored["documents"][0]
    assert stored["metadatas"][0].get("pii_redacted") is True


def test_add_documents_keeps_pii_when_disabled():
    svc = make_service(redact_ingest=False)
    docs = [Document(page_content="email john.doe@gmail.com now", metadata={"source": "a.md"})]

    asyncio.run(svc._add_documents_to_db(docs))

    stored = svc.collection.added[0]
    assert "john.doe@gmail.com" in stored["documents"][0]
    assert "pii_redacted" not in stored["metadatas"][0]
