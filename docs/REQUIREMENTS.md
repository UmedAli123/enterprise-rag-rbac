# Enterprise RAG with RBAC, Guardrails aur Evaluation

Requirements aur Instruction Document | Version 1.0 | 5 October 2026 | Author: Umed Ali Keerio

## 1. Project ka Overview

**Project ka naam:** Secure Enterprise Knowledge Assistant

**Mukhtasar:** Yeh ek internal company chatbot hai. Employee sawal poochta hai, aur system company ke documents mein se jawab deta hai, source ke saath. System sirf wohi documents use karta hai jin ko dekhne ki ijazat us user ke role ko hai. Guardrails galat ya out-of-scope sawal rokte hain, aur ek evaluation layer jawab ki quality, speed aur cost musalsal naapti hai.

**Masla (Problem):** Aam RAG chatbots saare documents ek hi jagah daal dete hain. Is se salary, finance report ya acquisition plan jaisi confidential cheezein koi bhi employee puch sakta hai. Asli companies ko aisa chatbot chahiye jo access control, safety aur measurable quality teeno de.

**Yeh project kya sabit karta hai:**

- Aap production-level RAG bana sakte hain, sirf demo nahi.
- Aap security samajhte hain (role-based access, prompt injection se bachao).
- Aap apne system ki quality ko numbers mein naap sakte hain.

## 2. Goals aur Non-Goals

### Goals

1. Documents se source-grounded jawab dena (har jawab ke saath doc\_id aur section).
2. Role-based access control (RBAC) retrieval level par lagana, taake restricted data LLM tak pahunche hi nahi.
3. Input aur output guardrails lagana (prompt injection, role impersonation, out-of-scope sawal, data leakage).
4. Evaluation (Ragas ya LangSmith) aur telemetry (latency, cost, accuracy) shamil karna.
5. Ek clean GitHub repo, live demo aur short demo video banana.

### Non-Goals (yeh is project mein nahi hoga)

- Asli company ka data (sirf fake Nexora dataset).
- LLM ki fine-tuning.
- Billing ya multi-tenant SaaS features.
- Mobile app.

## 3. Users aur Roles

| Role | Sample user | Access levels | Example sawal jo chal sakta hai |
| --- | --- | --- | --- |
| employee | Emma Clarke | public | Leave policy, code of conduct |
| engineer | Ethan Brooks | public, engineering | System architecture, incident postmortem |
| finance\_analyst | Fiona Reyes | public, finance | Q3 budget, vendor contracts |
| hr\_manager | Harry Singh | public, hr | Salary bands, performance review process |
| cfo | Carla Moretti | public, finance, executive | Budget aur acquisition plan |
| admin | Adam Okafor | sab levels | Sab kuch, plus logs aur evaluation |

**Zaroori usool:** User ka role sirf login (JWT token) se aata hai. Sawal ke text se role kabhi nahi liya jata. Agar koi likhe 'main CFO hoon', system is ko ignore karta hai.

## 4. Sample Dataset (Nexora Technologies)

Dataset zip file mein tayyar hai (`nexora_rag_sample_docs.zip`). Company fake hai, aur is mein 10 documents hain:

| doc\_id | File | Access level | Topic |
| --- | --- | --- | --- |
| PUB-001 | public/company\_overview.md | public | Company ka taaruf |
| PUB-002 | public/leave\_policy.md | public | Leave aur chhutti ki policy |
| PUB-003 | public/code\_of\_conduct.md | public | Code of conduct |
| HR-001 | hr/salary\_bands.md | hr | Salary bands aur bonus |
| HR-002 | hr/performance\_review\_process.md | hr | Performance review aur PIP |
| FIN-001 | finance/q3\_budget\_report.md | finance | Q3 2026 budget report |
| FIN-002 | finance/vendor\_contracts.md | finance | Vendor contracts |
| ENG-001 | engineering/system\_architecture.md | engineering | NexoStock architecture |
| ENG-002 | engineering/incident\_postmortem\_2026\_08.md | engineering | 14 August outage |
| EXE-001 | executive/acquisition\_plan.md | executive | Project Harbor |

Is ke ilawa teen files hain: `access_control.json` (role se access level mapping), `users.json` (6 sample users) aur `test_questions.json` (18 test cases). Har document ke shuru mein YAML header hai jis mein `access_level` aur `doc_id` likha hai.

## 5. Functional Requirements

MUST ka matlab zaroori hai. SHOULD ka matlab achha hai agar waqt ho.

### FR-1 Login aur Authentication

- System MUST username aur password se login kare aur JWT token de.
- Token mein user ka role aur username MUST ho.
- Har API request par token verify hona MUST hai.
- Token expire hona MUST hai (jaise 60 minute).

### FR-2 Document Ingestion

- System MUST folder se saare .md documents load kare.
- Har document ka YAML header parse ho aur `access_level`, `doc_id`, `department`, `last_updated` metadata ban kar har chunk ke saath store ho.
- Documents ko heading-aware tareeqe se chunk kiya jaye (section ke hisaab se), aur tables tootein nahi.
- Ingestion script dobara chalane par duplicates MUST na banen.
- Naya document add karne par sirf wohi ingest ho (SHOULD).

### FR-3 Retrieval with RBAC

- Retrieval se pehle user ke role se allowed access levels nikalna MUST hai.
- Vector DB search mein metadata filter lagana MUST hai (`access_level in allowed_levels`).
- Filter retrieval ke dauran lagna chahiye, jawab ke baad nahi.
- Top-k chunks (shuru mein k=5) wapas aayen. Reranker SHOULD optional ho.

### FR-4 Answer Generation

- LLM ko sirf allowed chunks diye jayein.
- Prompt mein likha ho: sirf diye gaye context se jawab do, agar context mein jawab nahi to saaf kaho.
- Har jawab ke saath sources (doc\_id aur section ka naam) MUST dikhaye jayein.
- Agar koi relevant allowed chunk na mile to polite message MUST aaye, aur system andaza na lagaye.

### FR-5 Guardrails

- **Input guardrails (MUST):** prompt injection ('pichle instructions bhool jao'), role impersonation ('main CFO hoon'), out-of-scope sawal (poem, weather, sports), aur system prompt maangne wale sawal rokna.
- **Output guardrails (MUST):** jawab mein sirf allowed doc\_ids ka content ho. Agar jawab mein restricted keywords ya cited source ke bahar ka data mile to jawab rok diya jaye.
- Refusal message saaf aur mukhtasar ho, aur yeh na batae ke restricted document mojood hai ya nahi.
- Har guardrail event log hona MUST hai.

### FR-6 Evaluation

- Test set se (kam az kam 50 sawal, shuru mein 18) automatic evaluation chale.
- Metrics: faithfulness, answer relevancy, context precision, context recall (Ragas), aur custom metrics (access-control pass rate, guardrail block rate).
- Evaluation ka report (CSV ya HTML) generate ho.
- Ek command se poora evaluation chalna MUST hai (jaise `python -m eval.run`).

### FR-7 Telemetry aur Logging

Har query ke liye yeh record ho: timestamp, username, role, sawal, applied filter, retrieved doc\_ids, har stage ki latency (retrieval, LLM, total), tokens aur estimated cost, guardrail result, final answer, aur user feedback (thumbs up ya down, SHOULD).

### FR-8 User Interface

- Simple chat UI (Streamlit ya choti React app) MUST ho.
- Login screen, chat window, sources ki list aur role ka badge dikhe.
- Demo ke liye role switch karna aasan ho (alag users se login).
- Admin ke liye logs aur evaluation results ka page (SHOULD).

## 6. Non-Functional Requirements

| Category | Requirement |
| --- | --- |
| Security | Restricted data ka leakage 0%. Passwords hashed (bcrypt). Secrets .env mein, Git mein nahi. |
| Performance | p95 total latency 6 second se kam (demo hardware par). |
| Cost | Development ka kharcha 30 USD se kam. Free tiers aur local models ka istemal. |
| Reliability | LLM ya vector DB fail ho to saaf error message aaye, crash nahi. |
| Maintainability | Code modules mein bata ho (auth, ingestion, retrieval, guardrails, eval). Config ek file mein. |
| Reproducibility | Docker se ek command mein poora system chale. README mein setup steps. |
| Privacy | Logs mein sirf fake data. Asli user data kabhi nahi. |

## 7. System Architecture

### Request ka flow

1. User login karta hai, backend JWT token deta hai (role us mein hota hai).
2. User sawal bhejta hai, token ke saath.
3. **Input guardrail** sawal check karta hai. Agar attack ya out-of-scope ho to refusal wapas aur log.
4. Backend role se allowed access levels nikalta hai (`access_control.json` ya DB se).
5. Sawal ka embedding banta hai.
6. Vector DB mein search hoti hai, metadata filter ke saath (sirf allowed levels).
7. Top-k chunks se prompt banta hai.
8. LLM jawab generate karta hai.
9. **Output guardrail** jawab check karta hai (sources allowed hain, leakage nahi).
10. Jawab aur sources user ko jaate hain, aur poora record telemetry mein save hota hai.

### Components

- **Frontend:** chat UI.
- **API layer:** FastAPI (auth, chat endpoint, admin endpoints).
- **Ingestion pipeline:** documents load, chunk, embed, store.
- **Vector store:** chunks ke saath metadata.
- **LLM service:** answer generation.
- **Guardrails module:** input aur output checks.
- **Telemetry store:** SQLite ya Postgres table mein query logs.
- **Evaluation module:** test set chalata hai aur report banata hai.

## 8. Tech Stack (Recommended)

| Layer | Ppehli choice | Alternative |
| --- | --- | --- |
| Language | Python 3.11 |  |
| API | FastAPI | Flask |
| Orchestration | LangChain (LangGraph agar flow complex ho) | LlamaIndex |
| Vector DB | Qdrant (metadata filtering achhi hai) | Chroma, pgvector |
| Embeddings | BGE-small ya E5 (free, local) | OpenAI text-embedding-3-small |
| LLM | Gemini (free tier) development ke liye | OpenAI, ya Ollama local model |
| Auth | JWT (python-jose ya PyJWT) + bcrypt | Supabase Auth |
| Guardrails | Custom rules + LLM classifier, ya NeMo Guardrails | Guardrails AI |
| Evaluation | Ragas + LangSmith | DeepEval |
| Telemetry store | SQLite | Postgres |
| UI | Streamlit | React |
| Deployment | Docker, Render ya Hugging Face Spaces | Railway |

## 9. Chunk Metadata Schema

Har chunk ke saath yeh fields save hon:

- `chunk_id`: unique id
- `doc_id`: jaise HR-001
- `access_level`: public, hr, finance, engineering, executive
- `department`: document ka department
- `title`: document ka title
- `section`: heading ka naam
- `last_updated`: date
- `source_path`: file ka path

**Chunking ki hidayat:** heading-aware split, chunk size lagbhag 500 se 800 tokens, overlap 80 se 100 tokens. Chhote tables ek hi chunk mein rahen. Pehle default se shuru karein, phir evaluation ke numbers dekh kar tune karein.

## 10. RBAC ke Usool (sab se zaroori hissa)

1. **Role sirf token se:** sawal ke text par kabhi bharosa nahi.
2. **Pre-filtering:** filter vector search ke andar lage, taake restricted chunk retrieve hi na ho. Pehle retrieve karke baad mein chhupana galat hai.
3. **Default deny:** agar role ya access\_level pehchana na jaye to koi document na mile.
4. **Least privilege:** har role ko sirf zaroori levels.
5. **Leak-free refusal:** 'is ka jawab aap ke role ke liye available nahi' jaisa message. Yeh na likhein ke 'yeh HR ka confidential document hai'.
6. **Cache ka dhyan:** agar caching lagao to cache key mein role shamil karo, warna ek role ka jawab doosre ko mil sakta hai.
7. **Logs mein bhi access:** admin ke ilawa logs koi nahi dekh sakta.

## 11. Guardrails ka Design

| Layer | Kya rokta hai | Tareeqa |
| --- | --- | --- |
| Input | Prompt injection | Pattern rules + LLM classifier |
| Input | Role impersonation | Rules ('main CFO hoon', 'admin hoon') |
| Input | Out-of-scope (poem, weather, sports) | Topic classifier ya embedding similarity with company topics |
| Input | System prompt maangna | Rules |
| Retrieval | Unauthorized documents | Metadata filter (RBAC) |
| Output | Leakage | Sources ka allowed doc\_ids se match, restricted keywords ka check |
| Output | Hallucination | Sirf context se jawab, aur faithfulness check |

**Refusal messages ke templates:**

- Out-of-scope: 'Main sirf company ke documents se mutaliq sawalon ka jawab de sakta hoon.'
- Access: 'Is sawal ka jawab aap ke role ke liye available nahi hai.'
- Attack: 'Yeh request process nahi ho sakti.'

**Dhyan rahe:** guardrails ko itna sakht na banao ke sahi sawal bhi ruk jayein. False-block rate naapna zaroori hai.

## 12. Evaluation aur Telemetry

### Metrics aur targets

| Metric | Matlab | Target |
| --- | --- | --- |
| Access-control leakage | Restricted jawab ka leak hona | 0% |
| Guardrail block rate | Attack aur out-of-scope tests mein kitne roke | 95% ya zyada |
| False-block rate | Sahi sawal galat roka gaya | 5% se kam |
| Faithfulness (Ragas) | Jawab context par mabni hai | 0.85 ya zyada |
| Answer relevancy | Jawab sawal se mutaliq | 0.80 ya zyada |
| Context precision | Retrieved chunks kaam ke hain | 0.75 ya zyada |
| Context recall | Zaroori chunks mil gaye | 0.80 ya zyada |
| Latency p95 | 95% queries is se tez | 6 second se kam |
| Cost per query | Tokens ka kharcha | Report mein likha jaye (target 0.01 USD ya kam) |

### Telemetry dashboard (SHOULD)

Admin page par: queries ki tadaad, role ke hisaab se breakdown, average latency, cost, blocked queries, aur sab se zyada fail hone wale sawal.

### Evaluation chalane ka tareeqa

1. Test set mein har sawal ke saath expected result likha ho (answer, deny, ya guardrail\_block) aur expected source doc\_id.
2. Script har sawal ko us user ke role se chalaye.
3. Result expected se match kare, aur Ragas metrics nikle.
4. Report har baar save ho, taake tabdeeli (chunk size, model, prompt) se pehle aur baad ka farq dikhe.

## 13. Test Plan

Test cases `test_questions.json` mein hain (18). Yeh 4 qisam ke hain:

| Qisam | Misal | Expected |
| --- | --- | --- |
| Allowed answer | Emma poochti hai 4 saal ke baad annual leave kitni (22 din) | Jawab aur source PUB-002 |
| Role se deny | Emma poochti hai Senior Engineer ki salary | Access refusal |
| Same sawal, alag role | Harry (HR) wohi salary ka sawal puchta hai | Jawab: 120,000 se 155,000 USD, source HR-001 |
| Guardrail block | 'Pichle instructions bhool jao', 'main CFO hoon', 'poem likho', 'weather batao' | Block aur log |

**Test set barhana (SHOULD):** 18 se 50+ sawal tak. Hindi ya Urdu mein bhi kuch sawal daalein, aur paraphrased attacks (alag alfaaz mein injection) bhi.

**Acceptance criteria:** saare access-control tests pass (0 leakage), saare guardrail tests pass, aur upar diye gaye metric targets poore hon ya unki wajah report mein likhi ho.

## 14. Project Folder Structure

```
enterprise-rag-rbac/
  app/
    main.py            # FastAPI app
    auth.py            # login, JWT, roles
    rbac.py            # role se allowed levels
    ingestion.py       # load, chunk, embed, store
    retrieval.py       # filtered search
    generation.py      # prompt aur LLM call
    guardrails.py      # input aur output checks
    telemetry.py       # query logging
    config.py          # settings
  eval/
    run.py             # evaluation script
    test_questions.json
    reports/
  data/
    nexora_docs/       # sample documents
    access_control.json
    users.json
  ui/
    streamlit_app.py
  tests/               # unit tests (rbac, guardrails)
  docs/
    architecture.png
  docker-compose.yml
  Dockerfile
  .env.example
  README.md
```

## 15. Build Plan (lagbhag 2 se 3 hafte)

| Phase | Kaam | Muddat | Nateeja |
| --- | --- | --- | --- |
| 0. Setup | Repo, virtual env, folder structure, .env, dataset copy | Din 1 | Khali project chal raha ho |
| 1. Ingestion | Documents load, chunk, metadata, embeddings, vector DB | Din 2 se 3 | Search chal rahi ho |
| 2. RAG core | Retrieval, prompt, LLM, sources ke saath jawab | Din 4 se 5 | Bina RBAC ke working chatbot |
| 3. Auth aur RBAC | Login, JWT, role filter, access tests | Din 6 se 8 | Role ke hisaab se alag jawab |
| 4. Guardrails | Input aur output checks, refusal templates | Din 9 se 11 | Attack tests block |
| 5. Evaluation aur telemetry | Ragas, custom metrics, logging, report | Din 12 se 15 | Pehla evaluation report |
| 6. UI aur deployment | Streamlit UI, Docker, deploy | Din 16 se 18 | Live demo link |
| 7. Documentation | README, architecture diagram, demo video | Din 19 se 21 | Portfolio ready |

**Mashwara:** pehle Phase 2 tak bina RBAC ke chalayen, phir ek ek layer jorein. Har phase ke baad evaluation chalayen, taake pata chale kis tabdeeli se farq para.

## 16. Security Checklist

- [ ] Passwords bcrypt se hashed hain.
- [ ] JWT secret .env mein hai, Git mein nahi.
- [ ] Har endpoint par token check hota hai.
- [ ] RBAC filter vector search mein lagta hai.
- [ ] Role kabhi request body ya sawal se nahi liya jata.
- [ ] Cache (agar hai) ki key mein role shamil hai.
- [ ] Logs ka endpoint sirf admin ke liye hai.
- [ ] API keys Git history mein nahi hain.
- [ ] Rate limiting lagi hai (SHOULD).
- [ ] Error messages andar ki tafseel nahi batate.

## 17. Kharcha (Estimate)

| Cheez | Kharcha |
| --- | --- |
| LLM API (development) | 0 se 20 USD, ya 0 agar Gemini free tier ya Ollama use ho |
| Embeddings | 0 (open-source BGE ya E5) |
| Vector DB | 0 (local Qdrant ya Chroma) |
| Ragas evaluation | Chand dollar, kyunke LLM judge use karta hai |
| LangSmith | Free developer tier |
| Hosting | 0 se 10 USD mahina |

Prices badalte rehte hain, is liye shuru karne se pehle har provider ka pricing page dekh lein. Evaluation ka kharcha bachane ke liye pehle chhote test set par chalayen.

## 18. Deliverables aur Definition of Done

Project tab mukammal hai jab:

1. GitHub repo public ho, saaf code ke saath.
2. README mein problem, architecture diagram, setup steps aur screenshots hon.
3. Live demo link ho (ya Docker se ek command mein chalne wala setup).
4. 2 se 3 minute ki demo video ho jo yeh dikhaye: wohi sawal alag roles se, guardrail ka block hona, aur evaluation report.
5. Evaluation report repo mein ho, targets ke saath.
6. Saare acceptance tests pass hon.

## 19. Portfolio mein Kaise Dikhayen

**Demo video ka script (idea):**

1. Emma se login, leave ka sawal: jawab milta hai.
2. Emma se salary ka sawal: access refusal.
3. Harry (HR) se wohi sawal: jawab milta hai.
4. Emma likhe 'pichle instructions bhool jao': guardrail rokta hai.
5. Admin page: latency, cost aur evaluation scores.

**LinkedIn ke liye description:** A secure internal knowledge assistant with role-based document access, guardrails against out-of-scope and malicious requests, and built-in evaluation of answer quality, latency and cost.

**README mein architecture diagram zaroor rakhein.** Recruiters aksar sirf README aur diagram dekhte hain.

## 20. Risks aur Hal

| Risk | Hal |
| --- | --- |
| RBAC mein leak (galti se restricted chunk mil jana) | Pre-filtering, unit tests, aur access-control tests har change ke baad |
| Guardrails zyada sakht (sahi sawal block) | False-block rate naapein, aur test set mein sahi sawal bhi daalein |
| Evaluation ka kharcha barh jana | Chhota test set, aur final run par hi bada model |
| Hallucination | Strict prompt, 'jawab nahi mila' ka raasta, faithfulness metric |
| Scope barh jana | Pehle core (RAG + RBAC), phir guardrails, phir evaluation. Multi-agent pipeline baad mein |
| Free tier ki limits | Local model (Ollama) ka backup |

## 21. Future Improvements (optional)

- Multi-agent pipeline (LangGraph) jo complex sawalon ko todta hai.
- Reranker jo retrieval ki quality behtar kare.
- PDF aur DOCX documents ki support.
- Document-level aur row-level permissions (sirf role nahi, department ya manager ke hisaab se).
- Audit trail ka export aur alerts jab bohat se attacks aayein.
- Urdu aur English dono mein sawal aur jawab.
