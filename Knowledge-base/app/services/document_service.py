import asyncio
import importlib
import logging
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Any as TypingAny, Mapping

import chromadb
from chromadb import SparseVector

# Suppress ChromaDB telemetry warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*telemetry.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*capture.*")

from chromadb.config import Settings as ChromaSettings
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import (
    TextLoader,
    JSONLoader,
    UnstructuredWordDocumentLoader,
    PyPDFLoader,
)

from app.core.config import Settings

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for handling document processing and vector storage"""

    def __init__(self, settings: Settings):
        self.settings = settings

        # Initialize embeddings using sentence-transformers
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2",
            model_kwargs={'device': 'cpu'}
        )

        self.chroma_client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # Get or create a collection
        try:
            self.collection = self.chroma_client.get_collection(settings.collection_name)
        except ValueError:
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

            # Split documents into chunks
            splitter = self.get_splitter(file_path)
            chunks = splitter.split_documents(documents)

            # Add metadata
            for chunk in chunks:
                chunk.metadata.update({
                    "source": str(file_path),
                    "file_type": file_path.suffix,
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size
                })

            return chunks

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise

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
        """Pick the best text splitter based on the file type."""
        ext = file_path.suffix.lower()
        if ext == ".md":
            # Preserve Markdown structure for better semantic chunks
            return MarkdownTextSplitter(
                chunk_size=self.settings.chunk_size,
                chunk_overlap=self.settings.chunk_overlap
            )
        elif ext in (".docx", ".pdf"):
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

    async def _add_documents_to_db(self, documents: List[Document]):
        """Add documents to ChromaDB vector database"""
        ids: List[str] = []
        if not documents:
            return

        # Extract texts and metadata
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        batch_size = max(1, self.settings.embedding_batch_size)
        total = len(texts)
        loop = asyncio.get_event_loop()

        added = 0
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_texts = texts[start:end]
            batch_metas = metadatas[start:end]

            # Compute embeddings for this batch off the event loop
            embeddings = await loop.run_in_executor(
                self.executor,
                self.embeddings.embed_documents,
                batch_texts,
            )

            # Generate unique IDs for the batch (stable-ish based on content snippet)
            ids = [f"doc_{i}_{abs(hash(t[:100]))}" for i, t in enumerate(batch_texts, start=start)]

            # Add batch to ChromaDB
            try:
                self.collection.add(
                    embeddings=embeddings,
                    documents=batch_texts,
                    metadatas=batch_metas,
                    ids=ids,
                )
                added += len(batch_texts)
                logger.info(f"Added batch {start}-{end - 1} ({len(batch_texts)}) documents to ChromaDB collection.")
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

    async def search_similar_documents(self, query: str, k: int = None) -> List[Dict[str, Any]]:
        """Search for similar documents using dense, sparse and optional re-ranking.

        Returns list of dicts: {content, metadata, score, rank}
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
            similar_docs: List[Dict[str, Any]] = []
            for i, (_, doc, meta, score) in enumerate(dense_items[:k]):
                similar_docs.append({"content": doc, "metadata": meta, "score": score, "rank": i + 1})
            return similar_docs

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

        # Build a candidate list with content/meta
        candidates: List[Tuple[str, str, Dict[str, Any], float]] = []
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
            candidates.append((cid, doc, meta, combined.get(cid, 0.0)))

        # Sort by combined score
        candidates.sort(key=lambda x: x[3], reverse=True)

        # Optional cross-encoder re-ranking on top-N
        if self.settings.enable_rerank and candidates:
            top_n = min(self.settings.rerank_top_n, len(candidates))
            pairs = [(query, c[1]) for c in candidates[:top_n]]

            # Run cross-encoder off the event loop
            def _score_pairs() -> List[float]:
                self._ensure_cross_encoder()
                if self._cross_encoder is None:
                    return [0.0] * len(pairs)
                return list(self._cross_encoder.predict(pairs))

            rerank_scores: List[float] = await loop.run_in_executor(self.executor, lambda x: _score_pairs(), None)
            reranked = list(zip(candidates[:top_n], rerank_scores))
            reranked.sort(key=lambda x: x[1], reverse=True)
            # Replace top_n with reranked order and scores
            candidates = [(cid, doc, meta, float(score)) for (cid, doc, meta, _), score in reranked] + candidates[
                top_n:]

        # Prepare final results top-k
        final = []
        for i, (_, doc, meta, score) in enumerate(candidates[:k]):
            final.append({
                "content": doc,
                "metadata": meta,
                "score": float(score),
                "rank": i + 1,
            })
        return final

    async def get_status(self) -> Dict[str, Any]:
        """Get the status of the document database"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.settings.collection_name,
                "document_count": count,
                "status": "healthy" if count > 0 else "empty"
            }
        except Exception as e:
            logger.error(f"Error getting database status: {e}")
            return {
                "collection_name": self.settings.collection_name,
                "document_count": 0,
                "status": "error",
                "error": str(e)
            }

    async def clear_database(self):
        """Clear all documents from the database"""
        try:
            # Delete and recreate the collection
            self.chroma_client.delete_collection(self.settings.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.settings.collection_name,
                metadata={"description": "RAG documents collection"}
            )
            logger.info("ChromaDB collection cleared and recreated successfully.")
        except Exception as e:
            logger.error(f"Error clearing database: {str(e)}")
            raise

    async def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
            logger.info("Executor shutdown completed.")
