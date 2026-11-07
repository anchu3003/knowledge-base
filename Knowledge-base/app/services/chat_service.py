import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncIterator

from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage)
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from openai import APIError, APIConnectionError, AuthenticationError, RateLimitError

from app.core.config import Settings
from app.services.document_service import DocumentService
from app.services.pii_service import PIIRedactor, summarize_pii_stats

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat interactions with RAG."""

    def __init__(self, settings: Settings, document_service: DocumentService):
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
                        max_tokens=settings.default_max_tokens
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
                "max_tokens": settings.default_max_tokens
            }
            if settings.openai_base_url:
                llm_kwargs["openai_api_base"] = settings.openai_base_url

            try:
                self.llm = ChatOpenAI(**llm_kwargs)
                logger.info("ChatOpenAI initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ChatOpenAI: {str(e)}")
                raise ValueError(f"Failed to initialize ChatOpenAI: {str(e)}. Please check your OpenAI configuration.")

        # Store conversations in memory
        # (In production, this should be replaced with a database)
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}

        # PII/secret redaction applied to every payload sent to the LLM
        # (see .clinerules/30-pii-safety.md)
        self.pii = PIIRedactor(settings)

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
            # Initial retrieval
            used_query = message
            rewrite_attempts = 0
            similar_docs = await self.document_service.search_similar_documents(
                query=used_query,
                k=self.settings.retrieval_k
            )

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
            conversation_history = self.conversations.get(conversation_id, [])

            # Create a prompt with context and history
            system_prompt = self._create_system_prompt(context)
            messages = self._build_messages(system_prompt, conversation_history, message)

            # Mask PII/secrets before anything leaves for the LLM
            messages, pii_stats = self._redact_messages(messages)

            # Update LLM parameters
            self.llm.temperature = temperature
            self.llm.max_tokens = max_tokens

            # Generate response
            response = await self.llm.agenerate([messages])
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
                    "pii_redaction": pii_stats,
                    **summarize_pii_stats(pii_stats)
                }
            }

        except (APIConnectionError, ConnectionError) as e:
            error_msg = f"Connection error: Unable to connect to OpenAI/Azure endpoint. Please check your network connection and endpoint URL ({self.settings.openai_base_url or 'default'})."
            logger.error(f"{error_msg} Details: {str(e)}")
            raise ConnectionError(error_msg) from e
        except AuthenticationError as e:
            error_msg = f"Authentication error: Invalid API key or credentials. Please check your OPENAI_API_KEY."
            logger.error(f"{error_msg} Details: {str(e)}")
            raise ValueError(error_msg) from e
        except RateLimitError as e:
            error_msg = f"Rate limit exceeded: Too many requests. Please try again later."
            logger.error(f"{error_msg} Details: {str(e)}")
            raise ValueError(error_msg) from e
        except APIError as e:
            error_msg = f"API error: {str(e)}"
            logger.error(f"{error_msg} Details: {str(e)}")
            raise RuntimeError(error_msg) from e

    async def stream_chat(
            self,
            message: str,
            conversation_id: Optional[str] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream chat response tokens as an async iterator of events.

        Yields dict events with keys:
        - type: one of "start", "token", "end", "error"
        - other fields depending on the type
        """
        # Generate conversation ID if not provided
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        # Set parameters
        max_tokens = max_tokens or self.settings.default_max_tokens
        temperature = temperature or self.settings.default_temperature

        try:
            # Initial retrieval
            used_query = message
            rewrite_attempts = 0
            similar_docs = await self.document_service.search_similar_documents(
                query=used_query,
                k=self.settings.retrieval_k
            )

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
            conversation_history = self.conversations.get(conversation_id, [])

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
                    "pii_redaction": pii_stats,
                    **summarize_pii_stats(pii_stats)
                }
            }

            full_text = ""
            async for chunk in self.llm.astream(messages):
                # chunk is typically an AIMessageChunk with .content containing incremental text
                delta = getattr(chunk, "content", None)
                if not delta:
                    # Some providers may use .text or other attributes
                    delta = getattr(chunk, "text", "")
                if not delta:
                    continue
                full_text += delta
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
                    "pii_redaction": pii_stats,
                    **summarize_pii_stats(pii_stats)
                }
            }

        except (APIConnectionError, ConnectionError) as e:
            error_msg = (
                f"Connection error: Unable to connect to OpenAI/Azure endpoint. "
                f"Please check your network connection and endpoint URL "
                f"({self.settings.openai_base_url or 'default'})."
            )
            logger.error(f"{error_msg} Details: {str(e)}")
            yield {"type": "error", "message": error_msg}
        except AuthenticationError as e:
            error_msg = (
                "Authentication error: Invalid API key or credentials. "
                "Please check your OPENAI_API_KEY."
            )
            logger.error(f"{error_msg} Details: {str(e)}")
            yield {"type": "error", "message": error_msg}
        except RateLimitError as e:
            error_msg = "Rate limit exceeded: Too many requests. Please try again later."
            logger.error(f"{error_msg} Details: {str(e)}")
            yield {"type": "error", "message": error_msg}
        except APIError as e:
            error_msg = f"API error: {str(e)}"
            logger.error(f"{error_msg} Details: {str(e)}")
            yield {"type": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during chat (stream): {str(e)}"
            logger.error(f"{error_msg}", exc_info=True)
            yield {"type": "error", "message": error_msg}

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
                resp = await self.llm.agenerate([[system, human]])
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

    @staticmethod
    def build_context(similar_docs: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved documents."""
        if not similar_docs:
            return "No relevant documents found."

        context_parts = []
        for i, doc in enumerate(similar_docs, 1):
            source = doc["metadata"].get("source", "Unknown")
            content = doc["content"][:500]  # limit content length
            context_parts.append(f"Document {i} (from {source}):\n{content}\n")

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
            "        You are an expert AI onboarding assistant for the **RAG Chatbot API** project - a FastAPI-based system using Retrieval-Augmented Generation to answer questions from project documents. Your mission is to help new team members understand and contribute to this project quickly, reducing mentor workload by 80%+.\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            "        RELEVANT CONTEXT FROM PROJECT DOCUMENTS:\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            f"        {context}\n\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            "        RESPONSE BEST PRACTICES:\n"
            "        ═══════════════════════════════════════════════════════════════════\n\n"
            "        1. **Always reference file paths** from the context when available\n"
            "        2. **Show concrete code examples** with line numbers\n"
            "        3. **Explain technical terms** (RAG, embeddings, vector search, chunking)\n"
            "        4. **Provide step-by-step instructions** for setup/deployment tasks\n"
            "        5. **Link related concepts**: \"When you modify document_service.py, also check chat_service.py\"\n"
            "        6. **Anticipate follow-up questions**: \"Next, you might want to know about...\"\n"
            "        7. **Cite sources** at the end: \"*Reference: app/main.py:45-67, documents/Architecture.md*\"\n"
            "        8. **Use Vietnamese** for explanations if context suggests Vietnamese docs\n"
            "        9. **Highlight common pitfalls**: Missing .env, wrong Docker port, ChromaDB path issues\n"
            "        10. **Be encouraging**: \"Great question! This is a key concept in RAG systems...\"\n"
            "        11. Decline to answer any request involving violence, weapons, self-harm, abuse, explicit content, or illegal activity.\n"
            "        12. Only respond with information directly connected to the user’s question.\n"
            "        13. Avoid unnecessary details, speculation, or hallucinated facts.\n"
            "        14. If the question lacks context, ask briefly for clarification.\n"
            "        ═══════════════════════════════════════════════════════════════════\n"
            "        YOUR ULTIMATE GOAL:\n"
            "        ═══════════════════════════════════════════════════════════════════\n\n"
            "        Make new developers **productive in 30 minutes instead of 3 days**. Answer questions that would typically require:\n"
            "        - 2-3 hours of senior developer time\n"
            "        - Reading through multiple documentation files\n"
            "        - Trial-and-error experimentation\n"
            "        - Understanding complex RAG/LLM concepts\n\n"
            "        You are the **first line of support** - only escalate to human mentors when:\n"
            "        - Bug in production code that needs immediate fix\n"
            "        - Architecture decisions requiring team discussion\n"
            "        - Access/permission issues\n"
            "        - Information truly not available in project docs\n\n"
            "        **Remember:** You have deep knowledge of this specific RAG Chatbot API project. Use it fully!\n"
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

    def _update_conversation(self, conversation_id: str, user_message: str, ai_response: str):
        """Update conversation history."""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        conversation = self.conversations[conversation_id]

        # Add the user message
        conversation.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })

        # Add AI response
        conversation.append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        })

        # Limit conversation length
        max_length = self.settings.max_conversation_length * 2  # *2 for user+assistant pairs
        if len(conversation) > max_length:
            self.conversations[conversation_id] = conversation[-max_length:]

    @staticmethod
    def _format_sources(similar_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format source documents for response."""
        sources = []
        for doc in similar_docs:
            metadata = doc.get("metadata", {})
            sources.append({
                "file_path": metadata.get("source", "Unknown"),
                "file_name": metadata.get("file_name", "Unknown"),
                "file_type": metadata.get("file_type", "Unknown"),
                "relevance_score": round(doc.get("score", 0.0), 3),
                "content_preview": (
                    doc["content"][:200] + "..."
                    if len(doc.get("content", "")) > 200
                    else doc.get("content", "")
                )
            })
        return sources

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation history."""
        return self.conversations.get(conversation_id, [])

    def clear_conversation(self, conversation_id: str):
        """Clear a specific conversation."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

    def list_conversations(self) -> List[str]:
        """List all conversation IDs."""
        return list(self.conversations.keys())
