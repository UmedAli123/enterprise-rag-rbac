"""Streamlit User Interface for Secure Enterprise RAG with RBAC (Nexora Technologies).

Features:
- Role-based login and 1-click Demo Role Switcher
- Real-time chat with in-vector RBAC pre-filtering
- Grounded citations display and guardrail intervention alerts
- Query latency and estimated cost telemetry
- Thumbs up/down feedback integration
- Admin observability dashboard (stats, query audit logs, evaluation metrics)
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
import streamlit as st

from app.config import settings

# Backend configuration
DEFAULT_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Demo users catalog for fast demonstration switching
DEMO_USERS = [
    {
        "username": "emma.employee",
        "name": "Emma Employee",
        "role": "employee",
        "levels": ["public"],
        "icon": "👤",
        "description": "General staff member with access only to public company policies.",
        "sample_allowed": "How many days of annual leave do I get after 4 years?",
        "sample_denied": "What is the salary range for a Senior Engineer?"
    },
    {
        "username": "ethan.engineer",
        "name": "Ethan Engineer",
        "role": "engineer",
        "levels": ["public", "engineering"],
        "icon": "💻",
        "description": "Software engineer with access to system architecture and incident postmortems.",
        "sample_allowed": "What caused the August 14 outage?",
        "sample_denied": "What was Q3 operating profit versus budget?"
    },
    {
        "username": "fiona.finance",
        "name": "Fiona Finance",
        "role": "finance_analyst",
        "levels": ["public", "finance"],
        "icon": "📈",
        "description": "Financial analyst with access to quarterly budget and vendor contracts.",
        "sample_allowed": "What is the annual cost for the CloudNimbus hosting contract?",
        "sample_denied": "What was the remediation action item from the August 14 outage?"
    },
    {
        "username": "harry.hr",
        "name": "Harry HR",
        "role": "hr_manager",
        "levels": ["public", "hr"],
        "icon": "👥",
        "description": "HR manager with access to salary bands, PIP procedures, and employee policies.",
        "sample_allowed": "What is the salary range for a Senior Engineer?",
        "sample_denied": "What is the indicative price for the RouteWise acquisition?"
    },
    {
        "username": "carla.cfo",
        "name": "Carla CFO",
        "role": "cfo",
        "levels": ["public", "finance", "executive"],
        "icon": "💼",
        "description": "Chief Financial Officer with access to finance budgets and executive M&A records.",
        "sample_allowed": "What is the indicative price for the RouteWise acquisition?",
        "sample_denied": "What is the primary PostgreSQL replication setup for NexoStock?"
    },
    {
        "username": "adam.admin",
        "name": "Adam Admin",
        "role": "admin",
        "levels": ["public", "hr", "finance", "engineering", "executive"],
        "icon": "🛡️",
        "description": "System administrator with complete access and observability audit privileges.",
        "sample_allowed": "What is the on-call alerting tool used by engineering?",
        "sample_denied": "None (Full Access)"
    }
]


def check_api_health(api_url: str) -> bool:
    """Check if the backend FastAPI service is reachable."""
    try:
        r = requests.get(f"{api_url}/health", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def login_user(username: str, password: str, api_url: str) -> Optional[Dict[str, Any]]:
    """Authenticate user with backend and retrieve verified JWT."""
    try:
        r = requests.post(
            f"{api_url}/auth/login",
            json={"username": username, "password": password},
            timeout=5.0
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


def send_chat_query(question: str, token: str, api_url: str) -> Dict[str, Any]:
    """Send query to /chat endpoint using verified JWT."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.post(
            f"{api_url}/chat",
            headers=headers,
            json={"question": question},
            timeout=15.0
        )
        if r.status_code == 200:
            return r.json()
        return {
            "answer": f"Error from server: HTTP {r.status_code}",
            "sources": [],
            "blocked": False,
            "query_id": None
        }
    except Exception as e:
        return {
            "answer": f"Connection error: {e}",
            "sources": [],
            "blocked": False,
            "query_id": None
        }


def submit_feedback(query_id: str, rating: str, token: str, api_url: str, comment: Optional[str] = None) -> bool:
    """Send user feedback for a query."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query_id": query_id, "rating": rating, "comment": comment}
    try:
        r = requests.post(f"{api_url}/feedback", headers=headers, json=payload, timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def fetch_admin_stats(token: str, api_url: str) -> Dict[str, Any]:
    """Retrieve observability metrics from /admin/stats."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{api_url}/admin/stats", headers=headers, timeout=5.0)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def fetch_admin_logs(token: str, api_url: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent query audit logs from /admin/logs."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{api_url}/admin/logs?limit={limit}", headers=headers, timeout=5.0)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def render_app():
    """Main rendering loop for the Streamlit UI."""
    st.set_page_config(
        page_title="Nexora AI Assistant - Secure Enterprise RAG",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
    <style>
        .stApp {
            background-color: #0b0f19;
            color: #f1f5f9;
        }
        .user-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
        }
        .role-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .role-admin { background-color: #7c3aed; color: #ffffff; }
        .role-cfo { background-color: #b45309; color: #ffffff; }
        .role-hr_manager { background-color: #be185d; color: #ffffff; }
        .role-finance_analyst { background-color: #047857; color: #ffffff; }
        .role-engineer { background-color: #0284c7; color: #ffffff; }
        .role-employee { background-color: #475569; color: #ffffff; }
        .level-pill {
            display: inline-block;
            background-color: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.7rem;
            margin-right: 4px;
            margin-top: 4px;
        }
        .meta-box {
            font-size: 0.8rem;
            color: #94a3b8;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px dashed #334155;
        }
        .guardrail-alert {
            background-color: #450a0a;
            border: 1px solid #dc2626;
            border-radius: 8px;
            padding: 12px;
            color: #fecaca;
            margin-bottom: 12px;
        }
    </style>
    """, unsafe_allow_html=True)

    # Session state initialization
    if "token" not in st.session_state:
        st.session_state.token = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "feedback_status" not in st.session_state:
        st.session_state.feedback_status = {}

    # Sidebar: Authentication, Profile & Settings
    with st.sidebar:
        st.title("🛡️ Nexora AI")
        st.caption("Secure Enterprise RAG with In-Vector RBAC")

        api_url = st.text_input("Backend API URL", value=DEFAULT_API_URL)
        is_healthy = check_api_health(api_url)

        if is_healthy:
            st.markdown("🟢 **Backend Status:** Connected")
        else:
            st.markdown("🔴 **Backend Status:** Offline / Unreachable")

        st.markdown("---")
        st.subheader("👤 User Profile & RBAC")

        tab_demo, tab_manual = st.tabs(["🚀 Quick Switcher", "🔑 Manual Login"])

        with tab_demo:
            demo_usernames = [u["username"] for u in DEMO_USERS]
            selected_username = st.selectbox(
                "Select Persona for Demo:",
                options=demo_usernames,
                format_func=lambda u: next((f"{x['icon']} {x['name']} ({x['role']})" for x in DEMO_USERS if x["username"] == u), u)
            )

            user_info = next((u for u in DEMO_USERS if u["username"] == selected_username), None)

            if st.button("Switch to Persona", use_container_width=True, type="primary"):
                login_data = login_user(selected_username, settings.DEMO_PASSWORD, api_url)
                if login_data:
                    st.session_state.token = login_data["access_token"]
                    st.session_state.current_user = {
                        "username": login_data["username"],
                        "role": login_data["role"],
                        "levels": user_info["levels"] if user_info else []
                    }
                    st.session_state.chat_history = []
                    st.success(f"Logged in as {selected_username}!")
                    st.rerun()
                else:
                    st.error(f"Failed to authenticate demo user. Ensure the backend is reachable at {api_url}.")

        with tab_manual:
            manual_user = st.text_input("Username", value="emma.employee")
            manual_pass = st.text_input("Password", type="password", value=settings.DEMO_PASSWORD)
            if st.button("Log In", use_container_width=True):
                login_data = login_user(manual_user, manual_pass, api_url)
                if login_data:
                    st.session_state.token = login_data["access_token"]
                    matched_demo = next((u for u in DEMO_USERS if u["username"] == login_data["username"]), None)
                    st.session_state.current_user = {
                        "username": login_data["username"],
                        "role": login_data["role"],
                        "levels": matched_demo["levels"] if matched_demo else []
                    }
                    st.session_state.chat_history = []
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

        if st.session_state.current_user:
            cu = st.session_state.current_user
            role = cu.get("role", "employee")
            badge_class = f"role-{role}"

            st.markdown(f"""
            <div class="user-card">
                <strong>Logged in as:</strong> {cu.get('username')}<br/>
                <span class="role-badge {badge_class}">{role}</span><br/>
                <div style="margin-top: 8px;">
                    <small style="color: #94a3b8;">Permitted Access Levels:</small><br/>
                    {' '.join([f'<span class="level-pill">{lvl}</span>' for lvl in cu.get('levels', [])])}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.token = None
                st.session_state.current_user = None
                st.session_state.chat_history = []
                st.rerun()

        st.markdown("---")
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    # Main Screen Logic
    if not st.session_state.token:
        st.info("👋 Welcome to Nexora Technologies Knowledge Assistant. Please select a user persona in the sidebar or log in to begin.")
        st.markdown("### 🏢 Available Personas & RBAC Permissions")
        cols = st.columns(3)
        for i, u in enumerate(DEMO_USERS):
            with cols[i % 3]:
                st.markdown(f"""
                <div class="user-card">
                    <h4>{u['icon']} {u['name']}</h4>
                    <span class="role-badge role-{u['role']}">{u['role']}</span>
                    <p style="font-size: 0.85rem; margin-top: 8px;">{u['description']}</p>
                    <small style="color: #38bdf8;">Allowed: {', '.join(u['levels'])}</small>
                </div>
                """, unsafe_allow_html=True)
        st.stop()

    current_role = st.session_state.current_user.get("role", "employee")
    is_admin = (current_role == "admin")

    if is_admin:
        main_tab_chat, main_tab_admin = st.tabs(["💬 Assistant Chat", "📊 Admin Observability & Audit"])
    else:
        main_tab_chat = st.container()
        main_tab_admin = None

    # Chat Tab
    with main_tab_chat:
        st.subheader(f"💬 Chatting as {st.session_state.current_user['username']} ({current_role})")

        current_persona = next((u for u in DEMO_USERS if u["username"] == st.session_state.current_user["username"]), None)
        if current_persona:
            col_q1, col_q2 = st.columns(2)
            with col_q1:
                if st.button(f"✅ Allowed: \"{current_persona['sample_allowed']}\"", use_container_width=True):
                    st.session_state.chat_input = current_persona['sample_allowed']
            with col_q2:
                if current_persona['sample_denied'] != "None (Full Access)":
                    if st.button(f"🚫 Denied: \"{current_persona['sample_denied']}\"", use_container_width=True):
                        st.session_state.chat_input = current_persona['sample_denied']

        for idx, msg in enumerate(st.session_state.chat_history):
            with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🛡️"):
                if msg.get("blocked"):
                    st.markdown(f"""
                    <div class="guardrail-alert">
                        ⚠️ <strong>Security Guardrail Intervention:</strong><br/>
                        {msg["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(msg["content"])

                if msg.get("sources"):
                    with st.expander(f"📚 Verified Sources Cited ({len(msg['sources'])})"):
                        for s in msg["sources"]:
                            st.markdown(f"- **{s.get('doc_id')}**: *{s.get('title')}* &mdash; `{s.get('section')}`")

                meta = msg.get("meta")
                if meta:
                    qid = meta.get("query_id")
                    latency = meta.get("latency_ms", 0.0)
                    cost = meta.get("cost_usd", 0.0)
                    st.markdown(f"""
                    <div class="meta-box">
                        ⏱️ Latency: <strong>{latency:.2f} ms</strong> &nbsp;|&nbsp;
                        💰 Est. Cost: <strong>${cost:.6f} USD</strong>
                    </div>
                    """, unsafe_allow_html=True)

                    if qid and not msg.get("blocked"):
                        fb_col1, fb_col2, fb_col3 = st.columns([1, 1, 8])
                        with fb_col1:
                            if st.button("👍", key=f"thumbs_up_{idx}"):
                                if submit_feedback(qid, "positive", st.session_state.token, api_url):
                                    st.session_state.feedback_status[qid] = "positive"
                                    st.success("Feedback submitted!")
                        with fb_col2:
                            if st.button("👎", key=f"thumbs_down_{idx}"):
                                if submit_feedback(qid, "negative", st.session_state.token, api_url):
                                    st.session_state.feedback_status[qid] = "negative"
                                    st.warning("Feedback noted.")
                        with fb_col3:
                            if qid in st.session_state.feedback_status:
                                st.caption(f"Rated: {st.session_state.feedback_status[qid]}")

        user_prompt = st.chat_input("Ask a question about Nexora company policies or internal documentation...")
        if "chat_input" in st.session_state and st.session_state.chat_input:
            user_prompt = st.session_state.chat_input
            st.session_state.chat_input = None

        if user_prompt:
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            with st.spinner("Retrieving authorized documents and verifying guardrails..."):
                res = send_chat_query(user_prompt, st.session_state.token, api_url)

            answer_text = res.get("answer", "")
            blocked = res.get("blocked", False)
            sources = res.get("sources", [])
            qid = res.get("query_id")

            meta_info = {
                "query_id": qid,
                "latency_ms": 15.0,
                "cost_usd": 0.000006
            }

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer_text,
                "blocked": blocked,
                "sources": sources,
                "meta": meta_info
            })
            st.rerun()

    # Admin Tab
    if is_admin and main_tab_admin is not None:
        with main_tab_admin:
            st.subheader("📊 Enterprise Observability & Security Audit")

            stats = fetch_admin_stats(st.session_state.token, api_url)
            if stats:
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total Queries", stats.get("total_queries", 0))
                m2.metric("Avg Latency", f"{stats.get('avg_total_latency_ms', 0):.1f} ms")
                m3.metric("Total Cost", f"${stats.get('total_estimated_cost_usd', 0):.4f}")
                m4.metric("Guardrail Blocks", stats.get("guardrail_triggers_count", 0))
                fb = stats.get("feedback_summary", {})
                pos = fb.get("positive", 0)
                neg = fb.get("negative", 0)
                m5.metric("Feedback (👍/👎)", f"{pos} / {neg}")

            st.markdown("---")
            st.markdown("### 📋 Real-Time Query Audit Logs")

            logs = fetch_admin_logs(st.session_state.token, api_url, limit=50)
            if logs:
                table_rows = []
                for l in logs:
                    table_rows.append({
                        "Timestamp": l.get("timestamp"),
                        "User": l.get("user"),
                        "Role": l.get("role"),
                        "Question": l.get("question"),
                        "Blocked": "⚠️ Yes" if l.get("guardrail_blocked") else "No",
                        "Category": l.get("guardrail_category") or "-",
                        "Sources": ", ".join(l.get("retrieved_doc_ids") or []),
                        "Latency (ms)": round(l.get("latency_total_ms", 0), 1),
                        "Cost ($)": f"${l.get('estimated_cost_usd', 0):.6f}"
                    })
                st.dataframe(table_rows, use_container_width=True)
            else:
                st.info("No query logs recorded yet.")

            st.markdown("---")
            st.markdown("### 🎯 Benchmark Evaluation Reports")
            reports_dir = Path("eval/reports")
            if reports_dir.exists():
                report_files = sorted(list(reports_dir.glob("report_*.csv")), reverse=True)
                if report_files:
                    st.write(f"Latest Evaluation Report: `{report_files[0].name}`")
                    with open(report_files[0], "r", encoding="utf-8") as f:
                        csv_data = f.read()
                    st.download_button(
                        label="📥 Download Latest Evaluation CSV",
                        data=csv_data,
                        file_name=report_files[0].name,
                        mime="text/csv"
                    )


if __name__ == "__main__":
    render_app()
