from pathlib import Path
import shutil

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db, init_db, EvaluationRun
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


# ============================================================
# UPLOAD PDF
# ============================================================

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Check file type
    # --------------------------------------------------------

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    # --------------------------------------------------------
    # Create destination path
    # --------------------------------------------------------

    file_path = (
        Path(settings.upload_dir)
        / file.filename
    )

    try:

        # ----------------------------------------------------
        # Save uploaded PDF
        # ----------------------------------------------------

        with file_path.open("wb") as buffer:

            shutil.copyfileobj(
                file.file,
                buffer,
            )

        # ----------------------------------------------------
        # Process PDF
        # ----------------------------------------------------

        document = ingest_document(
            str(file_path),
            db,
        )

        # ----------------------------------------------------
        # Return successful response
        # ----------------------------------------------------

        return {
            "message": "PDF uploaded successfully.",
            "document_id": document.id,
            "filename": document.filename,
            "status": document.status,
            "num_chunks": document.num_chunks,
        }

    except Exception as e:

        # ----------------------------------------------------
        # Remove uploaded file if processing failed
        # ----------------------------------------------------

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


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

            "retrieval_accuracy":
                result.retrieval_accuracy,

            "answer_correctness":
                result.answer_correctness,

            "citation_accuracy":
                result.citation_accuracy,

            "hallucination_rate":
                result.hallucination_rate,

            "avg_latency_ms":
                result.avg_latency_ms,
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

        "timestamp":
            result.timestamp,

        "num_cases":
            result.num_cases,

        "retrieval_accuracy":
            result.retrieval_accuracy,

        "answer_correctness":
            result.answer_correctness,

        "citation_accuracy":
            result.citation_accuracy,

        "hallucination_rate":
            result.hallucination_rate,

        "avg_latency_ms":
            result.avg_latency_ms,

        "results":
            result.results,
    }
    
    
"""
                        main.py
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
     Upload PDF          Chat          Evaluation
          │                │                │
          ▼                ▼                ▼
     ingest_document   answer_question   run_evaluation
          │                │                │
          ▼                ▼                ▼
       SQLite            FAISS           10 questions
       + FAISS             +              │
                          Gemini           ▼
                                      Metrics
                                          │
                                          ▼
                                      SQLite
                                      
    """