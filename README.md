# Nexa AI (Enterprise V2)

### Production Agentic RAG & Enterprise Policy Intelligence Assistant

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20RAG-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant%20Cloud-dc2626.svg)](https://qdrant.tech/)
[![NeMo Guardrails](https://img.shields.io/badge/Security-NVIDIA%20NeMo%20Guardrails-76b900.svg)](https://github.com/NVIDIA/NeMo-Guardrails)
[![Portkey](https://img.shields.io/badge/AI%20Gateway-Portkey-blueviolet.svg)](https://portkey.ai/)
[![Auth](https://img.shields.io/badge/Auth-Clerk%20JWT-6C47FF.svg)](https://clerk.com/)
[![Database](https://img.shields.io/badge/Database-Supabase%20PostgreSQL-3ECF8E.svg)](https://supabase.com/)
[![Tests](https://img.shields.io/badge/Tests-111%20Backend%20+%208%20Frontend%20Passed-brightgreen.svg)]()

**Nexa AI Enterprise V2** is a production-grade, full-stack **Agentic Retrieval-Augmented Generation (RAG)** platform designed to deliver verified, evidence-bounded policy answers from enterprise documentation. 

Unlike traditional "naive" RAG pipelines that execute rigid, linear retrieval, Nexa AI orchestrates an autonomous **LangGraph StateGraph** that evaluates query intent, grades retrieved evidence sufficiency, executes adaptive feedback loops to reformulate missing information, and enforces multi-layered guardrails to guarantee zero hallucinations, persona integrity, and zero credential leakage.

---

## Key Highlights & Performance Metrics

- **Agentic Decision Graph**: Autonomous planning and routing between conversation memory and vector retrieval with an LLM-powered **Sufficiency Evaluator** and adaptive query reformulation retry loops (max 2 retries).
- **Enterprise Authentication (Clerk)**: End-to-end user identity via Clerk JWTs and JWKS public-key caching. Guarantees complete guest isolation and strict user-ownership enforcement across all conversations.
- **Persistent Conversation Management**: Multi-turn chat persistence backed by Supabase PostgreSQL, deterministic zero-latency title generation on first turn, authenticated inline conversation renaming, deletion, and UTC timezone alignment.
- **Authoritative Knowledge Base**: Decoupled from client-side storage; `GET /api/documents` is the authoritative single source of truth with universal multi-format ingestion (PDF, DOCX, TXT).
- **Keyword Payload-Indexed Qdrant Deletion**: Fast cascade deletion of vector points using Qdrant Cloud keyword payload index on `document_id`.
- **Two-Tier Input Security Guard**: Combines a **0ms Tier 1 regex pre-filter** with a **Tier 2 neural security classifier** running a strict fail-closed policy against prompt injections, DAN modes, and role-hijacks.
- **High-Dimension Vector Retrieval**: Powered by **Qdrant Cloud** with **3,072-dimensional** Google Gemini embeddings (`gemini-embedding-2-preview`).
- **Sub-25ms Cross-Encoder Reranking**: Integrates **FlashRank** utilizing a local, quantized ONNX cross-encoder model (`ms-marco-MiniLM-L-12-v2`) to re-score top candidate chunks semantically.
- **Dual-Layer Caching Engine**: Thread-safe in-memory embedding cache and response cache with deterministic state hashing and 3600s TTL, achieving **<25ms cache hits** (a **>99% latency reduction** on repeated queries).
- **High-Availability Gateway**: Automated fallback and retry routing via **Portkey AI Gateway** from `Llama-3.3-70b-versatile` to `Llama-3.1-8b-instant` on HTTP 429/503 errors.
- **Dual Memory Isolation**: Explicitly decouples personal conversation history from authoritative company documentation to prevent memory contamination and policy hallucinations.
- **Comprehensive Output Guardrails**: Real-time filtering against API key exposure (`gsk_`, `sk-`, `AIza`), PII (SSNs, credit cards), internal system prompt leaks, and out-of-scope persona drift.
- **100% Verified Test Suite**: **111 backend unit and regression tests** + **8 frontend API client tests** passing with 0 failures and 0 errors.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Agentic State Machine Workflow](#agentic-state-machine-workflow)
- [Multi-Tier Guardrail & Security Architecture](#multi-tier-guardrail--security-architecture)
- [Technology Stack](#technology-stack)
- [Key Engineering Innovations](#key-engineering-innovations)
- [Project Directory Structure](#project-directory-structure)
- [API Reference](#api-reference)
- [Local Setup & Installation](#local-setup--installation)
- [Running Automated Tests](#running-automated-tests)
- [Author & License](#author--license)

---

## System Architecture

```mermaid
flowchart TD
    User(["👤 User / Client"])

    subgraph Frontend["Frontend Layer (React 19 + Vite + TailwindCSS)"]
        UI["Chat Interface & Source Citations"]
        HistorySidebar["Conversation History & Inline Rename"]
        ExecPanel["Agent Execution Panel (Telemetry & Latency)"]
        Badge["Trust Badges: Grounded vs. Refusal"]
        AuthUI["Clerk Auth Buttons (Sign In / Up / Profile)"]
    end

    subgraph Gateway["API Gateway & Ingress (FastAPI)"]
        AuthGuard["Clerk JWT Authentication & JWKS Validator"]
        API["POST /api/chat & /api/v2/chat\nGET/PATCH/DELETE /api/conversations\nGET/POST/DELETE /api/documents"]
    end

    subgraph InputGuard["Gate 1: Input Guardrails (NeMo Guardrails + Colang)"]
        T1["Tier 1: Regex Pre-Filter (0ms Heuristic Guard)"]
        T2["Tier 2: Neural Security Classifier (Fail-Closed)"]
    end

    subgraph AgenticCore["Gate 2: LangGraph Agentic RAG Core"]
        direction TB
        Planner{"Planner Node\n(Intent & Query Formulation)"}
        ConvMem[("Conversation Memory\nMemorySaver Checkpointer")]
        Retriever["Retriever Node\n(Qdrant Hybrid Search)"]
        Reranker["FlashRank Cross-Encoder\n(ONNX TinyBERT / MiniLM)"]
        Sufficiency{"Sufficiency Evaluator Node\n(Evidence Reflection)"}
        Responder["Responder Node\n(Dual Grounded / Refusal Generator)"]
        
        Planner -- "CONVERSATIONAL" --> ConvMem --> Responder
        Planner -- "ENTERPRISE RETRIEVAL" --> Retriever
        Retriever --> Reranker --> Sufficiency
        Sufficiency -- "INSUFFICIENT (retry < 2)" --> Planner
        Sufficiency -- "SUFFICIENT or retry >= 2" --> Responder
    end

    subgraph DataStorage["Enterprise Knowledge, Database & Cache Layer"]
        Postgres[("Supabase PostgreSQL\n(Conversations, Messages, Documents)")]
        Qdrant[("Qdrant Vector DB\n(Collection: enterprise_rag\nPayload Index: document_id)")]
        GeminiEmbed["Gemini Embeddings API\n(3,072 Dimensions)"]
        InMemCache[("Thread-Safe In-Memory Cache\n(Embedding & Response Caches, TTL=3600s)")]
    end

    subgraph OutputGuard["Gate 3: Output Guardrails (NVIDIA NeMo)"]
        CheckOutput["CheckBotResponseAction\n• Secret & Key Leaks (gsk_, sk-)\n• PII (SSN, Cards)\n• System Prompt Leaks\n• Insufficient Evidence Policy Violations\n• Scope & Persona Drift"]
    end

    subgraph ModelGateway["Inference Infrastructure"]
        PortkeyClient["Portkey AI Gateway Client\n(Fallback Mode + Automatic Retries)"]
        PrimaryModel["Primary: Llama-3.3-70b-versatile (Groq)"]
        FallbackModel["Fallback: Llama-3.1-8b-instant (Groq)"]
    end

    %% Wiring
    User <--> UI
    UI <--> AuthUI
    UI <--> API
    API --> AuthGuard
    AuthGuard --> Postgres
    API --> T1
    T1 -- "BLOCKED" --> API
    T1 -- "PASSED" --> T2
    T2 -- "BLOCKED" --> API
    T2 -- "PASSED" --> Planner

    Retriever <--> GeminiEmbed
    Retriever <--> Qdrant
    Planner <--> InMemCache

    Responder --> PortkeyClient
    PortkeyClient --> PrimaryModel
    PrimaryModel -. "On 429/503" .-> FallbackModel
    PortkeyClient --> CheckOutput

    CheckOutput -- "BLOCKED" --> API
    CheckOutput -- "APPROVED" --> API
    API --> InMemCache
```

---

## Agentic State Machine Workflow

Nexa AI replaces static RAG chains with an **autonomous cyclical StateGraph**:

```mermaid
stateDiagram-v2
    [*] --> Planner: User Message Received

    state Planner {
        [*] --> CheckIntent
        CheckIntent --> RouteConversational: Greeting / Identity / Stated Name
        CheckIntent --> GenerateQuery: Enterprise Policy / Follow-up Question
    }

    Planner --> Responder: Intent == CONVERSATIONAL
    Planner --> Retriever: Intent == Standalone Search Query

    state Retriever {
        [*] --> VectorSearch: Qdrant Search (Top-K Chunks)
        VectorSearch --> Reranking: FlashRank ONNX Cross-Encoder
        Reranking --> Top5: Top 5 Relevant Chunks
    }

    Retriever --> Sufficiency: Documents Retrieved

    state Sufficiency {
        [*] --> GradeEvidence: Evaluate Documents vs Question
        GradeEvidence --> Sufficient: Direct Answer Found
        GradeEvidence --> Insufficient: Missing Important Info
    }

    Sufficiency --> Responder: Decision == SUFFICIENT or retry_count >= 2
    Sufficiency --> Planner: Decision == INSUFFICIENT & retry_count < 2 (Feedback Loop)

    state Responder {
        [*] --> SynthesizeGrounded: If Evidence Sufficient
        [*] --> SynthesizeRefusal: If Evidence Insufficient
        [*] --> UseConversationHistory: If Conversational
    }

    Responder --> OutputGuardrail: Content Generated
    OutputGuardrail --> [*]: Verified Safe Output
```

### Shared Graph State (`AgentState`)
```python
class AgentState(TypedDict):
    messages: Annotated[List[Dict[str, str]], operator.add]  # Appending conversation turns
    current_query: str                   # "CONVERSATIONAL" or formulated search query
    documents: List[Dict[str, Any]]      # Retrieved & reranked context chunks
    plan: List[str]                      # Step-by-step agent thoughts & telemetry
    status: str                          # Human-readable execution status for frontend
    final_answer: str                    # Final synthesized answer
    sufficient: bool                     # Grounding decision flag from Sufficiency Node
    missing_information: str             # Specific missing details used for retry planning
    retry_count: int                     # Number of retrieval retries attempted (max 2)
```

### Detailed Step-by-Step Agentic Flow Walkthrough

The agent dynamically executes one of three operational pathways based on autonomous runtime evaluation:

#### 🟢 Path 1: Conversational Memory Path (Fast-Path, Zero Retrieval)
1. **User Query Arrives**: e.g., *"Hello!"*, *"My name is Piyush Singh"*, or *"What is my name?"*
2. **Planner Node**: Classifies input as `CONVERSATIONAL`. It bypasses the vector database, avoiding unnecessary latency and token costs.
3. **Responder Node**: Synthesizes a response utilizing the `messages` conversation history stored in the checkpointer.
4. **Output Verification**: The response is verified against persona-drift and delivered to the user.

#### 🔵 Path 2: Direct Grounded Retrieval Path (Single-Shot Success)
1. **User Query Arrives**: e.g., *"What is the standard employee workweek?"*
2. **Planner Node**: Classifies the query as enterprise policy; converts conversational pronouns into a standalone search query (`"standard employee workweek policy"`).
3. **Retriever Node**: Queries Qdrant Cloud using 3,072-dimensional Gemini embeddings to retrieve top candidate document chunks.
4. **FlashRank Reranker**: Cross-encoder re-scores and sorts the candidates, pruning irrelevant context to top-5 chunks in `<25ms`.
5. **Sufficiency Evaluator**: LLM evaluates retrieved chunks against the question and determines `DECISION: SUFFICIENT`.
6. **Responder Node**: Synthesizes an authoritative, document-grounded response citing source files and page numbers.
7. **Output Guardrail & Caching**: Validates output against leaks, stores the result in cache (`TTL=3600s`), and tags the UI with a blue `Grounded in company documents` trust badge.

#### 🔄 Path 3: Adaptive Reflection & Retry Feedback Loop (Multi-Hop Self-Correction)
1. **Initial Ambiguous Retrieval**: User asks a nuanced question (e.g., *"What are contractor leave allowances?"*).
2. **First Retrieval Attempt**: Planner generates general query (`"contractor leave"`). Qdrant returns general employee leave documents without explicit contractor rules.
3. **Sufficiency Reflection**: Sufficiency Node grades the evidence as `DECISION: INSUFFICIENT` and identifies missing info:
   ```text
   DECISION: INSUFFICIENT
   MISSING: Specific leave rules, paid time off eligibility, or exceptions for contractors.
   ```
4. **Conditional Branching (Retry Loop)**: Because `sufficient == False` and `retry_count < 2`, the graph routes **back to Planner**.
5. **Query Reformulation**: The Planner reads the missing information feedback and generates a refined query targeting contractor agreements.
6. **Second Retrieval & Re-evaluation**: Qdrant is queried with the refined query and re-graded by Sufficiency.
7. **Evidence-Bounded Fallback**: If after 2 retries the documentation truly does not contain the answer, the graph terminates into the Responder with an honest evidence-bounded disclaimer, completely preventing hallucination and displaying an amber `Evidence bounded / Refusal` badge.

---

## Multi-Tier Guardrail & Security Architecture

### 1. Two-Tier Input Safety Layer
- **Tier 1 (0ms Regex Pre-Filter)**: Instantly intercepts known adversarial patterns (e.g., `ignore previous instructions`, `reveal system prompt`, `DAN mode`, direct key extractions) before consuming LLM tokens.
- **Tier 2 (Neural Security Classifier)**: Evaluates semantic intent for subtle persona-hijacks and jailbreak framing. Operates on a **fail-closed** architecture—any unparseable or errored response defaults to `BLOCK`.

### 2. Output Guardrails (`CheckBotResponseAction`)
- **Credential & Secret Protection**: Scans output for OpenAI (`sk-`), Groq (`gsk_`), Gemini (`AIza`), Bearer tokens, and private keys.
- **PII Masking**: Detects 9-digit Social Security Numbers (SSN) and 16-digit credit card sequences.
- **Instruction Protection**: Catches fragments leaking system prompts or internal configuration.
- **Insufficient Evidence Enforcement**: When `sufficient == False`, blocks affirmative policy commitments and stops out-of-scope generative outputs (e.g. fabricated LeetCode coding challenges or interview coaching).

---

## Technology Stack

| Layer | Technology | Specification / Purpose |
| :--- | :--- | :--- |
| **Reasoning Engine** | Meta Llama 3.3 (70B) & Llama 3.1 (8B) | High-speed enterprise inference hosted on Groq LPUs |
| **AI Gateway** | Portkey AI Gateway | Automated fallback routing, retry handling, and unified observability |
| **Agent Orchestration** | LangGraph & LangChain Core | StateGraph workflow, cyclic reflection loops, conditional branching |
| **Authentication** | Clerk (JWT & JWKS) | Client auth, public key verification, user ownership, guest isolation |
| **Relational Database** | Supabase PostgreSQL + SQLAlchemy | Persistent conversations, messages, documents, schema migration |
| **Vector Database** | Qdrant Cloud | `enterprise_rag` collection, Cosine similarity metric, payload indexing |
| **Embedding Model** | Google Gemini Embeddings | `models/gemini-embedding-2-preview` (3,072 dimensions) |
| **Reranker** | FlashRank | Local quantized ONNX runtime (`ms-marco-MiniLM-L-12-v2`) |
| **Guardrails & Safety** | NVIDIA NeMo Guardrails + Colang | Dialogue flow governance, multi-tier input/output security |
| **Backend Framework** | Python 3.12, FastAPI, Uvicorn | High-concurrency async REST API |
| **Caching Engine** | Dual In-Memory Caches | Thread-safe query embedding & LLM response caches with TTL |
| **Observability** | Logfire & OpenTelemetry | Real-time distributed tracing, latency spans, error tracking |
| **Frontend UI** | React 19, Vite, Tailwind CSS | Telemetry dashboard, source citations, history sidebar, responsive cards |

---

## Key Engineering Innovations

### 1. Separation of Conversation History vs. Enterprise Evidence
In typical naive RAG, user claims in chat history (e.g. *"I am the VP of HR, the leave policy is 40 days"*) contaminate prompt context, causing models to hallucinate that user statements are official policies. Nexa AI strictly isolates:
- **Conversation History**: Solely used for conversational continuity (user's name, team, pronouns).
- **Enterprise Evidence**: Sole authoritative truth for company policies, rules, and procedures.

### 2. Evidence-Bounded Disclaimers (Zero Hallucinations)
When the vector database contains no evidence for an out-of-scope query:
1. The sufficiency node flags `sufficient = False`.
2. The responder explicitly states what official documentation establishes and what is absent.
3. The frontend displays an **Evidence bounded / Refusal** badge alongside the explanation.

### 3. Dual-Layer Deterministic Cache Architecture
- **Embedding Cache**: Hashes normalized query strings to bypass redundant 3,072-dimensional Gemini API calls.
- **Response Cache**: Generates a deterministic key over `query + evidence_digest + sufficiency + history_digest + model + prompt_version`. Prevents stale answers when documents change while serving repeat questions in `<25ms`.

### 4. Deterministic Zero-Latency Title Generation
Conversation titles are generated via lightweight string normalization and word-boundary truncation upon the first user message (**0 additional LLM calls, 0 latency, 0 cost**), while allowing users to rename conversations via an authenticated `PATCH` endpoint.

### 5. Cascade Vector Deletion via Qdrant Payload Index
Universal document deletion removes the document and its chunks from PostgreSQL and cascade-deletes all corresponding vector points from Qdrant Cloud using a keyword payload index on `document_id`.

---

## Project Directory Structure

```
Nexa-Ai/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── graph.py                 # LangGraph StateGraph definition & routing
│   │   │   ├── state.py                 # AgentState typed dictionary schema
│   │   │   └── nodes/
│   │   │       ├── planner.py           # Intent classification & query reformulation
│   │   │       ├── retriever.py         # Qdrant search caller
│   │   │       ├── sufficiency.py       # Evidence reflection & grading
│   │   │       └── responder.py         # Grounded & evidence-bounded synthesis
│   │   ├── auth/
│   │   │   ├── clerk_auth.py            # Clerk JWT decoding, JWKS caching & security
│   │   │   └── __init__.py
│   │   ├── gateway/
│   │   │   ├── client.py                # Portkey gateway client & fallback routing
│   │   │   └── __init__.py
│   │   ├── guardrails/
│   │   │   ├── rails.py                 # NeMo Guardrails initialization & wrappers
│   │   │   └── config/
│   │   │       ├── actions.py           # Tier 1 regex, Tier 2 neural & output actions
│   │   │       ├── rails.co             # Colang dialogue orchestration flows
│   │   │       └── config.yml           # NeMo model configuration
│   │   ├── services/
│   │   │   ├── cache.py                 # Thread-safe TTL in-memory caching engine
│   │   │   ├── conversation_service.py  # History, persistence, rename & auto-titling
│   │   │   ├── embedding.py             # 3,072-dim Gemini embedding service
│   │   │   └── retrieval/
│   │   │       ├── qdrant_service.py    # Qdrant collection interface
│   │   │       └── ranking_services.py  # FlashRank ONNX cross-encoder reranker
│   │   ├── ingestion/
│   │   │   ├── processor.py             # Universal document ingestion & point deletion
│   │   │   └── Chunking/
│   │   │       └── splitter.py          # Recursive character text splitting
│   │   ├── config.py                    # Environment & runtime settings
│   │   ├── database.py                  # SQLAlchemy engine, Conversation & Message models
│   │   └── main.py                      # FastAPI application & REST endpoints
│   ├── tests/
│   │   ├── test_clerk_auth.py           # Clerk JWT token validation tests
│   │   ├── test_conversation_history.py # User conversation listing & guest isolation
│   │   ├── test_conversation_messages.py# Chronological message retrieval tests
│   │   ├── test_conversation_rename.py  # Authenticated inline rename & validation tests
│   │   ├── test_conversation_deletion.py# Conversation deletion & ownership tests
│   │   ├── test_conversation_memory.py  # Verification of memory vs evidence
│   │   ├── test_document_management.py  # Document upload, listing & Qdrant cleanup
│   │   ├── test_caching.py              # Cache hit/miss & TTL isolation tests
│   │   ├── test_tier2_guardrail.py      # Two-tier input guardrail test suite
│   │   ├── test_output_guardrails.py    # Output safety, PII & secret leak tests
│   │   └── test_planner_retry.py        # Sufficiency retry feedback verification
│   ├── migrate_conversations_user_id.py # Database migration for Clerk ownership
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.js                # Centralized API client with Clerk Bearer auth
│   │   │   └── client.test.mjs          # Unit tests for API client auth & headers
│   │   ├── components/
│   │   │   ├── AgentExecutionPanel.jsx  # Live thought process telemetry
│   │   │   ├── SourceReceipt.jsx        # Chunk-level source citations
│   │   │   ├── Shell.jsx                # App shell, Clerk auth controls & navigation
│   │   │   ├── Icons.jsx                # UI icons (EditIcon, AssistantIcon, etc.)
│   │   │   └── ui.jsx                   # MetricCard, Card, Button components
│   │   ├── pages/
│   │   │   ├── AIAssistant.jsx          # Chat interface, history sidebar & rename UI
│   │   │   ├── KnowledgeBase.jsx        # Document management & upload dashboard
│   │   │   └── Dashboard.jsx
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## API Reference

### 1. Chat & Inference

#### `POST /api/chat` (or `/api/v2/chat`)
Executes the full Guardrails $\to$ LangGraph $\to$ Portkey RAG pipeline.

```json
// Request
{
  "question": "What is the company annual leave policy?",
  "conversation_id": "optional-uuid-for-continuity"
}
```

```json
// Response
{
  "conversation_id": "11dc5240-b8a6-40c2-84fd-30d7894433cf",
  "answer": "Full-time employees receive 20 days of paid annual leave per calendar year (employee_handbook.pdf, Page 12).",
  "sources": [
    {
      "chunk_id": "handbook-chunk-4",
      "document": "employee_handbook.pdf",
      "page": 12,
      "score": 0.9421,
      "text": "Full-time employees receive 20 days of paid annual leave..."
    }
  ],
  "grounded": true,
  "thought_process": [
    "Planner: Formulated search query 'company annual leave policy'",
    "Retriever: Retrieved 5 candidates from Qdrant",
    "Reranker: FlashRank refined top chunks",
    "Sufficiency: Evidence verified sufficient"
  ],
  "status": "completed",
  "latency_ms": 1840.5
}
```

---

### 2. Conversation Management (Authenticated via Clerk Bearer Token)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/conversations` | Lists authenticated user's conversations (ordered newest first) |
| `GET` | `/api/conversations/{id}/messages` | Retrieves chronological message history with sources |
| `PATCH` | `/api/conversations/{id}` | Renames a conversation (validated 1-100 characters, owner-only) |
| `DELETE` | `/api/conversations/{id}` | Deletes conversation and all associated messages |

---

### 3. Knowledge Base & Document Management

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/documents` | Authoritative single-source list of indexed documents |
| `POST` | `/api/documents/upload` | Ingests PDF, DOCX, or TXT file into vector store & database |
| `DELETE` | `/api/documents/{id}` | Cascade deletes document from DB and Qdrant points by `document_id` |

---

## Local Setup & Installation

### Prerequisites
- Python 3.11 or 3.12
- Node.js 18+ & npm
- Supabase PostgreSQL database
- Qdrant Cloud Cluster
- Clerk account (for authentication)

---

### 1. Backend Configuration
```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:
```env
# Database & Persistence (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres.xxx:password@aws-0-pooler.supabase.com:5432/postgres

# Authentication (Clerk)
CLERK_SECRET_KEY=sk_test_your_clerk_secret_key
CLERK_AUTHORIZED_PARTIES=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173

# Reasoning & Gateway
PORTKEY_API_KEY=your_portkey_api_key
PORTKEY_CONFIG_ID=your_portkey_config_id
PORTKEY_MODEL=@rag/llama-3.3-70b-versatile
GROQ_API_KEY=your_groq_api_key

# Embeddings & Vector DB
GEMINI_API_KEY=your_gemini_api_key
QDRANT_CLUSTER_ENDPOINT=https://your-qdrant-cluster.qdrant.tech
QDRANT_API_KEY=your_qdrant_api_key

# Caching & Observability
RESPONSE_CACHE_TTL=3600
EMBEDDING_CACHE_TTL=3600
LOGFIRE_TOKEN=your_logfire_token
```

Run database migration & launch server:
```bash
# Run user_id column migration if needed
python migrate_conversations_user_id.py

# Launch FastAPI development server
python -m uvicorn app.main:app --reload --port 8000
```

---

### 2. Frontend Configuration
```bash
cd ../frontend
npm install
```

Create a `.env` file in `frontend/`:
```env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key
VITE_API_URL=http://localhost:8000
```

Launch the frontend:
```bash
npm run dev
```
The interface will be live at `http://localhost:5173`.

---

## Running Automated Tests

### Backend Regression Suite (111 Tests)
From `backend/`:
```bash
# Run the complete test suite
python -m unittest discover -s tests -p "test*.py" -v
```

To run individual test modules:
```bash
# Clerk Authentication Tests
python -m unittest tests.test_clerk_auth -v

# Conversation Rename & Ownership Tests
python -m unittest tests.test_conversation_rename -v

# Document Ingestion & Deletion Tests
python -m unittest tests.test_document_management -v

# Caching Engine Tests
python -m unittest tests.test_caching -v

# Guardrails Tests
python -m unittest tests.test_tier2_guardrail -v
python -m unittest tests.test_output_guardrails -v
```

### Frontend Client Tests (8 Tests)
From `frontend/`:
```bash
node src/api/client.test.mjs
```

### Production Build Verification
From `frontend/`:
```bash
npm run build
```

---

## Author

**Piyush Singh**  
B.Tech — Mathematics & Computing  
Indian Institute of Information Technology, Bhagalpur  
- **GitHub**: [@Piyush30007](https://github.com/Piyush30007)

---

## License

This project is licensed under the MIT License — see the LICENSE file for details.
