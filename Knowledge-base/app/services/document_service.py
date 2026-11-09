import asyncio
import hashlib
import time
import importlib
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Any as TypingAny, Mapping

import chromadb
from chromadb import SparseVector
from chromadb.config import Settings as ChromaSettings
from langchain_community.document_loaders import (
    TextLoader,
    JSONLoader,
    UnstructuredWordDocumentLoader,
    PyPDFLoader,
)
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.core.config import Settings
from app.core.errors import DocumentsFolderEmptyError
from app.core.embeddings import build_embedding_params
from app.services.dedup import cap_per_file, dedupe_hits
from app.services.index_sync import (
    IndexedFile,
    SyncPlan,
    compute_file_digest,
    diff_indexed,
    scan_folder,
)
from app.services.pii_service import PIIRedactor, redact_texts_for_ingest
from app.services.rerank_cache import RerankCache, make_cache_key

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for handling document processing and vector storage"""

    #: Default an toàn khi test dựng service bằng `object.__new__(DocumentService)` (không qua
    #: `__init__`) — cùng bài học KB-5.2: attribute mới thêm vào service **phải** có class default,
    #: nếu không test cũ vỡ bằng `AttributeError` (xem TD-27).
    _index_version: int = 0
    _rerank_cache: Optional[RerankCache] = None
    _config_fingerprint: str = ""

    def __init__(self, settings: Settings):
        self.settings = settings

        # PII/secret redaction for ingestion (optional, gated by PII_REDACT_INGEST)
        # See .clinerules/30-pii-safety.md
        self.pii = PIIRedactor(settings)

        # Initialize embeddings (local sentence-transformers; model from env — KB-6.2)
        self.embeddings = HuggingFaceEmbeddings(**build_embedding_params(settings))

        self.chroma_client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # Get or create a collection
        try:
            self.collection = self.chroma_client.get_collection(settings.collection_name)
        except Exception:
            self.collection = self.chroma_client.create_collection(
                name=settings.collection_name,
                metadata={"description": "RAG documents collection"}
            )

        # Normalize supported extensions (lowercase, leading dot)
        self._supported_exts = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in (self.settings.supported_extensions or [])
        ]

        # Default text splitter (used for plain text/json/docx/pdf unless overridden per type)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )

        # Thread pool for file processing
        self.executor = ThreadPoolExecutor(max_workers=4)

        # In-memory corpus for sparse retrieval and re-ranking
        self._corpus_ids: List[str] = []
        self._corpus_texts: List[str] = []
        self._corpus_metas: List[Dict[str, Any]] = []
        self._bm25: Optional[TypingAny] = None
        self._cross_encoder: Optional[TypingAny] = None

        # KB-5.3: cache điểm rerank trong RAM (query + index_version + tham số) ⇒ hỏi lại câu cũ
        # không phải chấm lại 8–13 s. Tắt bằng `RERANK_CACHE_ENABLED=false` (dùng khi đo eval).
        self._index_version: int = 0
        self._rerank_cache: Optional[RerankCache] = None
        if self.settings.rerank_cache_enabled:
            self._rerank_cache = RerankCache(
                max_entries=self.settings.rerank_cache_max_entries,
                ttl_seconds=self.settings.rerank_cache_ttl_seconds,
            )
        # Mọi tham số ảnh hưởng tập ứng viên/time rerank ⇒ phải nằm trong khoá cache: đổi config
        # (restart với env khác) là entry cũ không dùng lại được nữa.
        self._config_fingerprint = (
            f"h={int(self.settings.enable_hybrid)}:a={self.settings.hybrid_alpha}:"
            f"d={int(self.settings.dedup_enabled)}:{self.settings.dedup_jaccard_threshold}:"
            f"cap={self.settings.max_chunks_per_file}:m={self.settings.rerank_model}:"
            f"thr={self.settings.similarity_threshold}:ck={self.settings.hybrid_candidate_k}"
        )

        # Attempt to bootstrap BM25 from existing Chroma collection
        try:
            if self.settings.enable_bm25:
                existing_count = self.collection.count()
                if existing_count > 0:
                    existing = self.collection.get(
                        limit=existing_count,
                        include=["documents", "metadatas"],
                    )
                    self._corpus_ids = existing.get("ids", []) or []
                    self._corpus_texts = existing.get("documents", []) or []
                    self._corpus_metas = existing.get("metadatas", []) or []
                    self._rebuild_bm25()
        except Exception as e:
            logger.warning(f"Failed to bootstrap BM25 from existing collection: {e}")

    async def auto_load_documents(self) -> Dict[str, Any]:
        """Autoload documents from the default documents folder"""
        documents_folder = Path(self.settings.documents_folder)

        if not documents_folder.exists():
            logger.warning(f"Documents folder does not exist: {documents_folder}")
            return {
                "processed_files": 0,
                "total_chunks": 0,
                "details": [f"Documents folder not found: {documents_folder}"]
            }

        # Default file patterns for supported extensions
        file_patterns = [f"*{ext}" for ext in self._supported_exts]
        logger.info(f"Auto-loading documents from: {documents_folder}")

        result = await self.process_documents(str(documents_folder), file_patterns)

        if result["processed_files"] > 0:
            logger.info(f"Auto-loaded {result['processed_files']} files, {result['total_chunks']} chunks")
        else:
            logger.warning("No documents were auto-loaded")

        return result

    async def process_documents(self, folder_path: str, file_patterns: List[str]) -> Dict[str, Any]:
        """Process documents from a folder and add them to the vector database"""
        folder = Path(folder_path)

        if not folder.exists():
            raise ValueError(f"Folder does not exist: {folder_path}")

        # Find matching files
        files_to_process = []
        for pattern in file_patterns:
            files_to_process.extend(folder.rglob(pattern))

        # Filter by supported extensions and file size
        valid_files = []
        for file_path in files_to_process:
            if file_path.is_file():
                if file_path.suffix.lower() in self._supported_exts:
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    if file_size_mb <= self.settings.max_file_size_mb:
                        valid_files.append(file_path)

        if not valid_files:
            return {
                "processed_files": 0,
                "total_chunks": 0,
                "details": ["No valid files found to process"]
            }

        # Process files concurrently
        tasks = [self._process_single_file(file_path) for file_path in valid_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_documents = []
        processed_count = 0
        error_details = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_details.append(f"Error processing {valid_files[i]}: {str(result)}")
            else:
                all_documents.extend(result)
                processed_count += 1

        # Add documents to the vector database
        if all_documents:
            await self._add_documents_to_db(all_documents)

        return {
            "processed_files": processed_count,
            "total_chunks": len(all_documents),
            "details": error_details if error_details else []
        }

    async def _process_single_file(self, file_path: Path) -> List[Document]:
        """Process a single file and return document chunks"""
        try:
            # Load document based on the file type
            loader = self.get_loader(file_path)

            loop = asyncio.get_event_loop()
            documents = await loop.run_in_executor(self.executor, lambda x: loader.load(), None)

            # Split documents into chunks (KB-2.4: .md tách theo heading rồi mới cắt theo size)
            chunks = self._split_documents(file_path, documents)

            # Add metadata. `chunk_index` phải đếm **theo file** (dùng cho chunk_id ổn định, KB-2.2).
            for idx, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "source": str(file_path),
                    "file_type": file_path.suffix,
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "chunk_index": idx,
                    # KB-5.1: sha256 nội dung ⇒ sync so được "file trên đĩa" với "file đã index"
                    "file_hash": compute_file_digest(file_path),
                })

            return chunks

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise

    def _split_documents(self, file_path: Path, documents: List[Document]) -> List[Document]:
        """Tách chunk theo loại file (KB-2.4).

        - `.md` → tách theo heading (giữ `heading_path`), rồi cắt mỗi section theo `CHUNK_SIZE`.
        - loại khác → splitter như cũ.
        """
        if file_path.suffix.lower() == ".md":
            return self._split_markdown(documents)
        return self.get_splitter(file_path).split_documents(documents)

    def _split_markdown(self, documents: List[Document]) -> List[Document]:
        """Markdown: tách theo heading H1–H3 rồi cắt mỗi section theo size (KB-2.4).

        `MarkdownHeaderTextSplitter` **không** giới hạn size ⇒ bắt buộc split lại bằng
        `RecursiveCharacterTextSplitter`, nếu không section dài (file 20KB) sẽ vượt budget context.
        """
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        )

        chunks: List[Document] = []
        for document in documents:
            for section in header_splitter.split_text(document.page_content):
                heading_path = " > ".join(
                    filter(None, [
                        section.metadata.get("h1"),
                        section.metadata.get("h2"),
                        section.metadata.get("h3"),
                    ])
                )
                section_doc = Document(
                    page_content=section.page_content,
                    metadata={**document.metadata, "heading_path": heading_path},
                )
                chunks.extend(self.text_splitter.split_documents([section_doc]))
        return chunks

    @staticmethod
    def get_loader(file_path: Path):
        """Get the appropriate document loader based on file extension"""
        extension = file_path.suffix.lower()

        if extension == ".md":
            return TextLoader(str(file_path), encoding="utf-8")
        elif extension == ".json":
            return JSONLoader(str(file_path), jq_schema=".")
        elif extension == ".docx":
            return UnstructuredWordDocumentLoader(str(file_path))
        elif extension == ".pdf":
            return PyPDFLoader(str(file_path))
        elif extension == ".txt":
            return TextLoader(str(file_path), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {extension}")

    def get_splitter(self, file_path: Path):
        """Pick the best text splitter based on the file type.

        `.md` KHÔNG dùng hàm này — markdown được tách theo heading trong `_split_markdown` (KB-2.4).
        """
        ext = file_path.suffix.lower()
        if ext in (".docx", ".pdf"):
            # Slightly conservative splitting works well for OCR/page artifacts
            return RecursiveCharacterTextSplitter(
                chunk_size=self.settings.chunk_size,
                chunk_overlap=self.settings.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
        else:
            # Default for .txt and .json
            return self.text_splitter

    @staticmethod
    def _make_chunk_id(source: str, chunk_index: int, text: str) -> str:
        """ID ổn định theo nội dung + vị trí (KB-2.2).

        Dùng sha1 thay vì `hash()` (bị randomize mỗi process → ingest lặp sinh bản trùng).
        """
        payload = f"{source}|{chunk_index}|{text}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    async def _add_documents_to_db(self, documents: List[Document]):
        """Add documents to ChromaDB vector database"""
        ids: List[str] = []
        if not documents:
            return

        # Extract texts and metadata
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # Optionally mask PII/secret before indexing (KB-1.2). Original files on disk
        # are never touched — only the copy stored in the vector store.
        if self.settings.pii_redact_ingest:
            texts, metadatas, redactions = redact_texts_for_ingest(self.pii, texts, metadatas)
            if redactions:
                logger.info(
                    f"Ingest PII redaction: masked {redactions} value(s) across {len(texts)} chunks."
                )

        # Stable, content-addressed IDs + `chunk_id` in metadata (KB-2.2). Re-ingesting the same
        # file produces the same IDs → `upsert` updates in place instead of duplicating.
        ids = [
            self._make_chunk_id(
                str(meta.get("source", "")),
                int(meta.get("chunk_index", index)),
                text,
            )
            for index, (text, meta) in enumerate(zip(texts, metadatas))
        ]
        for meta, chunk_id in zip(metadatas, ids):
            meta["chunk_id"] = chunk_id

        batch_size = max(1, self.settings.embedding_batch_size)
        total = len(texts)
        loop = asyncio.get_event_loop()

        added = 0
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_texts = texts[start:end]
            batch_metas = metadatas[start:end]
            batch_ids = ids[start:end]

            # Compute embeddings for this batch off the event loop
            embeddings = await loop.run_in_executor(
                self.executor,
                self.embeddings.embed_documents,
                batch_texts,
            )

            # Upsert (idempotent) batch to ChromaDB
            try:
                self.collection.upsert(
                    embeddings=embeddings,
                    documents=batch_texts,
                    metadatas=batch_metas,
                    ids=batch_ids,
                )
                added += len(batch_texts)
                logger.info(f"Upserted batch {start}-{end - 1} ({len(batch_texts)}) documents to ChromaDB collection.")
                # KB-5.3: nội dung index đổi ⇒ cache rerank cũ không còn đúng
                self._mark_index_changed()
            except Exception as e:
                logger.error(f"Error adding batch {start}-{end - 1} to ChromaDB: {e}")
                raise

        logger.info(f"Finished adding {added}/{total} documents to ChromaDB in batches of {batch_size}.")

        # Update in-memory corpus and BM25
        if self.settings.enable_bm25 and texts:
            self._corpus_ids.extend(ids)
            self._corpus_texts.extend(texts)
            self._corpus_metas.extend(metadatas)
            self._rebuild_bm25()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [t for t in (text.lower().split()) if t]

    def _rebuild_bm25(self) -> None:
        try:
            tokenized = [self._tokenize(t) for t in self._corpus_texts]
            if tokenized:
                bm25_module = importlib.import_module("rank_bm25")
                BM25Okapi = getattr(bm25_module, "BM25Okapi")
                self._bm25 = BM25Okapi(tokenized)
                logger.info(f"BM25 index built with {len(tokenized)} documents.")
        except Exception as e:
            logger.warning(f"Failed to build BM25 index: {e}")

    def _ensure_cross_encoder(self) -> None:
        if self._cross_encoder is None:
            try:
                st_module = importlib.import_module("sentence_transformers")
                CrossEncoder = getattr(st_module, "CrossEncoder")
                self._cross_encoder = CrossEncoder(self.settings.rerank_model)
                logger.info(f"CrossEncoder loaded: {self.settings.rerank_model}")
            except Exception as e:
                logger.warning(f"Failed to load CrossEncoder model {self.settings.rerank_model}: {e}")

    def _mark_index_changed(self) -> None:
        """Index vừa đổi (KB-5.3): tăng `index_version` + xoá cache rerank.

        Nhờ version nằm trong khoá cache, mọi entry cũ tự vô hiệu — kể cả khi quên gọi clear.
        """
        self._index_version += 1
        if self._rerank_cache is not None:
            self._rerank_cache.clear()

    def _postprocess_hits(self, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Hậu xử lý kết quả retrieval (KB-2.2): bỏ chunk gần trùng + giới hạn chunk/file.

        `hits` phải đã sort theo score giảm dần; hàm giữ hit đứng trước (score cao hơn).
        """
        if self.settings.dedup_enabled:
            hits = dedupe_hits(hits, self.settings.dedup_jaccard_threshold)
        return cap_per_file(hits, self.settings.max_chunks_per_file)

    async def search_similar_documents(
            self,
            query: str,
            k: int = None,
            rerank_top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using dense, sparse and optional re-ranking.

        `rerank_top_n` (KB-5.4): override số ứng viên đưa vào cross-encoder — dùng cho **multi-query**
        (mỗi phần chỉ cần chấm ít ứng viên hơn để không nhân latency lên gấp N).

        Returns list of dicts: {chunk_id, content, metadata, score, rank}
        (dedup + cap/file đã áp dụng — xem `_postprocess_hits`)
        """
        if k is None:
            k = self.settings.retrieval_k

        loop = asyncio.get_event_loop()

        # Dense retrieval from Chroma (candidate pool may be larger if hybrid/rerank enabled)
        dense_n = max(k,
                      self.settings.hybrid_candidate_k) if self.settings.enable_hybrid or self.settings.enable_rerank else k
        query_embedding = await loop.run_in_executor(self.executor, self.embeddings.embed_query, query)
        dense_results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=dense_n,
            include=["documents", "metadatas", "distances"],
        )

        dense_items: List[Tuple[str, str, Mapping[
            str, str | int | float | bool | SparseVector | None], float]] = []  # (id, doc, meta, score)
        if dense_results.get("documents") and dense_results["documents"][0]:
            for doc_id, doc, meta, dist in zip(
                    dense_results.get("ids", [[None]])[0],
                    dense_results["documents"][0],
                    dense_results["metadatas"][0],
                    dense_results["distances"][0],
            ):
                dense_items.append((doc_id, doc, meta, 1 - float(dist)))

        # Ngưỡng cosine tối thiểu cho dense candidates (0 = tắt). Chỉ dense được lọc:
        # score hybrid đã min-max normalize, còn rerank là logits cross-encoder — không cùng scale.
        if self.settings.similarity_threshold > 0:
            dense_items = [item for item in dense_items if item[3] >= self.settings.similarity_threshold]

        # Sparse retrieval via BM25
        sparse_scores: Dict[str, float] = {}
        if self.settings.enable_bm25 and self._bm25 is not None and self._corpus_ids:
            q_tokens = self._tokenize(query)
            bm25_scores = self._bm25.get_scores(q_tokens)
            # Keep the top candidate pool similar to dense_n for efficiency
            if bm25_scores is not None and len(bm25_scores) == len(self._corpus_ids):
                # Build mapping id -> score
                # Get top indices
                top_n = min(dense_n, len(bm25_scores))
                top_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:top_n]
                sparse_scores = {self._corpus_ids[i]: float(bm25_scores[i]) for i in top_idx}

        # If hybrid disabled, return dense-only top k
        if not self.settings.enable_hybrid and not self.settings.enable_rerank:
            dense_hits: List[Dict[str, Any]] = [
                {"chunk_id": doc_id, "content": doc, "metadata": dict(meta), "score": float(score)}
                for doc_id, doc, meta, score in dense_items
            ]
            dense_hits = self._postprocess_hits(dense_hits)
            return [{**hit, "rank": idx} for idx, hit in enumerate(dense_hits[:k], start=1)]

        # Normalize scores
        def normalize(scores: List[float]) -> List[float]:
            if not scores:
                return scores
            mx = max(scores)
            mn = min(scores)
            if mx == mn:
                return [1.0 for _ in scores]
            return [((s1 - mn) / (mx - mn)) for s1 in scores]

        dense_score_map: Dict[str, Tuple[str, Mapping[str, str | int | float | bool | SparseVector | None], float]] = {}
        dense_ids = []
        dense_vals = []
        for doc_id, doc, meta, score in dense_items:
            if doc_id is None:
                # Fallback: synthesize an id from content hash
                doc_id = f"hash_{abs(hash(doc[:100]))}"
            dense_ids.append(doc_id)
            dense_vals.append(score)
            dense_score_map[doc_id] = (doc, meta, score)

        dense_norm = dict(zip(dense_ids, normalize(dense_vals)))

        sparse_norm: Dict[str, float] = {}
        if sparse_scores:
            sparse_norm = dict(zip(sparse_scores.keys(), normalize(list(sparse_scores.values()))))

        alpha = self.settings.hybrid_alpha
        combined: Dict[str, float] = {}
        candidate_ids = set(dense_norm.keys()) | set(sparse_norm.keys())
        for cid in candidate_ids:
            d = dense_norm.get(cid)
            s = sparse_norm.get(cid)
            if d is not None and s is not None:
                combined[cid] = alpha * d + (1 - alpha) * s
            elif d is not None:
                combined[cid] = d if alpha > 0 else 0.0
            elif s is not None:
                combined[cid] = s if (1 - alpha) > 0 else 0.0

        # Build candidate hits (shape = kết quả cuối, để dedup/cap dùng chung 1 định dạng)
        candidates: List[Dict[str, Any]] = []
        for cid in candidate_ids:
            if cid in dense_score_map:
                doc, meta, _ = dense_score_map[cid]
            else:
                # Pull from corpus if exists
                try:
                    idx = self._corpus_ids.index(cid)
                    doc = self._corpus_texts[idx]
                    meta = self._corpus_metas[idx]
                except ValueError:
                    # Skip if metadata not found
                    continue
            candidates.append({
                "chunk_id": cid,
                "content": doc,
                "metadata": dict(meta),
                "score": float(combined.get(cid, 0.0)),
            })

        # Sort by combined score
        candidates.sort(key=lambda hit: hit["score"], reverse=True)

        # Dedup + cap/file TRƯỚC rerank: không để reranker chấm lại các chunk trùng nội dung
        candidates = self._postprocess_hits(candidates)

        # Optional cross-encoder re-ranking on top-N
        if self.settings.enable_rerank and candidates:
            effective_top_n = rerank_top_n if rerank_top_n is not None else self.settings.rerank_top_n
            top_n = min(max(1, effective_top_n), len(candidates))
            pairs = [(query, c["content"]) for c in candidates[:top_n]]

            # KB-5.3: tra cache trước — cùng câu hỏi + index chưa đổi ⇒ bỏ qua 8–13 s rerank.
            cache_key = None
            rerank_scores: Optional[List[float]] = None
            if self._rerank_cache is not None:
                cache_key = make_cache_key(
                    query=query,
                    index_version=self._index_version,
                    k=k,
                    top_n=top_n,
                    config_fingerprint=self._config_fingerprint,
                )
                rerank_scores = self._rerank_cache.get(cache_key)
                if rerank_scores is not None:
                    logger.debug("rerank cache hit (top_n=%d, index_version=%d)", top_n, self._index_version)

            # Run cross-encoder off the event loop
            def _score_pairs() -> List[float]:
                self._ensure_cross_encoder()
                if self._cross_encoder is None:
                    return [0.0] * len(pairs)
                return list(self._cross_encoder.predict(pairs))

            if rerank_scores is None:
                rerank_scores = await loop.run_in_executor(self.executor, lambda x: _score_pairs(), None)
                # Chỉ cache khi có kết quả thật (encoder lỗi ⇒ toàn 0.0, không nên giữ lại)
                if cache_key is not None and rerank_scores and any(score != 0.0 for score in rerank_scores):
                    self._rerank_cache.set(cache_key, rerank_scores)

            reranked = list(zip(candidates[:top_n], rerank_scores))
            reranked.sort(key=lambda item: item[1], reverse=True)
            candidates = [{**hit, "score": float(score)} for hit, score in reranked] + candidates[top_n:]
            # Rerank đổi thứ tự ⇒ chạy lại dedup/cap để giữ bất biến của top-k
            candidates = self._postprocess_hits(candidates)

        # Prepare final results top-k
        return [{**hit, "rank": idx} for idx, hit in enumerate(candidates[:k], start=1)]

    async def get_status(self) -> Dict[str, Any]:
        """Get the status of the document database"""
        try:
            count = self.collection.count()
            status: Dict[str, Any] = {
                "collection_name": self.settings.collection_name,
                "document_count": count,
                "status": "healthy" if count > 0 else "empty",
                # KB-5.3: `index_version` tăng mỗi lần index đổi; cache rerank keyed theo nó
                "index_version": self._index_version,
                "rerank_cache": self._rerank_cache.stats() if self._rerank_cache is not None else None,
            }
            return status
        except Exception as e:
            logger.error(f"Error getting database status: {e}")
            return {
                "collection_name": self.settings.collection_name,
                "document_count": 0,
                "status": "error",
                "error": str(e)
            }

    # ------------------------------
    # KB-5.1 — index tăng dần từ folder (file mới / sửa / xoá)
    # ------------------------------

    def indexed_files(self) -> Dict[str, IndexedFile]:
        """Đọc metadata collection ⇒ `{source: IndexedFile(digest, size)}`.

        Mọi chunk của một file chia sẻ cùng `file_hash`/`file_size` ⇒ chỉ lấy bản ghi đầu tiên.
        """
        files: Dict[str, IndexedFile] = {}
        try:
            found = self.collection.get(include=["metadatas"])
        except Exception as exc:  # pragma: no cover - Chroma lỗi
            logger.warning(f"indexed_files: cannot read collection: {exc}")
            return files

        for meta in found.get("metadatas") or []:
            if not isinstance(meta, dict):
                continue
            source = meta.get("source")
            if not source or source in files:
                continue
            digest = meta.get("file_hash")
            size = meta.get("file_size")
            files[str(source)] = IndexedFile(
                source=str(source),
                digest=str(digest) if digest else None,
                size=int(size) if isinstance(size, (int, float)) else None,
            )
        return files

    def delete_file_chunks(self, source: str) -> int:
        """Xoá toàn bộ chunk của một file (theo metadata `source`) — file đổi/xoá (KB-5.1)."""
        try:
            existing = self.collection.get(where={"source": source}, include=[])
            ids = existing.get("ids") or []
            if not ids:
                return 0
            self.collection.delete(ids=ids)
            # KB-5.3: index đổi ⇒ cache rerank cũ không còn đúng
            self._mark_index_changed()
            return len(ids)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"delete_file_chunks({source}): {exc}")
            return 0

    def backfill_file_digests(self, files: List[Any]) -> int:
        """Ghi `file_hash` cho file index từ bản trước KB-5.1 (cùng size ⇒ không cần embed lại)."""
        updated = 0
        for disk in files:
            try:
                found = self.collection.get(where={"source": disk.path}, include=["metadatas"])
            except Exception:  # pragma: no cover
                continue
            ids = found.get("ids") or []
            metas = found.get("metadatas") or []
            if not ids:
                continue
            new_metas = [{**(meta or {}), "file_hash": disk.digest, "file_size": disk.size} for meta in metas]
            try:
                self.collection.update(ids=ids, metadatas=new_metas)
                updated += len(ids)
            except Exception as exc:  # pragma: no cover
                logger.warning(f"backfill_file_digests({disk.path}): {exc}")
        return updated

    async def _refresh_corpus_after_sync(self) -> None:
        """Nạp lại corpus BM25 sau khi add/delete (TD-13: không được để corpus lệch)."""
        try:
            existing = self.collection.get(include=["documents", "metadatas"])
            self._corpus_ids = existing.get("ids", []) or []
            self._corpus_texts = existing.get("documents", []) or []
            self._corpus_metas = existing.get("metadatas", []) or []
            self._rebuild_bm25()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"_refresh_corpus_after_sync: {exc}")

    async def sync_documents(self) -> Dict[str, Any]:
        """Index **tăng dần** (KB-5.1): chỉ embed file mới/đổi, xoá chunk của file đã bị xoá.

        Khác `refresh` (clear + index lại tất cả): **không** gọi `clear_database()` ⇒ index cũ vẫn trả lời được
        trong lúc sync. Trả dict đếm + tên file cho UI hiện kết quả.
        """
        started = time.monotonic()
        folder = Path(self.settings.documents_folder)

        disk_files, skipped = scan_folder(folder, self._supported_exts, self.settings.max_file_size_mb)
        if not disk_files:
            raise DocumentsFolderEmptyError(
                f"sync_documents: folder={folder} has no supported files (skipped={len(skipped)})"
            )

        plan: SyncPlan = diff_indexed(disk_files, self.indexed_files())

        removed_chunks = 0
        for disk in plan.updated:
            removed_chunks += self.delete_file_chunks(disk.path)
        for source in plan.removed:
            removed_chunks += self.delete_file_chunks(source)

        documents: List[Document] = []
        errors: List[str] = []
        for disk in plan.to_index:
            try:
                documents.extend(await self._process_single_file(Path(disk.path)))
            except Exception as exc:  # một file lỗi không làm fail cả lần sync
                errors.append(f"{disk.path}: {type(exc).__name__}: {exc}")

        if documents:
            await self._add_documents_to_db(documents)

        backfilled = self.backfill_file_digests(plan.backfill)
        if documents or removed_chunks or backfilled:
            await self._refresh_corpus_after_sync()

        elapsed_ms = int((time.monotonic() - started) * 1000)
        summary = {
            "added": [Path(f.path).name for f in plan.added],
            "updated": [Path(f.path).name for f in plan.updated],
            "removed": [Path(s).name for s in plan.removed],
            "skipped": skipped,
            "unchanged": len(plan.unchanged),
            "total_chunks": len(documents),
            "removed_chunks": removed_chunks,
            "elapsed_ms": elapsed_ms,
            "details": errors,
        }
        logger.info(
            "sync_documents: +%d ~%d -%d (skip %d, unchanged %d) chunks=%d in %dms",
            len(plan.added),
            len(plan.updated),
            len(plan.removed),
            len(skipped),
            len(plan.unchanged),
            len(documents),
            elapsed_ms,
        )
        return summary

    async def clear_database(self):
        """Clear all documents from the database"""
        try:
            # Delete and recreate the collection
            self.chroma_client.delete_collection(self.settings.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.settings.collection_name,
                metadata={"description": "RAG documents collection"}
            )
            # TD-13: phải reset cả corpus in-memory, nếu không BM25 giữ chunk cũ và
            # sparse retrieval trộn dữ liệu đã xoá (bug thấy ở KB-2.1: 830 vs 638 chunk).
            self._corpus_ids = []
            self._corpus_texts = []
            self._corpus_metas = []
            self._bm25 = None
            # KB-5.3: index rỗng ⇒ mọi entry cache rerank vô nghĩa
            self._mark_index_changed()
            logger.info("ChromaDB collection cleared and recreated successfully.")
        except Exception as e:
            logger.error(f"Error clearing database: {str(e)}")
            raise

    async def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
            logger.info("Executor shutdown completed.")
