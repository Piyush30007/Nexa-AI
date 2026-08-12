from pathlib import Path
import shutil

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import (
    get_db,
    init_db,
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
# DATABASE STARTUP
# ============================================================

@app.on_event("startup")
def startup():
    init_db()


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

        result = answer_question(
            request.question,
            db,
        )

        return result

    except Exception as e:

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