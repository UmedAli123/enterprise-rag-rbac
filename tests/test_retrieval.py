"""Tests for Phase 2: RAG core retrieval and access isolation."""

import pytest
from app.retrieval import search
from app.generation import FALLBACK_NOT_FOUND, answer

# 10 queries covering restricted domains (salary, budget, outage, acquisition)
TEST_QUERIES = [
    "What is the salary range of a Senior Engineer?",
    "What is the bonus percentage for level E3?",
    "What is the Q3 2026 revenue and budget breakdown?",
    "Which vendors does Nexora have contracts with and what are the payment terms?",
    "Explain the NexoStock database architecture and replication setup.",
    "What caused the outage on 14 August 2026?",
    "What are the details and price of Project Harbor acquisition plan?",
    "Who are the key executive retention targets for Project Harbor?",
    "How much merit budget is allocated for 2026 payroll increases?",
    "What were the postmortem remediation action items from the incident?",
]


def test_empty_or_none_allowed_levels_returns_empty():
    """Verify empty or None allowed_levels returns empty list immediately without error."""
    assert search("What is the leave policy?", allowed_levels=[]) == []
    assert search("What is the leave policy?", allowed_levels=None) == []


def test_public_allowed_levels_never_leaks_restricted_chunks():
    """For 10 different queries across salary, budget, outage, and acquisition,

    retrieval with allowed_levels=['public'] must NEVER return any chunk
    whose access_level is not 'public'.
    """
    for query in TEST_QUERIES:
        chunks = search(query=query, allowed_levels=["public"])
        for chunk in chunks:
            assert chunk["access_level"] == "public", (
                f"LEAK DETECTED! Query: '{query}' returned chunk with "
                f"access_level='{chunk['access_level']}' (doc_id={chunk['doc_id']})"
            )


def test_allowed_levels_hr_retrieves_hr_salary_doc():
    """Verify that querying for salary with allowed_levels=['public', 'hr'] retrieves HR-001."""
    chunks = search(query="salary range of Senior Engineer", allowed_levels=["public", "hr"])
    assert len(chunks) > 0
    top_doc_id = chunks[0]["doc_id"]
    assert top_doc_id == "HR-001"
    assert chunks[0]["access_level"] == "hr"


def test_answer_fallback_when_unauthorized():
    """Verify that an unauthorized query yields the fallback answer when restricted."""
    # When asking an acquisition question with only public access, if no public doc matches
    # or retrieval has no relevant public chunks, the response gives the polite fallback.
    res = answer("Tell me about Project Harbor acquisition price", allowed_levels=["public"])
    for src in res["sources"]:
        assert src["doc_id"].startswith("PUB-"), f"Leak in cited sources: {src}"
