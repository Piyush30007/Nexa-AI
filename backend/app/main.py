# ============================================================
# CRITICAL: logfire MUST be configured before ALL other imports
# so that spans from all modules are captured from the start.
# ============================================================
import logfire
import os
from dotenv import load_dotenv

load_dotenv()
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

import time
from typing import Optional, List, Dict, Any

# Now safe to import app modules - logfire is already active
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.graph import rag_agent
from app.guardrails import initialize_rails, guard
from app.agents.state import AgentState


# Initialize FastAPI
app = FastAPI(title="Enterprise Agentic RAG API", version="2.0.0")

# ============================================================
# CORS MIDDLEWARE
# ============================================================
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
allowed_origins = [
    origin.strip()
    for origin in allowed_origins_env.split(",")
    if origin.strip()
] if allowed_origins_env else [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    initialize_rails()


# ============================================================
# SCHEMAS
# ============================================================
class QueryRequest(BaseModel):
    q: str
    thread_id: Optional[str] = "default_user"


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None


# ============================================================
# HEALTH ENDPOINTS
# ============================================================
@app.get("/")
def home():
    return {"message": "Enterprise LangGraph RAG API is live."}


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/graph")
def get_graph_image():
    """
    Returns the Mermaid image of the agent's workflow.
    """
    try:
        png_bytes = rag_agent.get_graph().draw_mermaid_png()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        return {"error": f"Could not generate graph image: {e}"}


# ============================================================
# HELPER: SOURCE NORMALIZATION
# ============================================================
def _normalize_sources(raw_docs: List[Any]) -> List[Dict[str, Any]]:
    """
    Normalize V2 Qdrant/FlashRank documents into the structure
    expected by the frontend SourceReceipt component.
    """
    normalized = []
    for idx, doc in enumerate(raw_docs):
        if isinstance(doc, dict):
            source_name = doc.get("source") or "Company Policy"
            score = doc.get("rerank_score") if doc.get("rerank_score") is not None else doc.get("score", 0.0)
            meta = doc.get("metadata") or {}
            page = meta.get("page") if isinstance(meta, dict) else None
            chunk_id = doc.get("chunk_id") or f"{source_name}-chunk-{idx}"
            text = doc.get("content", "")
        else:
            source_name = "Company Policy"
            score = 0.0
            page = None
            chunk_id = f"chunk-{idx}"
            text = str(doc)

        normalized.append({
            "chunk_id": str(chunk_id),
            "document": str(source_name),
            "page": page,
            "score": round(float(score), 4) if score is not None else 0.0,
            "text": text,
        })
    return normalized


# ============================================================
# V1-COMPATIBLE & V2 CHAT ENDPOINTS
# ============================================================
@app.post("/api/chat")
@app.post("/api/v2/chat")
def chat(request: ChatRequest):
    """
    Frontend-compatible chat endpoint connected to V2 Guardrails and LangGraph.
    """
    question = request.question.strip()
    thread_id = (request.conversation_id or "default_user").strip() or "default_user"
    start_time = time.perf_counter()

    try:
        # Gate 1: NeMo Guardrails
        rail_fired, rail_response = guard(question)
        if rail_fired:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logfire.info(f"🛡️ Request blocked by guardrails | thread={thread_id}")
            return {
                "conversation_id": thread_id,
                "answer": rail_response,
                "sources": [],
                "grounded": False,
                "thought_process": ["Intent: Guardrails Fired", "Retrieval: Skipped"],
                "status": "Blocked by guardrails.",
                "latency_ms": latency_ms,
            }

        # Gate 2: LangGraph RAG pipeline
        initial_state: AgentState = {
            "messages": [{"role": "user", "content": question}],
            "current_query": question,
            "documents": [],
            "plan": ["Start"],
            "status": "Initializing Graph...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }

        config = {"configurable": {"thread_id": thread_id}}
        final_output = rag_agent.invoke(initial_state, config=config)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        raw_docs = final_output.get("documents", [])
        normalized_sources = _normalize_sources(raw_docs)
        is_grounded = bool(final_output.get("sufficient") and len(normalized_sources) > 0)

        return {
            "conversation_id": thread_id,
            "answer": final_output.get("final_answer") or "I was unable to find relevant information to answer your question.",
            "sources": normalized_sources,
            "grounded": is_grounded,
            "thought_process": final_output.get("plan", []),
            "status": final_output.get("status", "completed"),
            "latency_ms": latency_ms,
        }

    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logfire.error(f"❌ Backend Execution Failed: {e}")
        return {
            "conversation_id": thread_id,
            "answer": "I apologize, but I encountered an internal error while processing your request. Please try again later.",
            "sources": [],
            "grounded": False,
            "thought_process": ["Error encountered during execution."],
            "status": "error",
            "latency_ms": latency_ms,
        }


# ============================================================
# LEGACY V2 QUERY ENDPOINT (PRESERVED)
# ============================================================
@app.post("/query")
def query(request: QueryRequest):
    """
    Executes the LangGraph RAG flow with memory using a POST request.
    """
    q = request.q
    thread_id = request.thread_id

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": q}],
        "current_query": q,
        "documents": [],
        "plan": ["Start"],
        "status": "Initializing Graph...",
        "final_answer": "",
        "sufficient": False,
        "missing_information": "",
        "retry_count": 0,
    }
    
    # Configuration for Memory (Thread ID)
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Gate 1: NeMo Guardrails — blocks off-topic, jailbreaks, and handles dialog
        rail_fired, rail_response = guard(q)
        if rail_fired:
            logfire.info(f"🛡️ Request blocked by guardrails | thread={thread_id}")
            return {
                "question": q,
                "answer": rail_response,
                "thought_process": ["Intent: Guardrails Fired", "Retrieval: Skipped"],
                "status": "Blocked by guardrails.",
                "sources": []
            }

        # Gate 2: LangGraph RAG pipeline
        final_output = rag_agent.invoke(initial_state, config=config)
        
        return {
            "question": q,
            "answer": final_output.get("final_answer"),
            "thought_process": final_output.get("plan"),
            "status": final_output.get("status"),
            "sources": final_output.get("documents", [])
        }
    except Exception as e:
        logfire.error(f"❌ Backend Execution Failed: {e}")
        return {
            "question": q,
            "answer": "I apologize, but I encountered an internal error while processing your request. Please try again later.",
            "thought_process": ["Error encountered during execution."],
            "status": "error",
            "sources": []
        }