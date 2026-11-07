import time
import json
import re
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.services.search import search_service
from backend.app.services.groq_service import groq_rag_service

logger = logging.getLogger(__name__)

class Citation:
    def __init__(self, document_id: str, filename: str, page_number: int, snippet: str, chunk_id: str):
        self.document_id = document_id
        self.filename = filename
        self.page_number = page_number
        self.snippet = snippet
        self.chunk_id = chunk_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "page_number": self.page_number,
            "snippet": self.snippet,
            "chunk_id": self.chunk_id
        }

class DocumentQAService:
    def answer_question(
        self,
        question: str,
        db: Session,
        top_k: int = 5,
        doc_type_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        
        # 1. Retrieve supporting evidence chunks using hybrid search
        search_res = search_service.search(
            query=question,
            db=db,
            mode="hybrid",
            top_k=top_k,
            doc_type_filter=doc_type_filter
        )
        
        hits = search_res.get("results", [])
        
        # 2. Check for insufficiency
        # If no hits or top hit has 0 lexical overlap and below relevance threshold
        if not hits or (hits[0].get("lexical_score", 0.0) == 0.0 and hits[0].get("score", 0.0) < 0.25):
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "question": question,
                "answer": "Evidence is insufficient in the indexed documents to answer this question. Please upload relevant documents or refine your search query.",
                "evidence_status": "insufficient",
                "citations": [],
                "provider_used": "deterministic_fallback",
                "latency_ms": duration_ms
            }

        # 3. Extract citations
        citations = []
        context_blocks = []
        for rank, hit in enumerate(hits, start=1):
            citations.append(Citation(
                document_id=hit["document_id"],
                filename=hit["filename"],
                page_number=hit["page_number"],
                snippet=hit["snippet"],
                chunk_id=hit["chunk_id"]
            ).to_dict())
            context_blocks.append(
                f"[Source {rank}: {hit['filename']} (Page {hit['page_number']})]\n{hit['content']}"
            )

        combined_context = "\n\n".join(context_blocks)

        # 4. Synthesize Answer
        # Priority 1: GroqCloud LLM (Ultra-low latency, strict citation grounding)
        if groq_rag_service.is_available() and getattr(settings, "LLM_PROVIDER", "groq") in ["groq", "auto", "default"]:
            try:
                groq_result = groq_rag_service.generate_rag_answer(
                    question=question,
                    context_chunks=hits
                )
                if groq_result.get("success"):
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    return {
                        "question": question,
                        "answer": groq_result["answer"],
                        "evidence_status": groq_result["evidence_status"],
                        "citations": citations if groq_result["evidence_status"] == "sufficient" else [],
                        "provider_used": f"groq ({groq_result['model_used']})",
                        "latency_ms": duration_ms
                    }
                else:
                    logger.warning(f"Groq RAG failed, proceeding to fallback: {groq_result.get('error')}")
            except Exception as e:
                logger.warning(f"Groq RAG exception: {e}")

        # Priority 2: Gemini API (if configured and Groq unavailable)
        if getattr(settings, "GEMINI_API_KEY", ""):
            try:
                import httpx
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                system_prompt = (
                    "You are the DataNexus document intelligence analyst. Answer the user's question based strictly on the provided document excerpts. "
                    "Always cite the sources using [Source N] tags. If the excerpts do not contain the answer, explicitly state that the evidence is insufficient. "
                    "Never hallucinate or assume facts not present in the text."
                )
                payload = {
                    "contents": [{
                        "role": "user",
                        "parts": [
                            {"text": f"{system_prompt}\n\nDOCUMENT EVIDENCE:\n{combined_context}\n\nQUESTION: {question}"}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}
                }
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(gemini_url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        duration_ms = int((time.perf_counter() - start_time) * 1000)
                        return {
                            "question": question,
                            "answer": raw_answer,
                            "evidence_status": "sufficient",
                            "citations": citations,
                            "provider_used": f"gemini ({settings.LLM_MODEL})",
                            "latency_ms": duration_ms
                        }
            except Exception as e:
                # Log and fallback to extractive synthesis
                pass

        # Deterministic Extractive Evidence Synthesis
        answer = self._extractive_synthesize(question, hits)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "question": question,
            "answer": answer,
            "evidence_status": "sufficient" if hits else "insufficient",
            "citations": citations,
            "provider_used": "extractive_evidence_synthesis",
            "latency_ms": duration_ms
        }

    def _extractive_synthesize(self, question: str, hits: List[Dict[str, Any]]) -> str:
        """Deterministic extractive synthesis referencing verified citations."""
        top_hit = hits[0]
        # Identify key extracted sentences matching query words
        q_words = set(re.findall(r"\w+", question.lower()))
        sentences = re.split(r"(?<=[.!?]) +", top_hit["content"])
        relevant_sentences = []
        for s in sentences:
            s_words = set(re.findall(r"\w+", s.lower()))
            overlap = len(q_words.intersection(s_words))
            if overlap > 0:
                relevant_sentences.append((overlap, s.strip()))

        relevant_sentences.sort(key=lambda x: x[0], reverse=True)
        top_sentence = relevant_sentences[0][1] if relevant_sentences else top_hit["content"][:200]

        summary = (
            f"Based on verifiable evidence in **{top_hit['filename']}** (Page {top_hit['page_number']}):\n\n"
            f"> \"{top_sentence}\"\n\n"
            f"Additional supporting references were identified across {len(hits)} indexed segment(s). "
            f"See detailed page citations below."
        )
        return summary

qa_service = DocumentQAService()
