"""Telemetry, latency timing, token counting, cost estimation, and query logging in SQLite."""

import json
import math
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

DB_PATH = Path("./telemetry.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_telemetry_db():
    """Initialize SQLite query_logs table."""
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                question TEXT NOT NULL,
                allowed_levels TEXT NOT NULL,
                retrieved_doc_ids TEXT NOT NULL,
                cited_doc_ids TEXT NOT NULL,
                guardrail_category TEXT NOT NULL,
                blocked INTEGER NOT NULL,
                answer TEXT NOT NULL,
                latency_retrieval_ms REAL NOT NULL,
                latency_llm_ms REAL NOT NULL,
                latency_total_ms REAL NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL,
                feedback TEXT
            )
        """)
    conn.close()


class StageTimer:
    """Helper context manager to measure latency of individual pipeline stages in milliseconds."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            self.elapsed_ms = round((time.perf_counter() - self.start_time) * 1000, 2)


def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate query cost in USD based on input and output token counts."""
    input_cost = (prompt_tokens / 1_000_000.0) * settings.PRICE_PER_M_INPUT_TOKENS
    output_cost = (completion_tokens / 1_000_000.0) * settings.PRICE_PER_M_OUTPUT_TOKENS
    return round(input_cost + output_cost, 6)


def log_query(
    username: str,
    role: str,
    question: str,
    allowed_levels: List[str],
    retrieved_doc_ids: List[str],
    cited_doc_ids: List[str],
    guardrail_category: str,
    blocked: bool,
    answer: str,
    latency_retrieval_ms: float,
    latency_llm_ms: float,
    latency_total_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: Optional[float] = None,
    feedback: Optional[str] = None,
    query_id: Optional[str] = None
) -> str:
    """Log an execution of /chat to SQLite query_logs table and return query_id."""
    init_telemetry_db()
    qid = query_id or str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()

    if estimated_cost_usd is None:
        estimated_cost_usd = calculate_cost(prompt_tokens, completion_tokens)

    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO query_logs (
                id, timestamp, username, role, question, allowed_levels,
                retrieved_doc_ids, cited_doc_ids, guardrail_category, blocked,
                answer, latency_retrieval_ms, latency_llm_ms, latency_total_ms,
                prompt_tokens, completion_tokens, estimated_cost_usd, feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            qid,
            ts,
            username,
            role,
            question,
            json.dumps(allowed_levels),
            json.dumps(retrieved_doc_ids),
            json.dumps(cited_doc_ids),
            guardrail_category,
            1 if blocked else 0,
            answer,
            round(latency_retrieval_ms, 2),
            round(latency_llm_ms, 2),
            round(latency_total_ms, 2),
            prompt_tokens,
            completion_tokens,
            round(estimated_cost_usd, 6),
            feedback
        ))
    conn.close()
    return qid


def update_feedback(query_id: str, username: str, feedback: str) -> str:
    """Record feedback (thumbs up / thumbs down) for a query.

    Returns:
        "ok" if updated,
        "not_found" if query does not exist,
        "forbidden" if current user does not own the query.
    """
    init_telemetry_db()
    conn = get_db_connection()
    cursor = conn.execute("SELECT username FROM query_logs WHERE id = ?", (query_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "not_found"

    if row["username"] != username:
        conn.close()
        return "forbidden"

    with conn:
        conn.execute("UPDATE query_logs SET feedback = ? WHERE id = ?", (feedback, query_id))
    conn.close()
    return "ok"


def get_logs(
    role: Optional[str] = None,
    blocked: Optional[bool] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Retrieve query logs with optional filtering by role and blocked status."""
    init_telemetry_db()
    conn = get_db_connection()
    query = "SELECT * FROM query_logs"
    conditions = []
    params: List[Any] = []

    if role is not None and role.strip():
        conditions.append("role = ?")
        params.append(role.strip().lower())

    if blocked is not None:
        conditions.append("blocked = ?")
        params.append(1 if blocked else 0)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    logs = []
    for r in rows:
        d = dict(r)
        d["blocked"] = bool(d["blocked"])
        try:
            d["allowed_levels"] = json.loads(d["allowed_levels"])
        except Exception:
            pass
        try:
            d["retrieved_doc_ids"] = json.loads(d["retrieved_doc_ids"])
        except Exception:
            pass
        try:
            d["cited_doc_ids"] = json.loads(d["cited_doc_ids"])
        except Exception:
            pass
        logs.append(d)

    return logs


def get_stats() -> Dict[str, Any]:
    """Compute aggregate telemetry stats."""
    init_telemetry_db()
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM query_logs")
    rows = cursor.fetchall()
    conn.close()

    total_queries = len(rows)
    if total_queries == 0:
        return {
            "total_queries": 0,
            "count_by_role": {},
            "blocked_count": 0,
            "average_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "total_cost_usd": 0.0,
            "average_cost_usd": 0.0
        }

    count_by_role: Dict[str, int] = {}
    blocked_count = 0
    latencies: List[float] = []
    total_cost = 0.0

    for r in rows:
        r_role = r["role"]
        count_by_role[r_role] = count_by_role.get(r_role, 0) + 1
        if r["blocked"]:
            blocked_count += 1
        latencies.append(r["latency_total_ms"])
        total_cost += r["estimated_cost_usd"]

    latencies.sort()
    avg_latency = sum(latencies) / total_queries
    # Compute 95th percentile index
    p95_index = max(0, int(math.ceil(0.95 * total_queries)) - 1)
    p95_latency = latencies[p95_index]
    avg_cost = total_cost / total_queries

    return {
        "total_queries": total_queries,
        "count_by_role": count_by_role,
        "blocked_count": blocked_count,
        "average_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "total_cost_usd": round(total_cost, 6),
        "average_cost_usd": round(avg_cost, 6)
    }