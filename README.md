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