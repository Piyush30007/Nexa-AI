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
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# Now safe to import app modules - logfire is already active
from fastapi import FastAPI, Response, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, init_db, Document, EvaluationRun
from app.ingestion.processor import (
    process_file,
    collection_exists,
    create_collection,
    delete_document_points,
)
from app.auth.clerk_auth import get_current_user_optional, get_current_user
from app.services.conversation_service import (
    resolve_or_create_conversation,
    save_user_message,
    save_assistant_message,
    get_user_conversations,
    get_conversation_messages,
    delete_conversation,
    update_conversation_title,
)
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
    "https://nexa-ai-v2-pearl.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()
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


class RenameConversationRequest(BaseModel):
    title: str


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
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    Frontend-compatible chat endpoint connected to V2 Guardrails, LangGraph,
    and authenticated conversation persistence (Phase 6.2A).
    """
    question = request.question.strip()
    thread_id = resolve_or_create_conversation(
        db=db,
        conversation_id=request.conversation_id,
        current_user=current_user,
    )
    start_time = time.perf_counter()

    # Step 1: For authenticated users, persist user query
    user_message = None
    if current_user is not None:
        try:
            user_message = save_user_message(
                db=db,
                conversation_id=thread_id,
                content=question,
            )
        except Exception as e:
            db.rollback()
            logfire.error(f"Failed to persist user message: {e}")
            raise HTTPException(
                status_code=500,
                detail="Database error: unable to record user message.",
            )

    try:
        # Gate 1: NeMo Guardrails
        rail_fired, rail_response = guard(question)
        if rail_fired:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logfire.info(f"🛡️ Request blocked by guardrails | thread={thread_id}")
            if current_user is not None:
                save_assistant_message(
                    db=db,
                    conversation_id=thread_id,
                    content=rail_response,
                    sources=[],
                )
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
        final_answer = final_output.get("final_answer") or "I was unable to find relevant information to answer your question."

        # Step 2: For authenticated users, persist assistant response and sources
        if current_user is not None:
            save_assistant_message(
                db=db,
                conversation_id=thread_id,
                content=final_answer,
                sources=normalized_sources,
            )

        return {
            "conversation_id": thread_id,
            "answer": final_answer,
            "sources": normalized_sources,
            "grounded": is_grounded,
            "thought_process": final_output.get("plan", []),
            "status": final_output.get("status", "completed"),
            "latency_ms": latency_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logfire.error(f"❌ Backend Execution Failed: {e}")
        # Clean up pending user message on RAG failure to avoid orphaned partial turn
        if current_user is not None and user_message is not None:
            try:
                db.delete(user_message)
                db.commit()
            except Exception as cleanup_err:
                db.rollback()
                logfire.error(f"Failed to clean up user message after RAG failure: {cleanup_err}")

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
# CONVERSATIONS HISTORY LISTING (PHASE 6.3A)
# ============================================================
@app.get("/api/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List conversation history belonging exclusively to the authenticated Clerk user.
    Ordered by newest first (created_at DESC, id DESC).
    """
    return get_user_conversations(db=db, user_id=current_user["id"])


# ============================================================
# CONVERSATION MESSAGES RETRIEVAL (PHASE 6.3B)
# ============================================================
@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieve message history for an authenticated user's conversation.
    Ordered chronologically (created_at ASC, id ASC).
    """
    return get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["id"],
    )


# ============================================================
# CONVERSATION DELETION (PHASE 6.4)
# ============================================================
@app.delete("/api/conversations/{conversation_id}")
def delete_conversation_endpoint(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete an authenticated user's conversation and cascade delete its messages.
    """
    return delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["id"],
    )


# ============================================================
# CONVERSATION RENAMING (PHASE 8.3)
# ============================================================
@app.patch("/api/conversations/{conversation_id}")
def rename_conversation_endpoint(
    conversation_id: str,
    request: RenameConversationRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Rename an authenticated user's conversation.
    """
    return update_conversation_title(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user["id"],
        title=request.title,
    )


# ============================================================
# DOCUMENT MANAGEMENT & INGESTION (KNOWLEDGE BASE)
# ============================================================
@app.get("/api/documents")
def list_documents(db: Session = Depends(get_db)):
    """
    List all documents indexed in the enterprise knowledge base.
    """
    documents = (
        db.query(Document)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "status": d.status,
            "num_chunks": d.num_chunks,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            "error_message": d.error_message,
        }
        for d in documents
    ]


@app.post("/api/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Ingest a document (PDF, HTML, TXT, DOCX, PPTX) into Qdrant Cloud using Gemini embeddings,
    and persist metadata in the documents database table.
    """
    allowed_extensions = {".pdf", ".html", ".htm", ".txt", ".docx", ".pptx"}
    filename = file.filename or "uploaded_document"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported formats: PDF, HTML, TXT, DOCX, PPTX.",
        )

    upload_dir = Path("uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_suffix = uuid.uuid4().hex[:8]
    temp_filename = f"{temp_suffix}_{filename}"
    file_path = upload_dir / temp_filename

    # Step 1: Save uploaded file to temporary location
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logfire.error(f"Failed to save uploaded file {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {str(e)}",
        )

    # Step 2: Create PostgreSQL Document record in 'Processing' state before ingestion starts
    doc = Document(
        id=str(uuid.uuid4()),
        filename=filename,
        file_type=ext.lstrip("."),
        status="Processing",
        num_chunks=0,
        uploaded_at=datetime.now(timezone.utc),
        error_message=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Step 3: Run existing V2 ingestion pipeline and update status
    try:
        if not collection_exists():
            create_collection()

        num_chunks = process_file(
            file_path=str(file_path),
            filename=filename,
            source_type="user_upload",
            document_id=str(doc.id),
        )

        if not num_chunks:
            doc.status = "Failed"
            doc.num_chunks = 0
            doc.error_message = "No extractable or indexable content found in document."
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"Document '{filename}' contains no extractable or indexable content.",
            )

        doc.status = "Indexed"
        doc.num_chunks = num_chunks
        doc.error_message = None
        db.commit()
        db.refresh(doc)

        return {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "num_chunks": doc.num_chunks,
            "status": doc.status,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "message": f"Document '{filename}' successfully indexed into Qdrant.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error during document ingestion for {filename}: {e}")
        doc.status = "Failed"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process and index document: {str(e)}",
        )
    finally:
        # Step 4: Always clean up the temporary uploaded file
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as cleanup_err:
                logfire.warning(f"Could not remove temp file {file_path}: {cleanup_err}")


@app.delete("/api/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete an indexed document from the database and remove its vector points from Qdrant.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete points from Qdrant using unique document_id
    try:
        delete_document_points(document_id=doc.id)
    except Exception as e:
        logfire.error(f"Qdrant deletion failed for document {document_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clean up document vectors from Qdrant: {str(e)}",
        )

    # Only delete from DB if Qdrant cleanup succeeded
    filename = doc.filename
    db.delete(doc)
    db.commit()

    return {"message": f"Document '{filename}' successfully deleted."}


# ============================================================
# EVALUATION ENDPOINTS
# ============================================================
@app.get("/api/evaluation/results")
def get_evaluation_results(
    db: Session = Depends(get_db),
):
    """
    Retrieve latest evaluation benchmark metrics. Returns empty list if no runs exist.
    """
    try:
        run = (
            db.query(EvaluationRun)
            .order_by(EvaluationRun.timestamp.desc())
            .first()
        )
        if not run:
            return []

        return {
            "id": run.id,
            "timestamp": run.timestamp.isoformat() if run.timestamp else None,
            "num_cases": run.num_cases,
            "retrieval_accuracy": run.retrieval_accuracy,
            "answer_correctness": run.answer_correctness,
            "citation_accuracy": run.citation_accuracy,
            "hallucination_rate": run.hallucination_rate,
            "avg_latency_ms": run.avg_latency_ms,
            "results": run.results or [],
        }
    except Exception as e:
        logfire.error(f"Failed to fetch evaluation results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch evaluation results: {str(e)}",
        )


@app.post("/api/evaluation/run")
def trigger_evaluation(
    db: Session = Depends(get_db),
):
    """
    Execute the RAG evaluation benchmark suite against the test dataset.
    """
    try:
        from evaluation import run_evaluation
        result = run_evaluation(db)
        return {
            "message": "Evaluation completed",
            "id": getattr(result, "id", None),
            "num_cases": getattr(result, "num_cases", 0),
            "retrieval_accuracy": getattr(result, "retrieval_accuracy", 0.0),
            "answer_correctness": getattr(result, "answer_correctness", 0.0),
            "citation_accuracy": getattr(result, "citation_accuracy", 0.0),
            "hallucination_rate": getattr(result, "hallucination_rate", 0.0),
            "avg_latency_ms": getattr(result, "avg_latency_ms", 0.0),
        }
    except Exception as e:
        logfire.error(f"Evaluation execution failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}",
        )


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