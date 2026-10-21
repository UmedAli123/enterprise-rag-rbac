"""Tests for Phase 3: Login, JWT Authentication, and RBAC Endpoint Isolation."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.rbac import allowed_levels
from scripts.seed_users import seed_users

client = TestClient(app)

# Ensure users are seeded for testing
seed_users()


def test_login_success_and_failure():
    """Login works for all 6 sample users and fails for a wrong password."""
    users_path = Path(settings.DATA_DIR) / "users.json"
    with open(users_path, "r", encoding="utf-8") as f:
        users = json.load(f)

    # 1. Success for all 6 users
    for u in users:
        res = client.post("/auth/login", json={
            "username": u["username"],
            "password": settings.DEMO_PASSWORD
        })
        assert res.status_code == 200, f"Login failed for {u['username']}"
        data = res.json()
        assert "access_token" in data
        assert data["role"] == u["role"]
        assert data["username"] == u["username"]

    # 2. Failure with wrong password
    bad_res = client.post("/auth/login", json={
        "username": "emma.employee",
        "password": "wrongpassword123"
    })
    assert bad_res.status_code == 401


def test_chat_without_token_returns_401():
    """Accessing /chat without a token returns HTTP 401."""
    res = client.post("/chat", json={"question": "What is the leave policy?"})
    assert res.status_code == 401


def test_sending_role_in_body_has_no_effect():
    """Sending a role inside the request body has zero effect;

    the role comes ONLY from the verified JWT token.
    """
    # Login as employee
    login_res = client.post("/auth/login", json={
        "username": "emma.employee",
        "password": settings.DEMO_PASSWORD
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to ask salary with spoofed role in body
    chat_res = client.post(
        "/chat",
        headers=headers,
        json={
            "question": "What is the salary range for a Senior Engineer?",
            "role": "admin"  # Injected role attempt
        }
    )
    assert chat_res.status_code == 200
    data = chat_res.json()
    # Employee must NOT get HR-001
    for s in data["sources"]:
        assert s["doc_id"] != "HR-001", "Spoofed role in body bypassed RBAC!"


def test_rbac_zero_leakage_on_test_questions():
    """For each role, run test cases from eval/test_questions.json and verify

    that every returned doc_id strictly belongs to an allowed access level.
    Zero leakage is the pass condition.
    """
    with open("eval/test_questions.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    # Load doc access mapping from nexora docs
    doc_access_map = {
        "PUB-001": "public",
        "PUB-002": "public",
        "PUB-003": "public",
        "HR-001": "hr",
        "HR-002": "hr",
        "FIN-001": "finance",
        "FIN-002": "finance",
        "ENG-001": "engineering",
        "ENG-002": "engineering",
        "EXE-001": "executive"
    }

    # Cache user tokens
    tokens = {}

    for case in test_cases:
        if case["expected"] not in ("answer", "deny"):
            continue

        username = case["user"]
        if username not in tokens:
            login_res = client.post("/auth/login", json={
                "username": username,
                "password": settings.DEMO_PASSWORD
            })
            assert login_res.status_code == 200
            tokens[username] = login_res.json()

        token = tokens[username]["access_token"]
        user_role = tokens[username]["role"]
        permitted_levels = allowed_levels(user_role)

        res = client.post(
            "/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": case["question"]}
        )
        assert res.status_code == 200
        data = res.json()

        # Check every returned source strictly belongs to permitted_levels
        for src in data["sources"]:
            doc_id = src["doc_id"]
            doc_level = doc_access_map.get(doc_id, "unknown")
            assert doc_level in permitted_levels, (
                f"LEAK DETECTED: User '{username}' (role '{user_role}') retrieved "
                f"doc '{doc_id}' with level '{doc_level}'. Permitted levels: {permitted_levels}"
            )

        # For deny cases, ensure the restricted source document was not cited
        if case["expected"] == "deny":
            assert len(data["sources"]) == 0 or all(
                doc_access_map.get(s["doc_id"]) in permitted_levels for s in data["sources"]
            )


def test_salary_question_comparison_employee_vs_hr():
    """Verify salary question behavior between employee and hr_manager."""
    # Emma (employee)
    emma_login = client.post("/auth/login", json={"username": "emma.employee", "password": settings.DEMO_PASSWORD})
    emma_token = emma_login.json()["access_token"]
    emma_chat = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {emma_token}"},
        json={"question": "What is the salary range for a Senior Engineer?"}
    )
    emma_sources = [s["doc_id"] for s in emma_chat.json()["sources"]]
    assert "HR-001" not in emma_sources

    # Harry (hr_manager)
    harry_login = client.post("/auth/login", json={"username": "harry.hr", "password": settings.DEMO_PASSWORD})
    harry_token = harry_login.json()["access_token"]
    harry_chat = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {harry_token}"},
        json={"question": "What is the salary range for a Senior Engineer?"}
    )
    harry_sources = [s["doc_id"] for s in harry_chat.json()["sources"]]
    assert "HR-001" in harry_sources
