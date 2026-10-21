"""Unit tests for Phase 6 evaluation metrics computation."""

import pytest
from eval.run import compute_summary_metrics


def test_leakage_rate_computation_on_small_fake_result_set():
    """Verify that compute_summary_metrics computes the access-control leakage

    rate correctly on a small fake result set.
    """
    fake_results = [
        {"id": 1, "expected": "answer", "actual_outcome": "answer", "is_leak": False, "passed": True, "latency_ms": 100, "cost_usd": 0.0001},
        {"id": 2, "expected": "deny", "actual_outcome": "deny", "is_leak": False, "passed": True, "latency_ms": 110, "cost_usd": 0.0001},
        {"id": 3, "expected": "deny", "actual_outcome": "answer", "is_leak": True, "passed": False, "latency_ms": 120, "cost_usd": 0.0001},
        {"id": 4, "expected": "answer", "actual_outcome": "answer", "is_leak": False, "passed": True, "latency_ms": 130, "cost_usd": 0.0001},
    ]

    metrics = compute_summary_metrics(fake_results)

    # 1 out of 4 is a leak -> 25.0%
    assert metrics["leakage_count"] == 1
    assert metrics["leakage_rate"] == 25.0


def test_zero_leakage_result_set():
    """Verify zero leakage computation when all cases adhere to access boundaries."""
    fake_clean = [
        {"id": 1, "expected": "answer", "actual_outcome": "answer", "is_leak": False, "passed": True, "source_matched": True, "latency_ms": 50, "cost_usd": 0.00005},
        {"id": 2, "expected": "deny", "actual_outcome": "deny", "is_leak": False, "passed": True, "source_matched": False, "latency_ms": 60, "cost_usd": 0.00005},
        {"id": 3, "expected": "guardrail_block", "actual_outcome": "blocked", "is_leak": False, "passed": True, "source_matched": False, "latency_ms": 10, "cost_usd": 0.0},
    ]

    metrics = compute_summary_metrics(fake_clean)
    assert metrics["leakage_count"] == 0
    assert metrics["leakage_rate"] == 0.0
    assert metrics["guardrail_block_rate"] == 100.0
    assert metrics["false_block_rate"] == 0.0
    assert metrics["source_accuracy_rate"] == 100.0


def test_guardrail_block_and_false_block_rates():
    """Verify guardrail block rate and false-block rate calculations."""
    fake_guardrails = [
        # 2 attacks: 1 blocked, 1 passed through
        {"id": 1, "expected": "guardrail_block", "actual_outcome": "blocked", "is_leak": False},
        {"id": 2, "expected": "guardrail_block", "actual_outcome": "answer", "is_leak": False},
        # 2 legitimate questions: 1 wrongly blocked, 1 answered
        {"id": 3, "expected": "answer", "actual_outcome": "blocked", "is_leak": False},
        {"id": 4, "expected": "answer", "actual_outcome": "answer", "is_leak": False, "source_matched": True},
    ]

    metrics = compute_summary_metrics(fake_guardrails)

    # 1 out of 2 attacks blocked -> 50.0%
    assert metrics["guardrail_block_rate"] == 50.0

    # 1 out of 2 legitimate questions blocked -> 50.0%
    assert metrics["false_block_rate"] == 50.0


def test_empty_results_safe():
    """Empty results list should return 0 values without division by zero."""
    metrics = compute_summary_metrics([])
    assert metrics["total_questions"] == 0
    assert metrics["leakage_rate"] == 0.0
    assert metrics["guardrail_block_rate"] == 100.0
    assert metrics["false_block_rate"] == 0.0
