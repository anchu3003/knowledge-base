import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncIterator

from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage)
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.core.config import Settings
from app.core.errors import AppError, map_provider_error
from app.core.provider_retry import ProviderThrottle
from app.services.document_service import DocumentService
from app.services.conversation_store import ConversationStore
from app.services.pii_service import PIIRedactor, summarize_pii_stats
from app.services.multi_query import merge_hits, split_query

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat interactions with RAG."""

    #: Mặc định = None để test có thể dựng service bằng `object.__new__(ChatService)` (không qua
    #: `__init__`) mà `get_conversation_history` vẫn chạy — trước KB-5.2 attribute này không tồn tại
    #: và 16 test cũ vỡ với `AttributeError`.
    conversation_store: Optional[ConversationStore] = None

    def __init__(
            self,
            settings: Settings,
            document_service: DocumentService,
            conversation_store: Optional[ConversationStore] = None,
    ):
        self.settings = settings
        self.document_service = document_service

        # Initialize LLM based on configuration type
        if settings.openai_base_url and settings.openai_api_type.lower() == "azure":
            # Use AzureChatOpenAI if available, otherwise use ChatOpenAI with model_kwargs
            if AzureChatOpenAI is not None:
                logger.info(
                    f"Initializing AzureChatOpenAI with endpoint: {settings.openai_base_url}, deployment: {settings.openai_model}")
                try:
                    self.llm = AzureChatOpenAI(
                        azure_deployment=settings.openai_model,
                        azure_endpoint=settings.openai_base_url,
                        temperature=settings.default_temperature,
                        max_tokens=settings.default_max_tokens,
                        timeout=settings.provider_timeout_seconds,
                        max_retries=0,
                    )
                    logger.info("AzureChatOpenAI initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize AzureChatOpenAI: {str(e)}")
                    raise ValueError(
                        f"Failed to initialize AzureChatOpenAI: {str(e)}. Please check your Azure configuration.")
            else:
                # Fallback to ChatOpenAI with model_kwargs for Azure
                logger.info(
                    f"Using ChatOpenAI for Azure with endpoint: {settings.openai_base_url}, deployment: {settings.openai_model}")
                try:
                    self.llm = ChatOpenAI(
                        api_key=settings.openai_api_key,
                        temperature=settings.default_temperature,
                        max_tokens=settings.default_max_tokens,
                        timeout=settings.provider_timeout_seconds,
                        max_retries=0,
                        model_kwargs={
                            "azure_endpoint": settings.openai_base_url,
                            "openai_api_version": settings.openai_api_version,
                            "azure_deployment": settings.openai_model
                        }
                    )
                    logger.info("ChatOpenAI (Azure) initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize ChatOpenAI for Azure: {str(e)}")
                    raise ValueError(
                        f"Failed to initialize ChatOpenAI for Azure: {str(e)}. Please check your Azure configuration.")
        else:
            # Public OpenAI or compatible endpoint
            logger.info(f"Initializing ChatOpenAI with model: {settings.openai_model}")
            llm_kwargs = {
                "openai_api_key": settings.openai_api_key,
                "model": settings.openai_model,
                "temperature": settings.default_temperature,
                "max_tokens": settings.default_max_tokens,
                # Retry do service quyết định (`ProviderThrottle`) — SDK không retry để tránh 2 tầng.
                "timeout": settings.provider_timeout_seconds,
                "max_retries": 0,
            }
            if settings.openai_base_url:
                llm_kwargs["openai_api_base"] = settings.openai_base_url

            try:
                self.llm = ChatOpenAI(**llm_kwargs)
                logger.info("ChatOpenAI initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ChatOpenAI: {str(e)}")
                raise ValueError(f"Failed to initialize ChatOpenAI: {str(e)}. Please check your OpenAI configuration.")

        # Conversation history: RAM là nguồn của phiên hiện tại, SQLite (`ConversationStore`) là bản bền
        # (KB-5.2 — trả TD-2). Không có store (`CHAT_DB_PATH=` rỗng) ⇒ chỉ in-memory như trước.
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        self.conversation_store = conversation_store

        # PII/secret redaction applied to every payload sent to the LLM
        # (see .clinerules/30-pii-safety.md)
        self.pii = PIIRedactor(settings)

        # Cổng duy nhất gọi provider: semaphore (PROVIDER_MAX_CONCURRENCY) + retry có ngân sách
        # (KB-3.2). LLM được tạo với `max_retries=0` ⇒ chỉ có MỘT tầng retry.
        self.provider = ProviderThrottle(settings)

    async def _initial_retrieval(self, query: str) -> tuple[List[Dict[str, Any]], List[str]]:
        """Retrieval bước đầu, có **multi-query** cho câu hỏi nhiều ý (KB-5.4).

        Trả `(hits, parts)`:
        - `parts` rỗng ⇒ câu hỏi **một ý** (hoặc multi-query bị tắt) ⇒ hành vi y như trước KB-5.4.
        - `parts` ≥ 2 ⇒ đã retrieve từng phần và gộp (mỗi chunk giữ score cao nhất).

        Tách bằng heuristic (0 token LLM — xem `app/services/multi_query.py`). Mỗi phần chỉ chấm
        `rerank_top_n // 2` ứng viên để latency không nhân lên gấp N; các phần chạy **song song**.
        """
        if not self.settings.multi_query_enabled:
            docs = await self.document_service.search_similar_documents(
                query=query, k=self.settings.retrieval_k
            )
            return docs, []

        parts = split_query(query, max_parts=self.settings.multi_query_max_parts)
        if len(parts) <= 1:
            docs = await self.document_service.search_similar_documents(
                query=query, k=self.settings.retrieval_k
            )
            return docs, []

        per_part_top_n = max(2, self.settings.rerank_top_n // 2)
        results = await asyncio.gather(
            *[
                self.document_service.search_similar_documents(
                    query=part,
                    k=self.settings.retrieval_k,
                    rerank_top_n=per_part_top_n,
                )
                for part in parts
            ],
            return_exceptions=True,
        )
        hit_lists = [result for result in results if isinstance(result, list) and result]
        if not hit_lists:
            # Mọi phần đều lỗi ⇒ không để câu hỏi chết: fallback về 1 bước như trước
            logger.warning("multi-query: tất cả sub-query lỗi, fallback single-query")
            docs = await self.document_service.search_similar_documents(
                query=query, k=self.settings.retrieval_k
            )
            return docs, []

        merged = merge_hits(hit_lists)[: self.settings.retrieval_k]
        logger.info("multi-query: %d phần, %d hit sau gộp", len(parts), len(merged))
        return merged, parts

    async def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """Retrieval-only (eval harness + debug): hits sau multi-query, **không** gọi LLM trả lời."""
        docs, _ = await self._initial_retrieval(query)
        return docs

    async def chat(
            self,
            message: str,
            conversation_id: Optional[str] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Handle chat interaction with RAG."""
        # Generate conversation ID if not provided
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        # Set parameters
        max_tokens = max_tokens or self.settings.default_max_tokens
        temperature = temperature or self.settings.default_temperature

        try:
            # Initial retrieval (KB-5.4: câu hỏi nhiều ý ⇒ retrieve từng phần rồi gộp)
            used_query = message
            rewrite_attempts = 0
            similar_docs, multi_query_parts = await self._initial_retrieval(message)

            # Optionally perform query rewriting if retrieval quality is poor
            if self.settings.enable_query_rewrite:
                def _quality(docs: List[Dict[str, Any]]) -> tuple[int, float]:
                    counts = len(docs)
                    top_score = docs[0]["score"] if docs else 0.0
                    return counts, float(top_score)

                count, top = _quality(similar_docs)
                target_min = self.settings.rewrite_min_results
                target_top = self.settings.rewrite_min_top_score

                if count < target_min or top < target_top:
                    best_docs = similar_docs
                    best_count, best_top = count, top
                    for _ in range(max(0, self.settings.rewrite_max_attempts)):
                        rewrite_attempts += 1
                        rewritten = await self._rewrite_query(used_query)
                        # Avoid infinite loops if the model echoes the same query
                        if rewritten and rewritten.strip() and rewritten.strip() != used_query.strip():
                            candidate_docs = await self.document_service.search_similar_documents(
                                query=rewritten,
                                k=self.settings.retrieval_k
                            )
                            c_count, c_top = _quality(candidate_docs)
                            # Prefer higher count, break ties by top score
                            if (c_count > best_count) or (c_count == best_count and c_top > best_top):
                                best_docs = candidate_docs
                                best_count, best_top = c_count, c_top
                                used_query = rewritten
                            # Stop early if we already meet thresholds
                            if best_count >= target_min and best_top >= target_top:
                                break
                        else:
                            # No meaningful rewrite; stop trying
                            break
                    similar_docs = best_docs

            # Build context from retrieved documents
            context = self.build_context(similar_docs)

            # Get conversation history
            # KB-5.2: lazy-load từ SQLite nếu RAM chưa có (restart container vẫn giữ context)
            conversation_history = self.get_conversation_history(conversation_id)

            # Create a prompt with context and history
            system_prompt = self._create_system_prompt(context)
            messages = self._build_messages(system_prompt, conversation_history, message)

            # Mask PII/secrets before anything leaves for the LLM
            messages, pii_stats = self._redact_messages(messages)

            # Update LLM parameters
            self.llm.temperature = temperature
            self.llm.max_tokens = max_tokens

            # Generate response (retry/backoff + semaphore: KB-3.2)
            response = await self.provider.run(lambda: self.llm.agenerate([messages]), op="chat")
            ai_response = response.generations[0][0].text

            # Update conversation history
            self._update_conversation(conversation_id, message, ai_response)

            # Prepare sources information
            sources = self._format_sources(similar_docs)

            return {
                "answer": ai_response,
                "conversation_id": conversation_id,
                "sources": sources,
                "metadata": {
                    "retrieved_documents": len(similar_docs),
                    "timestamp": datetime.now().isoformat(),
                    "model": self.settings.openai_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "original_query": message,
                    "used_query": used_query,
                    "query_rewrite_enabled": self.settings.enable_query_rewrite,
                    "query_rewrite_attempts": rewrite_attempts,
                    "multi_query_enabled": self.settings.multi_query_enabled,
                    "multi_query_parts": multi_query_parts,
                    "pii_redaction": pii_stats,
                    **summarize_pii_stats(pii_stats)
                }
            }

        except AppError:
            raise
        except Exception as e:
            # Map lỗi SDK/provider sang taxonomy dùng chung (KB-3.1); lỗi lạ → 500 internal_error.
            # Client chỉ nhận code + message chung; chi tiết gốc đi vào log qua `internal_detail`.
            mapped = map_provider_error(e)
            logger.error("chat failed: code=%s detail=%s", mapped.code, mapped.internal_detail)
            raise mapped from e

    async def stream_chat(
            self,
            message: str,
            conversation_id: Optional[str] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None,
            request_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream chat response tokens as an async iterator of events.

        Contract (KB-3.3): `start → token* → (end | error)` — luôn có **một** event kết thúc.

        - event `error` = `{"type": "error", "error": {code, message, request_id}}` (cùng schema với
          envelope lỗi của `/chat`, taxonomy KB-3.1);
        - client disconnect (`CancelledError`/`GeneratorExit`) ⇒ nếu đã phát ≥1 token thì lưu phần đã
          stream vào history với `interrupted=True`, chưa có token thì bỏ (Q&A KB-3.3); log mức `info`,
          không stack.
        """
        # Generate conversation ID if not provided
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        request_id = request_id or "-"

        # Set parameters
        max_tokens = max_tokens or self.settings.default_max_tokens
        temperature = temperature or self.settings.default_temperature

        full_text = ""
        emitted_tokens = False

        try:
            # Initial retrieval (KB-5.4: câu hỏi nhiều ý ⇒ retrieve từng phần rồi gộp)
            used_query = message
            rewrite_attempts = 0
            similar_docs, multi_query_parts = await self._initial_retrieval(message)

            # Optional query rewrite if results are weak
            if self.settings.enable_query_rewrite:
                def _quality(docs: List[Dict[str, Any]]) -> tuple[int, float]:
                    counts = len(docs)
                    top_score = docs[0]["score"] if docs else 0.0
                    return counts, float(top_score)

                count, top = _quality(similar_docs)
                target_min = self.settings.rewrite_min_results
                target_top = self.settings.rewrite_min_top_score

                if count < target_min or top < target_top:
                    best_docs = similar_docs
                    best_count, best_top = count, top
                    for _ in range(max(0, self.settings.rewrite_max_attempts)):
                        rewrite_attempts += 1
                        rewritten = await self._rewrite_query(used_query)
                        if rewritten and rewritten.strip() and rewritten.strip() != used_query.strip():
                            candidate_docs = await self.document_service.search_similar_documents(
                                query=rewritten,
                                k=self.settings.retrieval_k
                            )
                            c_count, c_top = _quality(candidate_docs)
                            if (c_count > best_count) or (c_count == best_count and c_top > best_top):
                                best_docs = candidate_docs
                                best_count, best_top = c_count, c_top
                                used_query = rewritten
                            if best_count >= target_min and best_top >= target_top:
                                break
                        else:
                            break
                    similar_docs = best_docs

            # Build context from retrieved documents
            context = self.build_context(similar_docs)

            # Get conversation history
            # KB-5.2: lazy-load từ SQLite nếu RAM chưa có (restart container vẫn giữ context)
            conversation_history = self.get_conversation_history(conversation_id)

            # Create a prompt with context and history
            system_prompt = self._create_system_prompt(context)
            messages = self._build_messages(system_prompt, conversation_history, message)

            # Mask PII/secrets before anything leaves for the LLM
            messages, pii_stats = self._redact_messages(messages)

            # Update LLM parameters
            self.llm.temperature = temperature
            self.llm.max_tokens = max_tokens

            # Send start event
            yield {
                "type": "start",
                "conversation_id": conversation_id,
                "metadata": {
                    "retrieved_documents": len(similar_docs),
                    "timestamp": datetime.now().isoformat(),
                    "model": self.settings.openai_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "original_query": message,
                    "used_query": used_query,
                    "query_rewrite_enabled": self.settings.enable_query_rewrite,
                    "query_rewrite_attempts": rewrite_attempts,
                    "multi_query_enabled": self.settings.multi_query_enabled,
                    "multi_query_parts": multi_query_parts,
                    "pii_redaction": pii_stats,
                    **summarize_pii_stats(pii_stats)
                }
            }

            async for chunk in self.provider.stream(lambda: self.llm.astream(messages), op="stream_chat"):
                # chunk is typically an AIMessageChunk with .content containing incremental text
                delta = getattr(chunk, "content", None)
                if not delta:
                    # Some providers may use .text or other attributes
                    delta = getattr(chunk, "text", "")
                if not delta:
                    continue
                full_text += delta
                emitted_tokens = True
                yield {"type": "token", "token": delta}

            # Update conversation history after completion
            self._update_conversation(conversation_id, message, full_text)

            # Prepare sources information
            sources = self._format_sources(similar_docs)

            yield {
                "type": "end",
                "answer": full_text,
                "conversation_id": conversation_id,
                "sources": sources,
                "metadata": {
                    "retrieved_documents": len(similar_docs),
                    "timestamp": datetime.now().isoformat(),
                    "model": self.settings.openai_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "original_query": message,
                    "used_query": used_query,
                    "query_rewrite_enabled": self.settings.enable_query_rewrite,
                    "query_rewrite_attempts": rewrite_attempts,
                    "multi_query_enabled": self.settings.multi_query_enabled,
                    "multi_query_parts": multi_query_parts,
                    "pii_redaction": pii_stats,
                    **summarize_pii_stats(pii_stats)
                }
            }

        except (asyncio.CancelledError, GeneratorExit):
            # Client disconnect — không phải lỗi ⇒ log `info`, KHÔNG stack trace.
            # Q&A KB-3.3: giữ phần đã stream nếu đã có ≥1 token (đánh dấu `interrupted`), chưa có thì bỏ.
            if emitted_tokens:
                self._update_conversation(conversation_id, message, full_text, interrupted=True)
                logger.info(
                    "stream_chat interrupted request_id=%s conversation_id=%s chars=%s (saved partial answer)",
                    request_id, conversation_id, len(full_text),
                )
            else:
                logger.info(
                    "stream_chat interrupted request_id=%s conversation_id=%s (no token yet, nothing saved)",
                    request_id, conversation_id,
                )
            raise
        except AppError as e:
            logger.error(
                "stream_chat failed: code=%s request_id=%s detail=%s", e.code, request_id, e.internal_detail,
            )
            yield {
                "type": "error",
                "error": {"code": e.code, "message": e.public_message, "request_id": request_id},
            }
        except Exception as e:
            mapped = map_provider_error(e)
            logger.error(
                "stream_chat failed: code=%s request_id=%s detail=%s",
                mapped.code, request_id, mapped.internal_detail, exc_info=True,
            )
            yield {
                "type": "error",
                "error": {"code": mapped.code, "message": mapped.public_message, "request_id": request_id},
            }

    async def provider_probe(self) -> None:
        """Gọi provider **1 request rẻ nhất** (`max_tokens=1`) — dùng cho `/ready?deep=true` (KB-3.4).

        - `retry=False`: probe phải fail-fast, retry chỉ làm probe chậm;
        - vẫn đi qua `ProviderThrottle` (semaphore) để không vượt TPM;
        - raise `AppError` (taxonomy KB-3.1) nếu provider không trả lời.
        """
        probe_llm = self.llm.bind(max_tokens=1) if hasattr(self.llm, "bind") else self.llm
        await self.provider.run(
            lambda: probe_llm.ainvoke([HumanMessage(content="ping")]),
            op="health_probe",
            retry=False,
        )

    async def _rewrite_query(self, original_query: str) -> str:
        """Use the LLM to rewrite the user query to improve retrieval.

        Returns a concise rewritten query string. If rewriting fails, returns the original.
        """
        try:
            # Load rewrite system prompt from a file if configured
            rewrite_prompt_path = getattr(self.settings, "rewrite_system_prompt_path", None)
            rewrite_system_prompt: Optional[str] = None
            if rewrite_prompt_path:
                try:
                    with open(rewrite_prompt_path, "r", encoding="utf-8") as f:
                        rewrite_system_prompt = f.read()
                except Exception as e:
                    logger.warning(
                        f"Failed to load rewrite system prompt from '{rewrite_prompt_path}': {e}. Using default."
                    )

            if not rewrite_system_prompt:
                rewrite_system_prompt = (
                    "You are a query reformulation assistant for a Retrieval-Augmented Generation (RAG) system.\n"
                    "Rewrite the user's query to best retrieve relevant documentation snippets from a developer knowledge base.\n"
                    "Guidelines:\n"
                    "- Be concise (5-25 words).\n"
                    "- Expand with key technical terms, synonyms, and likely file or technology names when helpful.\n"
                    "- Remove pronouns and vague words; keep only essential keywords.\n"
                    "- Do NOT answer the question; output only the rewritten search query."
                )

            system = SystemMessage(content=rewrite_system_prompt)
            # Redact PII before sending the query to the LLM (it may contain personal info)
            safe_query, _ = self.pii.redact_with_stats(original_query)
            human = HumanMessage(content=f"Original query: {safe_query}\nRewritten search query:")

            # Temporarily adjust parameters for rewriting
            prev_temp = getattr(self.llm, "temperature", 0.7)
            prev_max = getattr(self.llm, "max_tokens", 256)
            try:
                self.llm.temperature = 0.2
                self.llm.max_tokens = 64
                # Rewrite là best-effort: chỉ đi qua semaphore, KHÔNG retry (retry sẽ đốt quota
                # đúng lúc provider đang 429 — mà query gốc vẫn dùng được).
                resp = await self.provider.run(
                    lambda: self.llm.agenerate([[system, human]]), op="rewrite", retry=False,
                )
            finally:
                self.llm.temperature = prev_temp
                self.llm.max_tokens = prev_max

            text = resp.generations[0][0].text.strip()
            # Ensure a single-line short query
            text = text.splitlines()[0].strip()
            return text or original_query
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")
            return original_query

    def build_context(self, similar_docs: List[Dict[str, Any]], max_chars: Optional[int] = None) -> str:
        """Build context string with citation labels `[S1]`, `[S2]`, … (KB-2.3).

        - Nhãn `[S{i}]` map 1-1 với `sources[i]["citation_id"]` trả về cho client.
        - **Không** cắt cứng mỗi chunk 500 ký tự như bản cũ (mất nửa bằng chứng với `chunk_size=1000`);
          cắt theo **budget tổng** `CONTEXT_MAX_CHARS` (chunk điểm cao được ưu tiên vì `similar_docs`
          đã sort theo score).
        """
        if not similar_docs:
            return "No relevant documents found."

        budget = max_chars if max_chars is not None else getattr(self.settings, "context_max_chars", 6000)

        context_parts: List[str] = []
        used = 0
        for index, doc in enumerate(similar_docs, 1):
            remaining = budget - used
            if remaining <= 0:
                logger.info(
                    f"Context budget {budget} chars reached; dropped {len(similar_docs) - index + 1} source(s)."
                )
                break

            metadata = doc.get("metadata") or {}
            name = metadata.get("file_name") or metadata.get("source", "Unknown")
            heading = metadata.get("heading_path") or ""
            label = f"[S{index}] {name}" + (f" — {heading}" if heading else "")
            content = (doc.get("content") or "")[:remaining]
            context_parts.append(f"{label}:\n{content}\n")
            used += len(content)

        return "\n---\n".join(context_parts)

    def _create_system_prompt(self, context: str) -> str:
        """Create a system prompt with context.

        Attempts to load a prompt template from `settings.system_prompt_path`.
        The template may contain the placeholder `{context}` which will be
        replaced with the provided context. Falls back to the built-in default
        prompt if the file cannot be read or formatted.
        """
        path = getattr(self.settings, "system_prompt_path", None)
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    template = f.read()
                # Safer replacement to avoid KeyError with stray braces in the template
                return template.replace("{context}", context)
            except Exception as e:
                logger.warning(f"Failed to load system prompt from '{path}': {e}. Using default prompt.")

        # Built-in default prompt
        return (
            "\n"
            "        You are an expert AI assistant for my **personal knowledge base** (software engineering, interview prep, English learning).\n"
            "        Answer from the retrieved context below and cite its labels.\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            "        RETRIEVED CONTEXT FROM MY KNOWLEDGE BASE (mỗi block có nhãn [S1], [S2], ...):\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            f"        {context}\n\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            "        RESPONSE BEST PRACTICES:\n"
            "        ═══════════════════════════════════════════════════════════════════\n\n"
            "        1. **Cite every claim** with its context label: [S1], [S2], ... (chỉ dùng nhãn có trong context)\n"
            "        2. Nhiều block cùng chứng minh một ý thì ghi liền: [S1][S3]\n"
            "        3. Never invent labels, line numbers, or file paths that are not in the context\n"
            "        4. Context không chứa thông tin ⇒ nói rõ \"Thông tin này không có trong knowledge base\"\n"
            "        5. Explain technical terms briefly; use Vietnamese if the question/context is Vietnamese\n"
            "        6. Keep answers concise, structured, and free of speculation\n"
            "        7. End the answer with a line `Nguồn: [S1], [S2]` listing the labels actually used\n"
            "        8. Decline to answer any request involving violence, weapons, self-harm, abuse, explicit content, or illegal activity.\n"
            "        9. Only respond with information directly connected to the user’s question.\n"
            "        10. Avoid unnecessary details, speculation, or hallucinated facts.\n"
            "        11. If the question lacks context, ask briefly for clarification.\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            "        YOUR GOAL: help me recall and apply what is in my own notes, accurately and with traceable citations.\n"
            "        "
        )

    def _redact_messages(self, messages: List[Any]) -> tuple[List[Any], Dict[str, int]]:
        """Return (messages, stats) with PII/secret redacted from every message content.

        Applied at the outbound gate to the LLM so PII inside the retrieved context
        (not only the user's question) is masked too. See `.clinerules/30-pii-safety.md`.
        """
        if not self.pii.enabled:
            return messages, {}
        redacted_messages: List[Any] = []
        totals: Dict[str, int] = {}
        for msg in messages:
            content = getattr(msg, "content", None)
            if isinstance(content, str):
                redacted, stats = self.pii.redact_with_stats(content)
                if redacted != content:
                    msg = msg.__class__(content=redacted)
                    for key, val in stats.items():
                        totals[key] = totals.get(key, 0) + val
            redacted_messages.append(msg)
        return redacted_messages, totals

    def _build_messages(
            self,
            system_prompt: str,
            history: List[Dict[str, Any]],
            current_message: str
    ) -> List[Any]:
        """Build message list for LLM."""
        messages: List[Any] = [SystemMessage(content=system_prompt)]

        # Add conversation history (limit to relevant messages)
        max_history = self.settings.max_conversation_length
        recent_history = history[-max_history:] if len(history) > max_history else history

        for msg in recent_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # Add the current message
        messages.append(HumanMessage(content=current_message))
        return messages

    def _update_conversation(
            self,
            conversation_id: str,
            user_message: str,
            ai_response: str,
            interrupted: bool = False,
    ):
        """Update conversation history.

        `interrupted=True` (KB-3.3): client ngắt giữa stream ⇒ vẫn lưu phần đã sinh nhưng đánh dấu
        để lần sau biết câu trả lời chưa hoàn chỉnh.
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        conversation = self.conversations[conversation_id]

        # PII: **không** lưu bản thô xuống DB (giả định (b) của KB-5.2 + `.clinerules/30-pii-safety.md`).
        # Hội thoại reload từ server vì thế có thể hiện placeholder `[EMAIL_1]` thay cho dữ liệu thật.
        stored_user_message = self.pii.redact(user_message)

        # Add the user message
        conversation.append({
            "role": "user",
            "content": stored_user_message,
            "timestamp": datetime.now().isoformat()
        })

        # Add AI response
        assistant_message = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        }
        if interrupted:
            assistant_message["interrupted"] = True
        conversation.append(assistant_message)

        # Limit conversation length
        max_length = self.settings.max_conversation_length * 2  # *2 for user+assistant pairs
        if len(conversation) > max_length:
            self.conversations[conversation_id] = conversation[-max_length:]

        self._persist(conversation_id)

    def _persist(self, conversation_id: str) -> None:
        """Ghi conversation xuống SQLite (KB-5.2). Lỗi DB **không** được làm hỏng câu trả lời."""
        if self.conversation_store is None:
            return
        try:
            self.conversation_store.save(conversation_id, self.conversations.get(conversation_id, []))
        except Exception as exc:  # pragma: no cover - phụ thuộc IO/disk
            logger.error("Failed to persist conversation %s: %s: %s", conversation_id, type(exc).__name__, exc)

    @staticmethod
    def _format_sources(similar_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format source documents for response (KB-2.3: thêm citation_id/chunk_id/snippet).

        Field cũ (`file_path`, `file_name`, `file_type`, `relevance_score`, `content_preview`) được
        giữ nguyên để FE hiện tại không vỡ; các field mới là **additive**.
        """
        sources = []
        for index, doc in enumerate(similar_docs, 1):
            metadata = doc.get("metadata") or {}
            content = doc.get("content", "")
            sources.append({
                "citation_id": f"S{index}",
                "chunk_id": doc.get("chunk_id") or metadata.get("chunk_id"),
                "file_path": metadata.get("source", "Unknown"),
                "file_name": metadata.get("file_name", "Unknown"),
                "file_type": metadata.get("file_type", "Unknown"),
                "heading_path": metadata.get("heading_path", ""),
                "relevance_score": round(doc.get("score", 0.0), 3),
                "snippet": content[:400],
                "content_preview": content[:200] + "..." if len(content) > 200 else content,
            })
        return sources

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation history.

        KB-5.2: cache RAM miss ⇒ nạp từ SQLite (lazy). Nhờ vậy `conversation_id` cũ vẫn giữ context
        sau khi restart container, mà không phải nạp sẵn toàn bộ DB vào RAM lúc khởi động.
        """
        if conversation_id not in self.conversations and self.conversation_store is not None:
            try:
                messages = self.conversation_store.load(conversation_id)
            except Exception as exc:  # pragma: no cover - phụ thuộc IO/disk
                logger.error("Failed to load conversation %s: %s: %s", conversation_id, type(exc).__name__, exc)
                messages = None
            if messages is not None:
                self.conversations[conversation_id] = messages
        return self.conversations.get(conversation_id, [])

    def clear_conversation(self, conversation_id: str):
        """Clear a specific conversation (RAM + SQLite)."""
        self.conversations.pop(conversation_id, None)
        if self.conversation_store is not None:
            try:
                self.conversation_store.delete(conversation_id)
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to delete conversation %s: %s: %s", conversation_id, type(exc).__name__, exc)

    def list_conversations(self) -> List[Dict[str, Any]]:
        """Danh sách conversation (mới nhất trước).

        KB-5.2: server là nguồn sự thật ⇒ đọc từ SQLite. Không có store ⇒ chỉ trả id trong RAM
        (giữ kiểu dữ liệu cũ cho ai đang gọi trực tiếp).
        """
        if self.conversation_store is not None:
            try:
                return self.conversation_store.list(limit=self.settings.max_conversations)
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to list conversations: %s: %s", type(exc).__name__, exc)
                return []
        now = datetime.now().isoformat()
        return [
            {
                "id": conversation_id,
                "title": "",
                "created_at": now,
                "updated_at": now,
                "message_count": len(messages),
            }
            for conversation_id, messages in self.conversations.items()
        ]

    def get_conversation_detail(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Chi tiết 1 conversation (kèm messages) hoặc `None` nếu không tồn tại."""
        messages = self.get_conversation_history(conversation_id)
        summaries = {item["id"]: item for item in self.list_conversations()}
        summary = summaries.get(conversation_id)
        if summary is None and not messages:
            return None
        return {
            "id": conversation_id,
            "title": (summary or {}).get("title", ""),
            "created_at": (summary or {}).get("created_at", ""),
            "updated_at": (summary or {}).get("updated_at", ""),
            "messages": messages,
        }
