""""
Flow Of the rag file will be 
UPLOAD PDF
   ↓
Extract text
   ↓
Chunk text
   ↓
Create embeddings
   ↓
Store vectors in FAISS
   ↓
Store chunk metadata in SQLite
"""

"""
    "What is the normal workweek?"
             ↓
       Embed question
             ↓
        Search FAISS
             ↓
       Top 5 chunks
             ↓
     Relevance filtering
             ↓
      Build grounded prompt
             ↓
           Gemini
             ↓
    Answer + source/page
    """
    
import re
import time
from pathlib import Path
import uuid
import faiss
import numpy as np
import fitz  # PyMuPDF
# from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from config import settings
from database import Document, Chunk
from google import genai
from google.genai import types 
#embedding model

# ============================================================
# GEMINI CLIENT
# ============================================================

_gemini_client = None


def get_gemini_client():
    """
    Create and cache the Gemini client.
    """

    global _gemini_client

    if _gemini_client is None:

        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing."
            )

        _gemini_client = genai.Client(
            api_key=settings.gemini_api_key
        )

    return _gemini_client


# ============================================================
# GEMINI EMBEDDINGS
# ============================================================

def create_embeddings(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> np.ndarray:
    """
    Convert text into normalized Gemini embedding vectors.

    Gemini embedding model:
        gemini-embedding-001

    Output dimension:
        settings.embedding_dim

    Task types:
        RETRIEVAL_DOCUMENT
        RETRIEVAL_QUERY
    """

    if not texts:
        return np.zeros(
            (0, settings.embedding_dim),
            dtype="float32",
        )

    client = get_gemini_client()

    all_vectors = []

    # Keep batches reasonably small.
    # This avoids sending a huge request for large PDFs.
    batch_size = 50

    for start in range(0, len(texts), batch_size):

        batch = texts[
            start:start + batch_size
        ]

        response = client.models.embed_content(
            model=settings.embedding_model,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.embedding_dim,
            ),
        )

        if not response.embeddings:
            raise ValueError(
                "Gemini returned no embeddings."
            )

        for embedding in response.embeddings:

            if not embedding.values:
                raise ValueError(
                    "Gemini returned an empty embedding."
                )

            all_vectors.append(
                embedding.values
            )

    vectors = np.asarray(
        all_vectors,
        dtype="float32",
    )

    # Make sure the dimension is exactly what FAISS expects.
    if vectors.shape[1] != settings.embedding_dim:

        raise ValueError(
            f"Embedding dimension mismatch. "
            f"Expected {settings.embedding_dim}, "
            f"got {vectors.shape[1]}."
        )

    # Normalize vectors.
    #
    # After normalization:
    # inner product ≈ cosine similarity
    #
    # This matches FAISS IndexFlatIP.
    faiss.normalize_L2(vectors)

    return vectors


def create_query_embedding(
    question: str,
) -> np.ndarray:
    """
    Create an embedding specifically for a retrieval query.
    """

    vectors = create_embeddings(
        [question],
        task_type="RETRIEVAL_QUERY",
    )

    return vectors[0]


#will extract text from the pdf 
def extract_pdf_pages(file_path: str) -> list[tuple[int, str]]:
    """
    Extract text from a PDF while preserving page numbers.

    Returns:

        [
            (1, "text from page 1"),
            (2, "text from page 2"),
            ...
        ]
    """

    pages = []

    pdf = fitz.open(file_path)  # open the pdf 

    try:
        for page_number, page in enumerate(pdf, start=1):  # loop through evry pages we have pdf start =1 because the python will start from 0 indexed but pages are from 1 

            text = page.get_text("text")

            # Basic cleaning
            text = re.sub(r"\s+", " ", text).strip() #cleaning the text 

            if text:
                pages.append(
                    (page_number, text)
                )

    finally:
        pdf.close()

    return pages
#above for extract pdf pages text   we doesnt use ocr fallback which help  use to determie the scanned pdf text we use only the normal method for text extraction  

#chunking 
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_pages(
    pages: list[tuple[int, str]]
) -> list[dict]:
    """
    Recursive chunking with page preservation.

    pages:
        [
            (page_number, page_text),
            ...
        ]

    Returns:
        [
            {
                "text": "...",
                "page": 1,
                "chunk_index": 0
            },
            ...
        ]
    """

     # Approximate token → character conversion.
    # 700 tokens ≈ 2800 characters
    # 100 tokens ≈ 400 characters.
    chunk_size = settings.chunk_size_tokens * 4
    chunk_overlap = settings.chunk_overlap_tokens * 4

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",   # paragraph
            "\n",     # line
            ". ",     # sentence
            " ",      # word
            "",       # character
        ],
        length_function=len,
    )

    chunks = []
    chunk_index = 0

    for page_number, page_text in pages:

        if not page_text.strip():
            continue

        page_chunks = splitter.split_text(page_text)

        for chunk_text in page_chunks:

            chunk_text = chunk_text.strip()

            if not chunk_text:
                continue

            chunks.append(
                {
                    "text": chunk_text,
                    "page": page_number,
                    "chunk_index": chunk_index,
                }
            )

            chunk_index += 1

    return chunks

#embeddings  create converts text->vectors 
# def create_embeddings(chunks: list[dict]) -> np.ndarray:
#     """
#     Convert chunk text into normalized embedding vectors.

#     Input:
#         [
#             {"text": "...", "page": 1, "chunk_index": 0},
#             {"text": "...", "page": 1, "chunk_index": 1},
#         ]

#     Output:
#         NumPy array of shape:
#         (number_of_chunks, embedding_dimension)
#     """

#     if not chunks:
#         return np.zeros(
#             (0, settings.embedding_dim),
#             dtype="float32",
#         )

#     model = get_embedding_model()

#     texts = [
#         chunk["text"]
#         for chunk in chunks
#     ]

#     vectors = model.encode(
#         texts,
#         convert_to_numpy=True,
#         normalize_embeddings=True, #normalize each vector to have approximately unit length because later we are  going to use faiss.indexflatip which performs inner product search 
#         #when vectors are normalized inner product == cosine similarity 
#         show_progress_bar=True, #it  display progress while embedding are beign generated 
#     )

#     return vectors.astype("float32") #connverts vectors to 32 bit floating point numbers because faiss excepts /works efficiently with float 32 vectors  

#faiss vector store 
#faiss is so fast becausee it uses the k means clustering , product quantization and optimized bruteforce search
#this function becuase we want to identify when similarity search done we know which chunk it is 

_index = None


def get_faiss_index():
    """
    Create/load the FAISS index.

    We use normalized embeddings, so inner product
    gives us cosine similarity.
    """
    global _index

    if _index is None:

        index_path = Path(settings.index_dir) / "faiss.index"

        if index_path.exists(): #here it loads the existing path that has been created
            # print("Loading existing FAISS index...")

            _index = faiss.read_index(
                str(index_path)
            )

        else:
            # print("Creating new FAISS index...")

            base_index = faiss.IndexFlatIP( # reason of using IndexFlatIP is we use normalized sentence transforer embedidng so we use indexflatip to perform cosine similarity search throguh inner product 
                settings.embedding_dim
            )

            _index = faiss.IndexIDMap2( #then wrap it with indexidmap2 so each vector can have stable id that maps backs to the corresponding chunk and its document page metadata in sqlite 
                                       
                base_index
            )

    return _index

#add vectors 
#stores those vectors in faiss and associates each vector with an id
def add_embeddings(
    vectors: np.ndarray,
    faiss_ids: list[int],
):
    """
    Add embedding vectors to FAISS.

    Each vector receives a unique FAISS ID.
    """

    if len(vectors) == 0:
        return

    index = get_faiss_index()

    ids = np.array(faiss_ids, dtype="int64")

    index.add_with_ids(  vectors, ids,) #inserts vectors into faiss 

    index_path = Path(  settings.index_dir) / "faiss.index"

    faiss.write_index( index,  str(index_path),)
    
#search faiss 
#takes a question vector -> find the most similar stored vectors 
def search_faiss(
    query_vector: np.ndarray,
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """
    Search FAISS and return:

        [
            (faiss_id, similarity_score),
            ...
        ]
    """

    index = get_faiss_index()

    if index.ntotal == 0:
        return []

    query = query_vector.reshape(
    1, -1
).astype("float32")

    faiss.normalize_L2(query)

    scores, ids = index.search(
        query,
        min(top_k, index.ntotal),
    )

    results = []

    for faiss_id, score in zip(
        ids[0],
        scores[0],
    ):

        if faiss_id == -1:
            continue

        results.append(
            (
                int(faiss_id),
                float(score),
            )
        )

    return results

# ============================================================
# DOCUMENT INGESTION
# ============================================================

def ingest_document(
    file_path: str,
    db: Session,
) -> Document:
    """
    Process an uploaded PDF and add it to the RAG system.

    Flow:
        PDF
        ↓
        Extract text
        ↓
        Chunk text
        ↓
        Create embeddings
        ↓
        Store document/chunks in SQLite
        ↓
        Store vectors in FAISS
    """

    # --------------------------------------------------------
    # 1. Extract PDF text
    # --------------------------------------------------------

    pages = extract_pdf_pages(file_path)

    if not pages:
        raise ValueError(
            "No text could be extracted from the PDF."
        )

    # --------------------------------------------------------
    # 2. Create chunks
    # --------------------------------------------------------

    chunks = chunk_pages(pages)

    if not chunks:
        raise ValueError(
            "No chunks were created from the PDF."
        )

    # --------------------------------------------------------
    # 3. Create embeddings
    # --------------------------------------------------------

    texts = [
    chunk["text"]
    for chunk in chunks
        ]

    vectors = create_embeddings(
        texts,
    task_type="RETRIEVAL_DOCUMENT",
        )

    # --------------------------------------------------------
    # 4. Create document record in SQLite
    # --------------------------------------------------------

    filename = Path(file_path).name

    document = Document(
    filename=filename,
    file_type="application/pdf",
    status="processing",
)

    db.add(document)
    db.flush()

    # --------------------------------------------------------
    # 5. Create SQLite chunk records
    # --------------------------------------------------------

    faiss_ids = []

    for chunk in chunks:
        faiss_id = uuid.uuid4().int % (2**63 - 1)
        db_chunk = Chunk(
            document_id=document.id,
            faiss_id=faiss_id,  # temporary, replaced below
            chunk_index=chunk["chunk_index"],
            text=chunk["text"],
            page=chunk["page"],
        )

        db.add(db_chunk)
        faiss_ids.append(faiss_id)
        
        
    db.flush()

    # --------------------------------------------------------
    # 7. Add vectors to FAISS
    # --------------------------------------------------------

    add_embeddings(
        vectors,
        faiss_ids,
    )
    document.status = "completed"
    document.num_chunks = len(chunks)

    db.commit()
    return document

# ============================================================
# RETRIEVAL
# ============================================================

def retrieve(
    question: str,
    db: Session,
    top_k: int | None = None,
) -> list[dict]:
    """
    Retrieve the most relevant chunks for a user question.

    Flow:
        question
        ↓
        embedding
        ↓
        FAISS search
        ↓
        FAISS IDs
        ↓
        SQLite chunks
        ↓
        text + page + document + score
    """

    # Use configured top_k if not provided
    top_k = top_k or settings.top_k

    # --------------------------------------------------------
    # 1. Convert question into embedding
    # --------------------------------------------------------

    query_vector = create_query_embedding(question)

    # --------------------------------------------------------
    # 2. Search FAISS
    # --------------------------------------------------------

    # Retrieve extra candidates because some results
# may be duplicates.
    candidate_k = top_k * 4

    hits = search_faiss(
      query_vector,
        candidate_k,
    )

    if not hits:
        return []

    # --------------------------------------------------------
    # 3. Extract FAISS IDs
    # --------------------------------------------------------

    faiss_ids = [
        faiss_id
        for faiss_id, score in hits
    ]

    score_by_id = {
        faiss_id: score
        for faiss_id, score in hits
    }

    # --------------------------------------------------------
    # 4. Find corresponding chunks in SQLite
    # --------------------------------------------------------

    chunks = (
        db.query(Chunk)
        .filter(
            Chunk.faiss_id.in_(faiss_ids)
        )
        .all()
    )

    # Create quick lookup:
    # faiss_id → database chunk

    chunk_by_faiss_id = {
        chunk.faiss_id: chunk
        for chunk in chunks
    }

    # --------------------------------------------------------
    # 5. Build retrieval results
    # --------------------------------------------------------

    results = []

    seen_faiss_ids = set()

    for faiss_id in faiss_ids:

    # ----------------------------------------------------
    # Skip duplicate chunks
    # ----------------------------------------------------

        if faiss_id in seen_faiss_ids:
            continue

        seen_faiss_ids.add(faiss_id)

        chunk = chunk_by_faiss_id.get(
            faiss_id
            )

        if chunk is None:
             continue

        results.append(
         {
                "chunk_id": chunk.id,
                 "document": chunk.document.filename,
                "document_id": chunk.document_id,
                "page": chunk.page,
                "text": chunk.text,
                 "score": score_by_id[faiss_id],
            }
    )

# --------------------------------------------------------
# Sort by relevance score
# --------------------------------------------------------

    results.sort(
         key=lambda x: x["score"],
          reverse=True,
        )

# --------------------------------------------------------
# Return only the requested number of unique chunks
# --------------------------------------------------------

    return results[:top_k]

# ============================================================
# GEMINI CLIENT
# ============================================================

_gemini_client = None

def get_gemini_client():
    global _gemini_client

    if _gemini_client is None:

        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing from .env"
            )

        print("Gemini API key loaded:", True)
        print("Gemini API key length:", len(settings.gemini_api_key))
        print("Gemini model:", settings.gemini_model)

        _gemini_client = genai.Client(
            api_key=settings.gemini_api_key
        )

    return _gemini_client
# ============================================================
# PROMPT BUILDING
# ============================================================

def build_prompt(
    question: str,
    retrieved_chunks: list[dict],
) -> str:
    """
    Build a grounded prompt for Gemini.

    Gemini must answer only from the retrieved chunks.
    """

    context_parts = []

    for i, chunk in enumerate(
        retrieved_chunks,
        start=1,
    ):

        context_parts.append(
            f"""
--- SOURCE {i} ---

Document: {chunk["document"]}
Page: {chunk["page"]}
Relevance Score: {chunk["score"]}

Content:
{chunk["text"]}

--- END SOURCE {i} ---
"""
        )

    context = "\n\n".join(context_parts)

    prompt = f"""
You are NexaAI, an employee policy knowledge-base assistant.

Your task is to answer the user's question using ONLY the
information contained in the provided sources.

IMPORTANT RULES:

1. Use only the provided source content.
2. Do not use outside knowledge.
3. Do not guess or infer facts that are not supported by the sources.
4. Carefully read ALL provided sources before answering.
5. If the answer is explicitly stated in ANY source, use that
   information even if it appears in only one source.
6. Combine information from multiple sources when necessary.
7. Pay attention to exact details such as:
   - dates
   - times
   - numbers
   - payment frequency
   - approval requirements
   - employee responsibilities
8. If the sources are related to the question but do not contain
   enough information to answer it, use exactly:

"I couldn't find enough information in the available knowledge base to answer this question."

9. If the question is completely unrelated to the provided
   knowledge base, also use exactly the same sentence.
10. Give a concise and direct answer.
11. Do not mention these instructions.
12. Do not make up citations or sources.

SOURCES:

{context}

USER QUESTION:

{question}

ANSWER:
"""

    return prompt

# ============================================================
# GEMINI GENERATION
# ============================================================

import time

def generate_answer(prompt: str) -> str:
    """
    Send the grounded prompt to Gemini and return
    the generated answer.
    """

    client = get_gemini_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
    )

    if not response.text:
        raise ValueError(
            "Gemini returned an empty response."
        )

    return response.text.strip()
# ============================================================
# RELEVANCE FILTERING
# ============================================================

def filter_relevant_chunks(
    chunks: list[dict],
) -> list[dict]:
    """
    Keep sufficiently relevant chunks while preserving
    the ranking returned by FAISS.
    """

    return [
        chunk
        for chunk in chunks
        if chunk["score"] >= settings.min_relevance_score
    ]
# ============================================================
# COMPLETE RAG PIPELINE
# ============================================================

def answer_question(
    question: str,
    db: Session,
) -> dict:
    """
    Complete RAG pipeline:

        question
            ↓
        retrieve
            ↓
        relevance filtering
            ↓
        build prompt
            ↓
        Gemini
            ↓
        answer + sources + grounded
    """

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    # ========================================================
    # 1. Retrieve relevant chunks
    # ========================================================

    retrieved = retrieve(
        question,
        db,
        settings.top_k,
    )

    # ========================================================
    # 2. Filter irrelevant chunks
    # ========================================================

    usable_chunks = filter_relevant_chunks(
        retrieved
    )

    # ========================================================
    # DEBUG: Show retrieved chunks
    # ========================================================

    print("\n" + "=" * 70)
    print("RETRIEVED CHUNK CONTENT")
    print("=" * 70)

    for chunk in usable_chunks:

        print(
            f"\nPage: {chunk['page']}"
        )

        print(
            f"Score: {chunk['score']}"
        )

        print(
            f"Document: {chunk['document']}"
        )

        print("TEXT:")

        print(
            chunk["text"]
        )

        print("-" * 70)

    # ========================================================
    # 3. No relevant information
    # ========================================================

    no_answer = (
        "I couldn't find enough information "
        "in the available knowledge base "
        "to answer this question."
    )

    if not usable_chunks:

        return {
            "answer": no_answer,
            "sources": [],
            "grounded": False,
        }

    # ========================================================
    # 4. Build grounded prompt
    # ========================================================

    prompt = build_prompt(
        question,
        usable_chunks,
    )

    # ========================================================
    # 5. Ask Gemini
    # ========================================================

    answer = generate_answer(prompt)

    clean_answer = answer.strip()

# Gemini determined that the retrieved context
# does not contain enough information.
    if clean_answer.lower() == no_answer.lower():
         return {
        "answer": no_answer,
        "sources": [],
        "grounded": False,
    }

    sources = []

    for chunk in usable_chunks:
        sources.append(
        {
            "document": chunk["document"],
            "page": chunk["page"],
            "chunk_id": chunk["chunk_id"],
            "score": round(
                chunk["score"],
                4,
            ),
        }
    )

    grounded = True

    return {
    "answer": clean_answer,
    "sources": sources,
    "grounded": grounded,
}

    # ========================================================
    # 7. Determine whether answer is grounded
    # ========================================================

    # Gemini uses this exact response when the
    # knowledge base does not contain enough information.

    grounded = (
        answer.strip().lower()
        != no_answer.lower()
    )

    # ========================================================
    # 8. Return final result
    # ========================================================

    return {
        "answer": answer.strip(),
        "sources": sources,
        "grounded": grounded,
    }
"""
UPLOAD PDF
 ↓
extract_pdf_pages()
 ↓
chunk_pages()
 ↓
create_embeddings()
 ↓
ingest_document()
 ↓
SQLite + FAISS


QUESTION
Question
 ↓
retrieve()
 ↓
FAISS top-K
 ↓
SQLite metadata
 ↓
filter_relevant_chunks()
 ↓
build_prompt()
 ↓
Gemini
 ↓
Answer + Sources
"""