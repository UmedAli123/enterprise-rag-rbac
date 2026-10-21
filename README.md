# Secure Enterprise RAG with Role-Based Access Control (RBAC)
### Nexora Technologies Knowledge Assistant

An enterprise-grade, secure Retrieval-Augmented Generation (RAG) assistant featuring **in-vector access pre-filtering**, **multi-layer security guardrails**, **JWT-governed RBAC**, **comprehensive telemetry**, and an **interactive Streamlit UI**.

---

## 🏗️ System Architecture

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 User / Client Request                  │
                  └───────────────────────────┬────────────────────────────┘
                                              │ 1. POST /chat + JWT Token
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │               FastAPI Gateway & Auth                   │
                  │   - Verifies JWT (Secret HMAC-SHA256)                  │
                  │   - Extracts Role (Employee, HR, Finance, Exec, Admin) │
                  └───────────────────────────┬────────────────────────────┘
                                              │ 2. Role Verified
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │            Layer 1: Input Guardrails                   │
                  │   - Detects prompt injection & role impersonation      │
                  │   - Filters out-of-scope queries (EN & Roman Urdu)     │
                  └───────┬───────────────────────────────────────┬────────┘
             Attack Blocked│                                       │ Query Allowed
                          ▼                                       ▼
                  [Refusal Response]                      [RBAC Mapping]
                                                                  │ 3. Allowed Levels
                                                                  ▼
                                              ┌────────────────────────────────────┐
                                              │    Qdrant Vector Database Engine   │
                                              │  *IN-VECTOR PRE-FILTERING*         │
                                              │  MatchAny(allowed_levels)          │
                                              └───────────────────┬────────────────┘
                                                                  │ 4. Authorized Chunks Only
                                                                  ▼
                                              ┌────────────────────────────────────┐
                                              │     LLM Answer Generation          │
                                              │  Strict context-grounding & doc    │
                                              │  citations [doc_id: section]       │
                                              └───────────────────┬────────────────┘
                                                                  │ 5. Candidate Answer
                                                                  ▼
                                              ┌────────────────────────────────────┐
                                              │    Layer 2: Output Guardrails      │
                                              │  Scans for sensitive token leakage │
                                              └───────────────────┬────────────────┘
                                                                  │ 6. Verified Answer
                                                                  ▼
                                              ┌────────────────────────────────────┐
                                              │    Telemetry & Observability       │
                                              │  Logs query, latency & cost to DB  │
                                              └───────────────────┬────────────────┘
                                                                  │ 7. Return to User
                                                                  ▼
                                              ┌────────────────────────────────────┐
                                              │    Streamlit Chat & Admin UI       │
                                              └────────────────────────────────────┘
```

---

## 🛡️ Core Security Principles

1. **In-Vector Pre-Filtering (Qdrant):**
   Access controls are evaluated *inside* the vector index before cosine similarity search. Unauthorized documents are never retrieved, preventing post-retrieval leakage.
2. **Cryptographic Role Verification:**
   The user's role comes **ONLY from the cryptographically verified JWT token**. It cannot be spoofed through prompts or request body parameters.
3. **Default-Deny Policy:**
   Unauthenticated users or unrecognized access levels retrieve zero documents by default.
4. **Multi-Layer Guardrails:**
   - **Layer 1 (Pre-Retrieval):** Blocks prompt injections, system prompt leak requests, role impersonation, and out-of-scope topics (including Roman Urdu and English).
   - **Layer 2 (Post-Generation):** Distinctive token scanning guarantees that sensitive data (e.g., M&A deal codenames, acquisition prices) never leaks to unauthorized roles.
5. **Zero Data Leakage:**
   Achieved **0.0% access-control leakage** across automated benchmark evaluations.

---

## 👥 Personas & RBAC Access Matrix

| Username | Role | Department | Allowed Levels | Accessible Documents |
| :--- | :--- | :--- | :--- | :--- |
| `emma.employee` | `employee` | Operations | `public` | Company Facts, Annual Leave, Code of Conduct |
| `ethan.engineer` | `engineer` | Engineering | `public`, `engineering` | + System Architecture, Incident Postmortems |
| `fiona.finance` | `finance_analyst`| Finance | `public`, `finance` | + Q3 Budget Reports, Vendor Contracts |
| `harry.hr` | `hr_manager` | Human Resources | `public`, `hr` | + Salary Bands, PIP & Appraisal Guidelines |
| `carla.cfo` | `cfo` | Executive | `public`, `finance`, `executive` | + Project Harbor M&A Acquisition Plan |
| `adam.admin` | `admin` | IT / Security | `*` (All Levels) | Complete Access + Admin Observability |

> **Demo Password:** `nexora123` (configured in `.env` and `app/config.py`).

---

## 📊 Benchmark Evaluation Results

Evaluated across **52 automated benchmark questions** in `eval/test_questions.json`:

| Metric | Target | Actual Result | Status |
| :--- | :---: | :---: | :---: |
| **Access-Control Leakage** | **0.0%** | **0.0%** (0 leaks) | ✅ **PASS** |
| **Guardrail Block Rate** | **$\ge$ 95.0%** | **100.0%** (17/17 attacks blocked) | ✅ **PASS** |
| **False-Block Rate** | **$\le$ 5.0%** | **0.0%** (0/35 legitimate blocked) | ✅ **PASS** |
| **Answer Source Accuracy** | **$\ge$ 80.0%** | **100.0%** (18/18 verified citations) | ✅ **PASS** |
| **Latency (p95 / p50)** | **$<$ 6.0 s** | **29.7 ms / 14.4 ms** | ✅ **PASS** |
| **Average Cost per Query** | **$\le$ $0.010000** | **$0.000006 USD** | ✅ **PASS** |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.12+
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd enterprise-rag-rbac

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

### 3. Initialize Database & Vector Store
```bash
# Seed user accounts into SQLite (users.db)
python scripts/seed_users.py

# Ingest and embed markdown documentation into local Qdrant
python -m app.ingestion
```

### 4. Run Automated Tests
Execute the full test suite (31 tests across all phases):
```bash
PYTHONPATH=. pytest tests/
```

### 5. Run Evaluation Benchmark
Generate `.csv` and interactive `.html` evaluation reports:
```bash
PYTHONPATH=. python -m eval.run --no-ragas --tag benchmark
```

---

## 💻 Running the Application

### Option A: Local Development

1. **Start FastAPI Backend Server:**
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   - Swagger Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - Healthcheck: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

2. **Launch Streamlit Web Interface:**
   In a separate terminal:
   ```bash
   streamlit run ui/streamlit_app.py
   ```
   Open **[http://localhost:8501](http://localhost:8501)** to interact with the assistant, test role switching, and view the Admin Observability Dashboard.

---

### Option B: Docker Compose (Single Command)

Run the entire stack (FastAPI Backend + Streamlit UI) in Docker:
```bash
docker compose up --build
```
- **Streamlit Web UI:** [http://localhost:8501](http://localhost:8501)
- **FastAPI Backend:** [http://localhost:8000](http://localhost:8000)

---

## 📁 Repository Structure

```
enterprise-rag-rbac/
├── app/
│   ├── config.py          # Pydantic environment configuration
│   ├── auth.py            # SQLite user database, password hashing, JWT tokens
│   ├── rbac.py            # Role-to-access-level mapping logic
│   ├── ingestion.py       # Heading-aware chunker, BGE-small embeddings, Qdrant store
│   ├── retrieval.py       # In-vector pre-filtered search (MatchAny)
│   ├── generation.py      # Dual-mode answer generation (Live Gemini / Grounded Mock)
│   ├── guardrails.py      # Input injection defense & output token leakage scanning
│   ├── telemetry.py       # StageTimer, SQLite query logger, token cost & feedback
│   └── main.py            # FastAPI REST application
├── data/
│   ├── access_control.json# Role-to-access mapping definitions
│   ├── users.json         # Initial employee credentials catalog
│   └── nexora_docs/       # Markdown company documentation by access level
│       ├── public/        # Public policies (PUB-001, PUB-002, PUB-003)
│       ├── hr/            # Salary & performance guidelines (HR-001, HR-002)
│       ├── finance/       # Budget reports & vendor contracts (FIN-001, FIN-002)
│       ├── engineering/   # System architecture & postmortems (ENG-001, ENG-002)
│       └── executive/     # M&A acquisition plan (EXE-001)
├── ui/
│   └── streamlit_app.py   # Streamlit chat interface & admin dashboard
├── eval/
│   ├── test_questions.json# 52 benchmark evaluation cases
│   ├── run.py             # Evaluation runner and HTML/CSV report generator
│   └── reports/           # Timestamped evaluation benchmark outputs
├── scripts/
│   ├── seed_users.py      # Seed users database script
│   ├── search_debug.py    # Search diagnostics script
│   └── ask.py             # CLI query tester
├── tests/                 # 31 pytest unit & integration tests
│   ├── test_health.py
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   ├── test_auth_rbac.py
│   ├── test_guardrails.py
│   ├── test_telemetry.py
│   ├── test_eval.py
│   └── test_ui.py
├── Dockerfile             # Container definition
├── docker-compose.yml     # Multi-container orchestration
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # Project documentation
```

---

## 📄 License
MIT License. Developed for enterprise knowledge retrieval and access control research.
