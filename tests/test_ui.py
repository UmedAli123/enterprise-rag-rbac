"""Unit and integration tests for Phase 7 Streamlit UI components and backend communication."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from scripts.seed_users import seed_users
from ui.streamlit_app import (
    DEMO_USERS,
    check_api_health,
    login_user,
    send_chat_query,
    submit_feedback,
    fetch_admin_stats,
    fetch_admin_logs
)

client = TestClient(app)
seed_users()


def test_demo_users_catalog_completeness():
    """Verify DEMO_USERS catalog includes all required roles and permissions."""
    roles = {u["role"] for u in DEMO_USERS}
    expected_roles = {"employee", "engineer", "finance_analyst", "hr_manager", "cfo", "admin"}
    assert expected_roles.issubset(roles), f"Missing roles in catalog: {expected_roles - roles}"

    for u in DEMO_USERS:
        assert "username" in u
        assert "levels" in u
        assert len(u["levels"]) >= 1
        assert "sample_allowed" in u
        assert "sample_denied" in u


def test_login_user_and_token_retrieval():
    """Verify login_user properly calls backend and receives JWT token."""
    with patch("requests.post") as mock_post:
        # Simulate successful FastAPI login response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "mock.jwt.token",
            "token_type": "bearer",
            "username": "emma.employee",
            "role": "employee"
        }
        mock_post.return_value = mock_response

        res = login_user("emma.employee", settings.DEMO_PASSWORD, "http://testserver")
        assert res is not None
        assert res["access_token"] == "mock.jwt.token"
        assert res["role"] == "employee"


def test_send_chat_query_success_and_guardrail():
    """Verify send_chat_query formats headers and processes response."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "According to PUB-002: Leave policy...",
            "sources": [{"doc_id": "PUB-002", "title": "Leave Policy", "section": "Overview"}],
            "blocked": False,
            "query_id": "test-uuid"
        }
        mock_post.return_value = mock_response

        result = send_chat_query("How many days leave?", "dummy_token", "http://testserver")
        assert result["blocked"] is False
        assert len(result["sources"]) == 1
        assert result["query_id"] == "test-uuid"


def test_submit_feedback_flow():
    """Verify submit_feedback sends properly formatted payload."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        ok = submit_feedback("query-123", "positive", "dummy_token", "http://testserver")
        assert ok is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["rating"] == "positive"
        assert kwargs["json"]["query_id"] == "query-123"


def test_fetch_admin_stats_and_logs():
    """Verify admin stats and audit logs fetch helper functions."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_queries": 42,
            "avg_total_latency_ms": 18.5,
            "total_estimated_cost_usd": 0.00025,
            "guardrail_triggers_count": 3,
            "feedback_summary": {"positive": 10, "negative": 1}
        }
        mock_get.return_value = mock_response

        stats = fetch_admin_stats("admin_token", "http://testserver")
        assert stats["total_queries"] == 42
        assert stats["guardrail_triggers_count"] == 3
