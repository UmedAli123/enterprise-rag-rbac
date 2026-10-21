"""LLM prompt construction and answer generation using Gemini with context grounding."""

import logging
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.retrieval import search
from app.telemetry import StageTimer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Secure Enterprise Knowledge Assistant for Nexora Technologies.
Follow these strict rules:
1. Answer the user's question ONLY using the provided context.
2. If the context does not contain the answer, say exactly:
   "I could not find the answer in the documents available to you."
3. Do not guess, speculate, or use outside knowledge.
4. Cite the doc_id (and section if applicable) for each fact mentioned.
5. Keep the answer concise and direct.
6. Reply in the same language as the question.
"""

FALLBACK_NOT_FOUND = "I could not find the answer in the documents available to you."


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a structured context string for the prompt."""
    context_blocks = []
    for idx, c in enumerate(chunks, 1):
        block = (
            f"[Source {idx}] doc_id: {c.get('doc_id')} | title: {c.get('title')} | "
            f"section: {c.get('section')}\n{c.get('text')}"
        )
        context_blocks.append(block)
    return "\n\n---\n\n".join(context_blocks)


def answer(question: str, allowed_levels: List[str]) -> Dict[str, Any]:
    """Retrieve allowed documents and generate grounded answer.

    Args:
        question: User's query.
        allowed_levels: Permitted access levels.

    Returns:
        Dict with keys:
            - answer: generated string
            - sources: list of dicts with doc_id, title, section
            - retrieved_chunks: list of raw chunk dicts
            - latency_retrieval_ms: retrieval latency
            - latency_llm_ms: LLM generation latency
            - prompt_tokens: input tokens count
            - completion_tokens: output tokens count
    """
    # 1. Retrieve pre-filtered chunks with timing
    retrieval_timer = StageTimer()
    with retrieval_timer:
        raw_chunks = search(query=question, allowed_levels=allowed_levels)
        # Filter chunks by relevance score to prevent hallucination on unrelated queries (FR-4)
        retrieved_chunks = [c for c in raw_chunks if c.get("score", 0.0) >= 0.578]

    # 2. If no chunks found, return polite fallback immediately without invoking LLM
    if not retrieved_chunks:
        return {
            "answer": FALLBACK_NOT_FOUND,
            "sources": [],
            "retrieved_chunks": [],
            "latency_retrieval_ms": retrieval_timer.elapsed_ms,
            "latency_llm_ms": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }

    # Extract sources list
    sources = []
    seen = set()
    for c in retrieved_chunks:
        key = (c.get("doc_id"), c.get("title"), c.get("section"))
        if key not in seen:
            seen.add(key)
            sources.append({
                "doc_id": c.get("doc_id"),
                "title": c.get("title"),
                "section": c.get("section")
            })

    # 3. Check for API key
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        # In mock/offline mode when key is not configured, synthesize direct grounded answer from context
        # Verify that key terms from the question appear in the retrieved context
        question_terms = set(re.findall(r"\b[a-zA-Z]{4,}\b", question.lower())) - {
            "what", "when", "where", "which", "whom", "this", "that", "there", "their",
            "have", "from", "with", "about", "company", "policy", "procedure", "does",
            "will", "would", "could", "should", "tell", "give", "much", "many", "please",
            "according", "know", "need", "like", "information", "details"
        }

        def term_in_text(term: str, text: str) -> bool:
            if term in text:
                return True
            root = term.rstrip("s")
            if len(root) >= 4 and root in text:
                return True
            if term.endswith("ing") and len(term) > 5 and term[:-3] in text:
                return True
            return False

        best_chunk = retrieved_chunks[0]
        best_matches: List[str] = []
        for c in retrieved_chunks:
            c_text = (c.get("text", "") + " " + c.get("section", "")).lower()
            c_matches = [w for w in question_terms if term_in_text(w, c_text)]
            if len(c_matches) > len(best_matches):
                best_matches = c_matches
                best_chunk = c

        is_roman_urdu = bool(re.search(r"\b(hai|hain|kya|mutabiq|kitni|saal|chhutti|chhutiyan|batao|dikhao|karo|jao)\b", question.lower()))

        insufficient_grounding = False
        if question_terms:
            if is_roman_urdu or len(question_terms) <= 2:
                insufficient_grounding = (len(best_matches) < 1)
            else:
                insufficient_grounding = (len(best_matches) < 2) or (len(best_matches) / len(question_terms) < 0.35)

        if insufficient_grounding:
            return {
                "answer": FALLBACK_NOT_FOUND,
                "sources": [],
                "retrieved_chunks": [],
                "latency_retrieval_ms": retrieval_timer.elapsed_ms,
                "latency_llm_ms": 0.0,
                "prompt_tokens": max(1, int(len(question.split()) * 1.3)),
                "completion_tokens": 15
            }

        top_chunk = best_chunk
        summary_ans = (
            f"According to [{top_chunk.get('doc_id')}: {top_chunk.get('section')}]: "
            f"{top_chunk.get('text')[:300].strip()}..."
        )
        return {
            "answer": summary_ans,
            "sources": sources,
            "retrieved_chunks": retrieved_chunks,
            "latency_retrieval_ms": retrieval_timer.elapsed_ms,
            "latency_llm_ms": 0.0,
            "prompt_tokens": max(1, int(len(question.split()) * 1.3)),
            "completion_tokens": max(1, int(len(summary_ans.split()) * 1.3))
        }

    # 4. Generate answer via Gemini with timing and token usage extraction
    llm_timer = StageTimer()
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.0
        )
        context_str = format_context(retrieved_chunks)
        user_message = f"Context:\n{context_str}\n\nQuestion: {question}"

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message)
        ]

        with llm_timer:
            response = llm.invoke(messages)

        generated_answer = response.content.strip() if hasattr(response, "content") else str(response)

        usage = (
            getattr(response, "usage_metadata", None)
            or getattr(response, "response_metadata", {}).get("usage_metadata")
            or getattr(response, "response_metadata", {}).get("token_usage")
            or {}
        )
        prompt_tokens = (
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or usage.get("prompt_token_count")
            or max(1, int(len(user_message.split()) * 1.3))
        )
        completion_tokens = (
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or usage.get("candidates_token_count")
            or max(1, int(len(generated_answer.split()) * 1.3))
        )

        return {
            "answer": generated_answer,
            "sources": sources,
            "retrieved_chunks": retrieved_chunks,
            "latency_retrieval_ms": retrieval_timer.elapsed_ms,
            "latency_llm_ms": llm_timer.elapsed_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens
        }
    except Exception as e:
        logger.error("Error generating answer from Gemini: %s", e)
        return {
            "answer": f"Error communicating with AI model: {e}",
            "sources": sources,
            "retrieved_chunks": retrieved_chunks,
            "latency_retrieval_ms": retrieval_timer.elapsed_ms,
            "latency_llm_ms": llm_timer.elapsed_ms,
            "prompt_tokens": max(1, int(len(question.split()) * 1.3)),
            "completion_tokens": 10
        }
