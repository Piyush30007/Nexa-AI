# Nexa AI

### Document-Based RAG Knowledge Assistant

Nexa AI is a full-stack Retrieval-Augmented Generation (RAG) application that allows users to upload documents, ask questions about their content, and receive answers grounded in the retrieved document evidence.

The system combines **FastAPI, SQLite, FAISS, Sentence Transformers, Gemini, React, and Tailwind CSS** to provide a complete document-question-answering workflow with source citations and RAG evaluation.

---

## Features

- 📄 Upload PDF documents
- ✂️ Extract and chunk document text
- 🧠 Generate semantic embeddings using Sentence Transformers
- 🔎 Perform similarity search using FAISS
- 🗃️ Store document and chunk metadata in SQLite
- 🤖 Generate grounded answers using Gemini
- 📚 Display source documents and page numbers
- 🛡️ Reduce hallucinations using retrieval-based grounding
- 💬 Conversational AI assistant
- 📊 RAG evaluation dashboard
- 📈 Retrieval, citation, correctness, and hallucination metrics
- ⚡ Track retrieval and answer latency
- 📋 Usage monitoring
- 🎨 React-based dashboard with Tailwind CSS

---

## Architecture

```text
                         ┌─────────────────────┐
                         │      React UI       │
                         │  Vite + Tailwind    │
                         └──────────┬──────────┘
                                    │
                                    │ HTTP / REST API
                                    ▼
                         ┌─────────────────────┐
                         │      FastAPI        │
                         │      Backend        │
                         └──────────┬──────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                │                   │                   │
                ▼                   ▼                   ▼
        ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
        │    SQLite    │    │    FAISS     │    │    Gemini    │
        │              │    │              │    │              │
        │ Documents    │    │ Vector       │    │ Answer       │
        │ Chunks       │    │ Similarity   │    │ Generation   │
        │ Messages     │    │ Search       │    │              │
        │ Evaluation   │    │              │    │              │
        └──────────────┘    └──────────────┘    └──────────────┘
                                    ▲
                                    │
                            ┌───────┴────────┐
                            │ Sentence       │
                            │ Transformers   │
                            │ Embeddings     │
                            └────────────────┘

📊 RAG Evaluation
The application includes an evaluation pipeline for measuring:

Retrieval Accuracy

Answer Correctness

Citation Accuracy

Hallucination Rate

Retrieval Latency

Answer Generation Latency

The evaluation dataset contains both in-context questions and out-of-context questions.

📈 Usage Monitoring
The backend tracks:

Model

Endpoint

Input tokens

Output tokens

Estimated cost

Request latency

Grounding status

Timestamp

🎨 Frontend Dashboard
The React frontend contains:

Dashboard

AI Assistant

Knowledge Base

Evaluation

Usage

Settings

🧠 Technology Stack
Frontend
Technology	Purpose
React	User interface
Vite	Frontend build tool
React Router	Client-side routing
Tailwind CSS	Styling
JavaScript	Frontend logic
Backend
Technology	Purpose
Python	Backend programming
FastAPI	REST API
Uvicorn	ASGI server
SQLAlchemy	Database ORM
SQLite	Application metadata storage
AI / RAG
Technology	Purpose
Sentence Transformers	Semantic embeddings
FAISS	Vector similarity search
Google Gemini	Answer generation
Document Processing
Technology	Purpose
PDF Processing	Extract document text
Python	Document processing pipeline
🏗️ System Architecture
Plaintext
                         ┌────────────────────────┐
                         │     React Frontend     │
                         │    Vite + Tailwind     │
                         └───────────┬────────────┘
                                     │
                                     │ REST API
                                     ▼
                         ┌────────────────────────┐
                         │     FastAPI Backend    │
                         │                        │
                         │ Document Processing    │
                         │ RAG Pipeline           │
                         │ Chat                   │
                         │ Evaluation             │
                         │ Usage Tracking         │
                         └───────────┬────────────┘
                                     │
             ┌───────────────────────┼───────────────────────┐
             │                       │                       │
             ▼                       ▼                       ▼
      ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
      │    SQLite    │        │    FAISS     │        │    Gemini    │
      │              │        │              │        │              │
      │ Documents    │        │ Vector Index │        │ Generation   │
      │ Chunks       │        │ Similarity   │        │              │
      │ Messages     │        │ Search       │        │              │
      │ Conversations│        │              │        │              │
      │ Usage Logs   │        │              │        │              │
      │ Evaluations  │        │              │        │              │
      └──────────────┘        └──────▲───────┘        └──────────────┘
                                     │
                              ┌──────┴───────┐
                              │   Sentence   │
                              │ Transformers │
                              │  Embeddings  │
                              └──────────────┘
🔄 RAG Pipeline
Nexa AI follows a retrieval-first RAG architecture.

1. Document Ingestion
Plaintext
PDF ──► Text Extraction ──► Text Chunking ──► Embedding Generation ──► Normalized Embeddings ──► FAISS Index & SQLite Metadata
2. Question Answering
Plaintext
User Question ──► Question Embedding ──► FAISS Similarity Search ──► Retrieve Candidate Chunks ──► SQLite Chunk Lookup ──► Relevant Context ──► Gemini ──► Generated Answer ──► Sources + Grounding Status
📄 Document Ingestion
When a document is uploaded:

Plaintext
PDF ──► Extract Text ──► Create Chunks ──► Generate Embeddings ──► Store Vectors in FAISS & Metadata in SQLite
Each chunk contains metadata such as:

Chunk ID

Document ID

FAISS ID

Chunk Index

Text

Page Number

The faiss_id connects the vector stored in FAISS with the corresponding chunk stored in SQLite.

🔎 Retrieval System
The retrieval pipeline works as follows:

Plaintext
Question ──► Embedding ──► FAISS Search ──► FAISS IDs ──► SQLite Lookup ──► Chunk Text + Metadata + Score
The application uses normalized embeddings with FAISS IndexFlatIP. Because the vectors are normalized, inner product can be used for cosine-similarity-style retrieval.

The retriever also obtains additional candidates before selecting the final results:

Python
candidate_k = top_k * 4
This provides extra candidates that can be filtered before returning the final retrieval results.

📚 Source Attribution
Each retrieved result contains information such as:

JSON
{
  "document": "test_policy.pdf",
  "page": 1,
  "chunk_id": "...",
  "score": 0.5566
}
The frontend displays these sources with the generated answer. This allows users to understand:

Which document was used

Which page contained the information

Which retrieved chunk supported the answer

The similarity score of the retrieved result

🤖 Answer Generation
Gemini receives the retrieved context instead of being asked to answer purely from general knowledge.

Plaintext
User Question + Retrieved Evidence ──► Gemini ──► Grounded Answer
Example
Question: How often are employees paid?

Retrieved Evidence: Employees are paid on a bi-weekly basis.

Answer: Employees are paid on a bi-weekly basis.

🛡️ Out-of-Context Handling
The evaluation system tests questions that are not present in the knowledge base.

Question: What is the company's policy for employees working on Mars?

Expected Behavior: Since the indexed document contains no information about Mars, the system does not fabricate an answer and responds:

Plaintext
I couldn't find enough information in the available knowledge base to answer this question.
🗄️ Database Architecture
SQLite is used to store application metadata.

Documents Table
Stores uploaded documents (id, filename, file_type, status, num_chunks, error_message, uploaded_at).

Chunks Table
Stores document chunks (id, document_id, faiss_id, chunk_index, text, page).

Plaintext
FAISS ──(faiss_id)──► SQLite Chunk ──► [text, page, document]
Conversations Table
Stores conversations (id, title, created_at).

Messages Table
Stores conversation messages (id, conversation_id, role, content, sources, created_at).

Usage Logs Table
Stores API usage information (id, request_id, endpoint, model, input_tokens, output_tokens, latency_ms, estimated_cost, was_grounded, timestamp).

Evaluation Runs Table
Stores evaluation results (id, timestamp, num_cases, retrieval_accuracy, answer_correctness, citation_accuracy, hallucination_rate, avg_latency_ms, results).

📊 Evaluation System
Nexa AI includes an automated evaluation pipeline checking the complete RAG workflow:

Retrieval Accuracy: Checks whether expected evidence was retrieved.

Answer Correctness: Checks whether the generated answer matches expectations.

Citation Accuracy: Checks whether the answer references the correct source document.

Grounding: Checks whether the answer is fully supported by retrieved evidence.

Hallucination Rate: Measures unsupported answers.

Latency: Tracks Retrieval Latency + Answer Generation Latency.

🧪 Evaluation Dataset
Contains in-context questions (e.g., "How often are employees paid?") and out-of-context rejection tests (e.g., "What is the policy for teleporting employees?").

📈 Example Evaluation
Plaintext
============================================================
EVALUATION COMPLETE
============================================================
Total test cases       : 6
Gemini cases completed : 5
Gemini cases failed    : 0

Retrieval Accuracy     : 83.33%
Citation Accuracy      : 83.33%
Answer Correctness     : 100.00%
Hallucination Rate     : 0.00%
============================================================
🖥️ Frontend
Built using React, Vite, React Router, and Tailwind CSS.

Dashboard: Overview of system status, documents, usage, and metrics.

AI Assistant: Conversational interface with source receipts, grounding status, and response latency.

Knowledge Base: Upload, view, and delete indexed PDF documents.

Evaluation: Visual display of RAG benchmark scores and detailed test case breakdowns.

Usage: Tracking backend/API usage metrics.

Settings: Backend and system health status.

📁 Project Structure
Plaintext
Nexa-Ai/
│
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── rag.py
│   ├── evaluation.py
│   └── requirements.txt
│
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   └── src/
│       ├── api/
│       │   └── client.js
│       ├── components/
│       │   ├── Shell.jsx
│       │   ├── PageHeader.jsx
│       │   ├── SourceReceipt.jsx
│       │   └── ui.jsx
│       ├── pages/
│       │   ├── Dashboard.jsx
│       │   ├── AIAssistant.jsx
│       │   ├── KnowledgeBase.jsx
│       │   ├── Evaluation.jsx
│       │   ├── Usage.jsx
│       │   └── Settings.jsx
│       ├── App.jsx
│       ├── index.css
│       └── main.jsx
│
├── data/
├── .gitignore
└── README.md
⚙️ Backend Setup
Prerequisites
Python 3.12+

pip

Git

Clone & Navigate
Bash
git clone [https://github.com/Piyush30007/Nexa-AI.git](https://github.com/Piyush30007/Nexa-AI.git)
cd Nexa-AI/backend
Create Virtual Environment
Windows:

PowerShell
python -m venv .venv
.venv\Scripts\activate
Linux / macOS:

Bash
python3 -m venv .venv
source .venv/bin/activate
Install Dependencies
Bash
pip install -r requirements.txt
Environment Variables
Create backend/.env and add:

Code snippet
GEMINI_API_KEY=your_gemini_api_key
Run Backend
Bash
uvicorn main:app --reload
API Base: http://localhost:8000

Swagger Docs: http://localhost:8000/docs

💻 Frontend Setup
Open a new terminal:

Bash
cd frontend
npm install
npm run dev
Frontend Base: http://localhost:5173

API Configuration
Defined in src/api/client.js:

JavaScript
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
🔌 API Endpoints
GET / — Root endpoint

GET /api/health — System health

POST /api/documents/upload — Upload PDF document

POST /api/chat — Submit query to AI assistant

POST /api/evaluation/run — Run evaluation suite

GET /api/evaluation/results — Fetch latest evaluation results

🔐 Security
Store GEMINI_API_KEY in environment variables; never commit .env.

Do not expose API keys in frontend code.

Keep virtual environments (.venv/) out of version control.

Enforce production CORS policies.

🚀 Deployment
Plaintext
                    Internet
                       │
                       ▼
              ┌─────────────────┐
              │ React + Vite    │
              │     Vercel      │
              └────────┬────────┘
                       │ HTTPS
                       ▼
              ┌─────────────────┐
              │ FastAPI Backend │
              │     Render      │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       SQLite        FAISS       Gemini
Backend (Render)
Root Directory: backend

Build Command: pip install -r requirements.txt

Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT

Environment Variable: Set GEMINI_API_KEY

Frontend (Vercel)
Root Directory: frontend

Build Command: npm run build

Output Directory: dist

Environment Variable: Set VITE_API_URL=https://your-backend-domain.com

🛠️ Future Improvements
🔄 Streaming LLM responses

🔍 Hybrid keyword + semantic retrieval

🧠 Cross-encoder reranking

📄 Advanced chunking strategies

🔐 Authentication & Authorization

☁️ Cloud Object Storage (S3 / Cloud Storage)

🗄️ PostgreSQL + Pgvector integration

🎯 Project Objective
Nexa AI demonstrates a complete and measurable RAG pipeline rather than connecting an LLM to a basic prompt. It serves as a practical implementation of vector similarity search, grounded LLM generation, hallucination control, and full-stack AI system architecture.

📌 Current Status
PDF Upload ✅

Document Processing & Chunking ✅

FAISS Vector Indexing ✅

Gemini Answer Generation ✅

Grounded Citations ✅

Evaluation Pipeline ✅

Usage Tracking ✅

Frontend Dashboard ✅

👨‍💻 Author
Piyush Singh

B.Tech — Mathematics & Computing

Indian Institute of Information Technology, Bhagalpur

GitHub: https://github.com/Piyush30007

📜 License
This project is intended for educational, research, and portfolio purposes.


---

### 💻 Terminal Commands

Run these commands in your PowerShell terminal to commit and push the update to GitHub:

```powershell
git add README.md
git commit -m "Update complete project documentation"
git push