from pathlib import Path
import shutil
import time

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import (
    get_db,
    init_db,
    SessionLocal,
    Document,
    EvaluationRun,
    UsageLog,
    Conversation,
    Message,
)
from rag import ingest_document, answer_question
from evaluation import run_evaluation


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="NexaAI",
    description="Document-based RAG Assistant",
    version="1.0.0",
)


# ============================================================
# DATABASE STARTUP & BASELINE SEEDING
# ============================================================

@app.on_event("startup")
def startup():
    init_db()

    # Check whether the database already contains documents
    db = SessionLocal()
    try:
        doc_count = db.query(Document).count()
        if doc_count == 0:
            sample_pdf = Path(settings.sample_docs_dir) / "test_policy.pdf"
            if sample_pdf.exists():
                print(f"[Startup] Database is empty. Seeding baseline document: {sample_pdf.name}")
                ingest_document(str(sample_pdf), db)
                print("[Startup] Baseline document successfully ingested.")
            else:
                print(f"[Startup] Sample document not found at {sample_pdf}")
        else:
            print(f"[Startup] Database already contains {doc_count} document(s). Skipping seeding.")
    except Exception as e:
        print(f"[Startup] Seeding check encountered an issue: {e}")
    finally:
        db.close()


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CHAT REQUEST
# ============================================================

class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "message": "NexaAI RAG API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/api/health")
def api_health():
    return {
        "status": "ok"
    }


# ============================================================
# LIST DOCUMENTS
# ============================================================

@app.get("/api/documents")
def list_documents(
    db: Session = Depends(get_db),
):
    documents = (
        db.query(Document)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    return [
        {
            "id": document.id,
            "filename": document.filename,
            "file_type": document.file_type,
            "status": document.status,
            "num_chunks": document.num_chunks,
            "error_message": document.error_message,
            "uploaded_at": document.uploaded_at,
        }
        for document in documents
    ]


# ============================================================
# UPLOAD PDF
# ============================================================

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    # Check file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    file_path = (
        Path(settings.upload_dir)
        / file.filename
    )

    try:

        # Save uploaded PDF
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(
                file.file,
                buffer,
            )

        # Process PDF
        document = ingest_document(
            str(file_path),
            db,
        )

        return {
            "message": "PDF uploaded successfully.",
            "document_id": document.id,
            "filename": document.filename,
            "status": document.status,
            "num_chunks": document.num_chunks,
        }

    except Exception as e:

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# DELETE DOCUMENT
# ============================================================

@app.delete("/api/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
):

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    db.delete(document)
    db.commit()

    return {
        "message": "Document deleted successfully."
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/api/chat")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):

    try:

        # 1. Retrieve or create Conversation
        conversation_id = request.conversation_id
        conversation = None

        if conversation_id:
            conversation = (
                db.query(Conversation)
                .filter(
                    Conversation.id == conversation_id
                )
                .first()
            )

        if conversation is None:
            conversation_title = request.question.strip()[:60] or "New conversation"
            conversation = Conversation(
                id=conversation_id if conversation_id else None,
                title=conversation_title,
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        conversation_id = conversation.id

        # 2. Save user message
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=request.question,
            sources=[],
        )
        db.add(user_message)
        db.commit()

        # 3. Run RAG pipeline with timing
        start_time = time.perf_counter()
        result = answer_question(
            request.question,
            db,
        )
        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        answer_text = result.get("answer", "")
        sources = result.get("sources", [])
        grounded = result.get("grounded", False)

        # 4. Save assistant response message with sources
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer_text,
            sources=sources,
        )
        db.add(assistant_message)

        # 5. Record usage information
        context_chars = sum(
            len(str(s.get("text", "")))
            for s in sources
        )
        input_tokens = max(
            1,
            (len(request.question) + context_chars) // 4,
        )
        output_tokens = max(
            1,
            len(answer_text) // 4,
        )
        estimated_cost = round(
            (input_tokens / 1000.0 * settings.cost_per_1k_input_tokens)
            + (output_tokens / 1000.0 * settings.cost_per_1k_output_tokens),
            6,
        )

        usage_log = UsageLog(
            endpoint="/api/chat",
            model=settings.gemini_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            was_grounded=1 if grounded else 0,
        )
        db.add(usage_log)
        db.commit()

        # 6. Return response contract
        return {
            "conversation_id": conversation_id,
            "answer": answer_text,
            "sources": sources,
            "grounded": grounded,
            "latency_ms": latency_ms,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# CONVERSATIONS
# ============================================================

@app.get("/api/conversations")
def list_conversations(
    db: Session = Depends(get_db),
):

    conversations = (
        db.query(Conversation)
        .order_by(Conversation.created_at.desc())
        .all()
    )

    return [
        {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
        }
        for conversation in conversations
    ]


@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
):

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id
        )
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    messages = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "sources": message.sources or [],
            "created_at": message.created_at,
        }
        for message in messages
    ]


# ============================================================
# USAGE
# ============================================================

@app.get("/api/usage")
def get_usage(
    db: Session = Depends(get_db),
):

    logs = (
        db.query(UsageLog)
        .order_by(UsageLog.timestamp.desc())
        .all()
    )

    total_requests = len(logs)

    grounded_requests = sum(
        1
        for log in logs
        if log.was_grounded
    )

    total_input_tokens = sum(
        log.input_tokens or 0
        for log in logs
    )

    total_output_tokens = sum(
        log.output_tokens or 0
        for log in logs
    )

    total_cost = sum(
        log.estimated_cost or 0
        for log in logs
    )

    avg_latency = (
        sum(
            log.latency_ms or 0
            for log in logs
        )
        / total_requests
        if total_requests
        else 0
    )

    grounded_rate = (
        grounded_requests / total_requests
        if total_requests
        else 0
    )

    return {
        "total_requests": total_requests,
        "grounded_requests": grounded_requests,
        "grounded_rate": grounded_rate,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "estimated_cost": total_cost,
        "avg_latency_ms": avg_latency,
    }


# ============================================================
# RUN EVALUATION
# ============================================================

@app.post("/api/evaluation/run")
def evaluate(
    db: Session = Depends(get_db),
):

    try:

        result = run_evaluation(db)

        return {
            "message": "Evaluation completed",
            "num_cases": result.num_cases,
            "retrieval_accuracy": result.retrieval_accuracy,
            "answer_correctness": result.answer_correctness,
            "citation_accuracy": result.citation_accuracy,
            "hallucination_rate": result.hallucination_rate,
            "avg_latency_ms": result.avg_latency_ms,
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# GET LATEST EVALUATION RESULTS
# ============================================================

@app.get("/api/evaluation/results")
def get_evaluation_results(
    db: Session = Depends(get_db),
):

    result = (
        db.query(EvaluationRun)
        .order_by(
            EvaluationRun.timestamp.desc()
        )
        .first()
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "No evaluation results found. "
                "Run the evaluation first."
            ),
        )

    return {
        "id": result.id,
        "timestamp": result.timestamp,
        "num_cases": result.num_cases,
        "retrieval_accuracy": result.retrieval_accuracy,
        "answer_correctness": result.answer_correctness,
        "citation_accuracy": result.citation_accuracy,
        "hallucination_rate": result.hallucination_rate,
        "avg_latency_ms": result.avg_latency_ms,
        "results": result.results,
    }