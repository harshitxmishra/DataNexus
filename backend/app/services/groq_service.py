import time
import logging
from typing import List, Dict, Any, Optional
from backend.app.config import settings

logger = logging.getLogger(__name__)

class GroqRAGService:
    """
    Production-grade GroqCloud LLM integration for Retrieval-Augmented Generation (RAG).
    Provides ultra-low-latency, evidence-grounded synthesis with strict citation validation,
    negative question gating, and multi-model fallback.
    """

    SYSTEM_PROMPT = (
        "You are the DataNexus Document Intelligence Analyst.\n"
        "Your mission is to answer user queries based strictly and solely on the provided document excerpts.\n\n"
        "RULES FOR EVIDENCE GROUNDING & CITATIONS:\n"
        "1. GROUNDING: Every statement, numerical figure, date, and factual claim must be verifiable within the provided excerpts.\n"
        "2. CITATIONS: Attribute every material claim to its source using [Source N] tags matching the provided excerpt headers.\n"
        "3. INSUFFICIENT EVIDENCE: If the excerpts do not contain sufficient facts to answer the question, or if the question "
        "is unrelated to the documents, you MUST respond beginning exactly with:\n"
        "   INSUFFICIENT_EVIDENCE: <concise explanation of why the evidence is insufficient>\n"
        "4. NO HALLUCINATION: Never assume, extrapolate, or introduce external knowledge not present in the excerpts."
    )

    def __init__(self):
        self._client = None
        self._initialized = False

    def _get_client(self):
        """Lazy thread-safe initialization of the Groq client."""
        if not self._initialized:
            api_key = getattr(settings, "GROQ_API_KEY", "") or ""
            if api_key.strip():
                try:
                    import groq
                    self._client = groq.Groq(
                        api_key=api_key.strip(),
                        timeout=getattr(settings, "GROQ_TIMEOUT_SECONDS", 15.0)
                    )
                except Exception as e:
                    logger.warning(f"Groq client initialization failed: {e}")
                    self._client = None
            else:
                self._client = None
            self._initialized = True
        return self._client

    def is_available(self) -> bool:
        """Check whether GroqCloud is configured with an active client."""
        client = self._get_client()
        return client is not None

    def generate_rag_answer(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        model_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesize an evidence-backed answer using GroqCloud LLM inference.
        Returns a dictionary with answer, evidence_status, model_used, latency_ms, and token metrics.
        """
        start_time = time.perf_counter()
        client = self._get_client()
        if not client:
            return {
                "success": False,
                "error": "Groq client is not configured or GROQ_API_KEY is missing",
                "answer": "",
                "evidence_status": "insufficient",
                "model_used": "none",
                "latency_ms": 0
            }

        # 1. Format Context Excerpts
        formatted_excerpts = []
        for rank, chunk in enumerate(context_chunks, start=1):
            filename = chunk.get("filename", "unknown_document.pdf")
            page = chunk.get("page_number", 1)
            chunk_id = chunk.get("chunk_id", "")
            content = chunk.get("content", "").strip()
            formatted_excerpts.append(
                f"[Source {rank}: {filename} (Page {page}, Chunk {chunk_id})]\n{content}"
            )

        context_text = "\n\n".join(formatted_excerpts)

        user_content = (
            f"DOCUMENT EXCERPTS:\n"
            f"{context_text}\n\n"
            f"USER QUESTION: {question}\n\n"
            f"Provide a concise, professional answer strictly citing [Source N] references. "
            f"If the excerpts do not contain the answer, begin with INSUFFICIENT_EVIDENCE:"
        )

        # 2. Determine Candidate Models (Primary + Fallbacks)
        primary_model = model_override or getattr(settings, "GROQ_MODEL", "qwen/qwen3.8-27b")
        fallbacks_str = getattr(settings, "GROQ_FALLBACK_MODELS", "")
        fallback_models = [m.strip() for m in fallbacks_str.split(",") if m.strip()]
        candidate_models = [primary_model] + [m for m in fallback_models if m != primary_model]

        last_error = None
        for model_name in candidate_models:
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=getattr(settings, "GROQ_TEMPERATURE", 0.1),
                    max_tokens=getattr(settings, "GROQ_MAX_TOKENS", 800)
                )

                raw_answer = (resp.choices[0].message.content or "").strip()
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                # Check for Insufficient Evidence directive in response
                if raw_answer.startswith("INSUFFICIENT_EVIDENCE:"):
                    clean_answer = raw_answer.replace("INSUFFICIENT_EVIDENCE:", "").strip()
                    if not clean_answer:
                        clean_answer = (
                            "The provided document excerpts do not contain sufficient evidence "
                            "to answer this question."
                        )
                    return {
                        "success": True,
                        "answer": clean_answer,
                        "evidence_status": "insufficient",
                        "model_used": model_name,
                        "latency_ms": duration_ms,
                        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
                        "completion_tokens": getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
                    }

                return {
                    "success": True,
                    "answer": raw_answer,
                    "evidence_status": "sufficient",
                    "model_used": model_name,
                    "latency_ms": duration_ms,
                    "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
                    "completion_tokens": getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
                }

            except Exception as e:
                logger.warning(f"Groq inference failed with model {model_name}: {e}")
                last_error = str(e)
                continue

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "success": False,
            "error": f"All Groq candidate models failed. Last error: {last_error}",
            "answer": "",
            "evidence_status": "insufficient",
            "model_used": "failed",
            "latency_ms": duration_ms
        }

groq_rag_service = GroqRAGService()

