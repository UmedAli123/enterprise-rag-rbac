"""FastAPI application entrypoint for Secure Enterprise Knowledge Assistant."""

import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import (
    create_access_token,
    get_current_user,
    get_user_by_username,
    init_db,
    verify_password,
)
from app.generation import answer
from app.guardrails import (
    REFUSAL_ACCESS,
    REFUSAL_ATTACK,
    REFUSAL_OUT_OF_SCOPE,
    check_input,
    check_output,
)
from app.rbac import allowed_levels
from app.telemetry import (
    StageTimer,
    get_logs,
    get_stats,
    init_telemetry_db,
    log_query,
    update_feedback,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_telemetry_db()
    yield


app = FastAPI(title="Secure Enterprise Knowledge Assistant API", lifespan=lifespan)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class ChatRequest(BaseModel):
    question: str = Field(..., description="The user query or question")


class SourceItem(BaseModel):
    doc_id: str
    title: str
    section: str


class ChatResponse(BaseModel):
    query_id: str
    answer: str
    sources: List[SourceItem]
    blocked: bool = False
    guardrail_category: str = "ok"


class FeedbackRequest(BaseModel):
    query_id: str
    feedback: str = Field(..., description="User feedback (e.g. thumbs_up, thumbs_down)")


class FeedbackResponse(BaseModel):
    status: str
    query_id: str
    feedback: str


def require_admin(current_user: Dict[str, str] = Depends(get_current_user)) -> Dict[str, str]:
    """Dependency that ensures only users with role 'admin' can access admin endpoints."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required",
        )
    return current_user


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"username": user["username"], "role": user["role"]})
    return LoginResponse(
        access_token=token,
        role=user["role"],
        username=user["username"]
    )


@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    current_user: Dict[str, str] = Depends(get_current_user)
):
    query_id = str(uuid.uuid4())
    username = current_user.get("username", "anonymous")
    user_role = current_user.get("role", "")
    levels = allowed_levels(user_role)

    total_timer = StageTimer()
    with total_timer:
        # 1. Input Guardrails Check
        input_check = check_input(question=req.question, user=username)
        if not input_check["allowed"]:
            category = input_check["category"]
            if category in ("prompt_injection", "role_impersonation", "system_prompt_request"):
                refusal_text = REFUSAL_ATTACK
            elif category == "out_of_scope":
                refusal_text = REFUSAL_OUT_OF_SCOPE
            else:
                refusal_text = REFUSAL_ATTACK

            # Ensure timer stops before logging
            total_timer.__exit__(None, None, None)

            log_query(
                username=username,
                role=user_role,
                question=req.question,
                allowed_levels=levels,
                retrieved_doc_ids=[],
                cited_doc_ids=[],
                guardrail_category=category,
                blocked=True,
                answer=refusal_text,
                latency_retrieval_ms=0.0,
                latency_llm_ms=0.0,
                latency_total_ms=total_timer.elapsed_ms,
                prompt_tokens=0,
                completion_tokens=0,
                query_id=query_id
            )

            return ChatResponse(
                query_id=query_id,
                answer=refusal_text,
                sources=[],
                blocked=True,
                guardrail_category=category
            )

        # 2. Friendly greeting handling (no retrieval needed)
        if input_check.get("is_greeting"):
            greeting_text = "Hello! I am your Secure Enterprise Knowledge Assistant. How can I help you today?"
            total_timer.__exit__(None, None, None)

            log_query(
                username=username,
                role=user_role,
                question=req.question,
                allowed_levels=levels,
                retrieved_doc_ids=[],
                cited_doc_ids=[],
                guardrail_category="ok",
                blocked=False,
                answer=greeting_text,
                latency_retrieval_ms=0.0,
                latency_llm_ms=0.0,
                latency_total_ms=total_timer.elapsed_ms,
                prompt_tokens=max(1, int(len(req.question.split()) * 1.3)),
                completion_tokens=15,
                query_id=query_id
            )

            return ChatResponse(
                query_id=query_id,
                answer=greeting_text,
                sources=[],
                blocked=False,
                guardrail_category="ok"
            )

        # 3. Retrieve and Generate Answer with RBAC Pre-filtering
        result = answer(question=req.question, allowed_levels=levels)

        raw_answer = result.get("answer", "")
        sources = result.get("sources", [])
        retrieved_chunks = result.get("retrieved_chunks", [])

        retrieved_doc_ids = list(dict.fromkeys([c.get("doc_id") for c in retrieved_chunks if c.get("doc_id")]))
        cited_doc_ids = list(dict.fromkeys([s.get("doc_id") for s in sources if s.get("doc_id")]))

        lat_retrieval = result.get("latency_retrieval_ms", 0.0)
        lat_llm = result.get("latency_llm_ms", 0.0)
        p_tokens = result.get("prompt_tokens", 0)
        c_tokens = result.get("completion_tokens", 0)

        # 4. Output Guardrail Check (Source check & distinctive tokens)
        output_check = check_output(
            answer_text=raw_answer,
            sources=sources,
            allowed_levels=levels,
            user=username
        )

        total_timer.__exit__(None, None, None)

        if not output_check["allowed"]:
            log_query(
                username=username,
                role=user_role,
                question=req.question,
                allowed_levels=levels,
                retrieved_doc_ids=retrieved_doc_ids,
                cited_doc_ids=cited_doc_ids,
                guardrail_category="output_leakage",
                blocked=True,
                answer=REFUSAL_ACCESS,
                latency_retrieval_ms=lat_retrieval,
                latency_llm_ms=lat_llm,
                latency_total_ms=total_timer.elapsed_ms,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                query_id=query_id
            )

            return ChatResponse(
                query_id=query_id,
                answer=REFUSAL_ACCESS,
                sources=[],
                blocked=True,
                guardrail_category="output_leakage"
            )

        # Successful normal response
        log_query(
            username=username,
            role=user_role,
            question=req.question,
            allowed_levels=levels,
            retrieved_doc_ids=retrieved_doc_ids,
            cited_doc_ids=cited_doc_ids,
            guardrail_category="ok",
            blocked=False,
            answer=raw_answer,
            latency_retrieval_ms=lat_retrieval,
            latency_llm_ms=lat_llm,
            latency_total_ms=total_timer.elapsed_ms,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            query_id=query_id
        )

        return ChatResponse(
            query_id=query_id,
            answer=raw_answer,
            sources=[SourceItem(**s) for s in sources],
            blocked=False,
            guardrail_category="ok"
        )


@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    req: FeedbackRequest,
    current_user: Dict[str, str] = Depends(get_current_user)
):
    status_res = update_feedback(
        query_id=req.query_id,
        username=current_user["username"],
        feedback=req.feedback
    )
    if status_res == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query log not found"
        )
    elif status_res == "forbidden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only submit feedback for your own queries"
        )

    return FeedbackResponse(
        status="ok",
        query_id=req.query_id,
        feedback=req.feedback
    )


@app.get("/admin/logs")
def admin_logs(
    role: Optional[str] = None,
    blocked: Optional[bool] = None,
    limit: int = 100,
    admin_user: Dict[str, str] = Depends(require_admin)
):
    return get_logs(role=role, blocked=blocked, limit=limit)


@app.get("/admin/stats")
def admin_stats(admin_user: Dict[str, str] = Depends(require_admin)):
    return get_stats()
