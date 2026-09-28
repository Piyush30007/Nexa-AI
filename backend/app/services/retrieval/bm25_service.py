import os
import re
import math
import json
from pathlib import Path
import logfire

# Optional rank_bm25 import with self-contained fallback
try:
    from rank_bm25 import BM25Okapi
    HAS_RANK_BM25 = True
except ImportError:
    HAS_RANK_BM25 = False


def _tokenize(text: str) -> list[str]:
    """Simple alphanumeric tokenization and lowercase normalization."""
    return re.findall(r"\w+", (text or "").lower())


class SimpleBM25:
    """
    Self-contained pure-Python Okapi BM25 engine for fast sparse keyword retrieval.
    Guarantees zero-dependency reliability even without external C-extensions.
    """
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.tokenized_corpus = [_tokenize(doc) for doc in corpus]
        self.doc_lens = [len(doc) for doc in self.tokenized_corpus]
        self.avgdl = sum(self.doc_lens) / max(1, self.corpus_size)
        
        # Calculate document frequencies
        self.df = {}
        for doc in self.tokenized_corpus:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1
                
        # Calculate IDF values
        self.idf = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.corpus_size
        for term in query_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]
            for idx, doc in enumerate(self.tokenized_corpus):
                term_count = doc.count(term)
                if term_count == 0:
                    continue
                num = term_count * (self.k1 + 1)
                denom = term_count + self.k1 * (1 - self.b + self.b * (self.doc_lens[idx] / self.avgdl))
                scores[idx] += idf_val * (num / denom)
        return scores


class BM25SearchService:
    """
    Manages in-memory document corpus and executes BM25 sparse keyword queries.
    """
    def __init__(self):
        self.documents: list[dict] = []
        self.engine = None
        self._load_corpus()

    def _load_corpus(self):
        """Loads chunks from local processed_data directories and sample docs."""
        self.documents = []
        base_dir = Path(__file__).resolve().parents[3]
        processed_dir = base_dir / "processed_data"

        if processed_dir.exists():
            for json_path in processed_dir.rglob("*.json"):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        filename = data.get("filename", json_path.name)
                        chunks = data.get("chunks", [])
                        for chunk in chunks:
                            text = chunk if isinstance(chunk, str) else chunk.get("text", "")
                            if text.strip():
                                self.documents.append({
                                    "content": text.strip(),
                                    "source": filename,
                                })
                except Exception as e:
                    logfire.warning(f"Failed to read chunk file {json_path}: {e}")

        # Initialize BM25 engine if documents exist
        if self.documents:
            corpus_texts = [doc["content"] for doc in self.documents]
            if HAS_RANK_BM25:
                tokenized = [_tokenize(t) for t in corpus_texts]
                self.engine = BM25Okapi(tokenized)
            else:
                self.engine = SimpleBM25(corpus_texts)
            logfire.info(f"BM25 initialized with {len(self.documents)} document chunks.")

    def add_documents(self, new_docs: list[dict]):
        """Dynamically add new document chunks into the BM25 index."""
        for doc in new_docs:
            if doc.get("content"):
                self.documents.append({
                    "content": doc["content"],
                    "source": doc.get("source", "Unknown"),
                })
        if self.documents:
            corpus_texts = [d["content"] for d in self.documents]
            if HAS_RANK_BM25:
                tokenized = [_tokenize(t) for t in corpus_texts]
                self.engine = BM25Okapi(tokenized)
            else:
                self.engine = SimpleBM25(corpus_texts)

    def search(self, query: str, limit: int = 8) -> list[dict]:
        """
        Executes BM25 keyword search.
        Returns top matching documents formatted identically to vector search results.
        """
        if not self.engine or not self.documents:
            self._load_corpus()

        if not self.engine or not self.documents:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        try:
            if HAS_RANK_BM25 and isinstance(self.engine, BM25Okapi):
                scores = self.engine.get_scores(tokens)
            else:
                scores = self.engine.get_scores(tokens)

            scored_docs = []
            for idx, score in enumerate(scores):
                if score > 0.0:
                    doc = self.documents[idx]
                    scored_docs.append({
                        "content": doc["content"],
                        "source": doc["source"],
                        "score": float(score),
                    })

            scored_docs.sort(key=lambda x: x["score"], reverse=True)
            return scored_docs[:limit]

        except Exception as e:
            logfire.error(f"BM25 Search failed: {e}")
            return []


# Global singleton instance
_bm25_instance = None


def get_bm25_service() -> BM25SearchService:
    global _bm25_instance
    if _bm25_instance is None:
        _bm25_instance = BM25SearchService()
    return _bm25_instance


def search_bm25(query: str, limit: int = 8) -> list[dict]:
    """Convenience search helper matching Qdrant service signature."""
    service = get_bm25_service()
    return service.search(query, limit=limit)
