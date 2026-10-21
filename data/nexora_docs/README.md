# Nexora Technologies: Sample Dataset for Enterprise RAG with RBAC

Fake company data for building and testing a role-based RAG assistant. All names, numbers and companies are invented.

## Structure
- `public/`, `hr/`, `finance/`, `engineering/`, `executive/`: 10 documents. Each has YAML front-matter with `access_level` and `doc_id`.
- `access_control.json`: which roles can read which access levels.
- `users.json`: 6 sample users, one per role.
- `test_questions.json`: 18 test cases covering allowed answers, denied access, and guardrail blocks. Use them later as your evaluation set (Ragas / LangSmith).

## How to use
1. Load each document, read the front-matter, and store `access_level` and `doc_id` as metadata on every chunk in the vector database.
2. At query time, get the user's role from the login (never from the question text), look up allowed access levels, and filter retrieval with them.
3. Run input guardrails before retrieval (prompt injection, role claims, out-of-scope topics).
4. Run the test questions and compare against `expected`.
