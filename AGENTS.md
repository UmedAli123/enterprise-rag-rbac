Project: Secure Enterprise RAG assistant (fake company: Nexora Technologies).
The full spec is in docs/REQUIREMENTS.md. Read it before every task.

Rules:
- Follow the folder structure in section 14 of the spec.
- The user's role comes ONLY from the verified JWT token. Never from the request body or the question text.
- The access filter must be applied INSIDE the vector search (pre-filtering). Never filter after retrieval or after the LLM answer.
- Default deny: unknown role or access level means no documents.
- Never commit secrets. Use .env and keep .env.example updated.
- Write pytest tests for every phase. Do not say a phase is done until its tests pass.
- Work on one phase at a time. When a phase is done, stop and tell me how to run it and how to verify it.
- Keep code simple and commented. Prefer small functions. No unnecessary dependencies.
