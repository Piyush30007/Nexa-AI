"""
In-Memory Caching Service
=========================

DEVELOPMENT ONLY — IN-MEMORY
----------------------------
This cache implementation uses an in-memory dictionary with TTL-based expiration.
It is intended for local development and testing to reduce API usage and latency.
For production deployment, this in-memory backend will be replaced by a distributed
cache (e.g., Redis or Upstash) while preserving this exact cache interface (get, set,
clear, delete).
NOTE: This in-memory cache is local to the current process and is NOT shared across
multiple production instances or workers.
"""

import time
import hashlib
from typing import Any, Dict, Optional, List, Tuple
from threading import Lock
import numpy as np 
from app.config import settings


class InMemoryCache:
    """
    Thread-safe, simple in-memory cache with TTL-based item expiration.
    Supports get, set, delete, clear, and automatic expiration handling.
    """

    def __init__(self, default_ttl: int = 3600, name: str = "cache"):
        self.default_ttl = default_ttl
        self.name = name
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve an item from the cache.
        Returns None if key does not exist or has expired.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            expires_at = entry.get("expires_at")
            if expires_at is not None and time.time() > expires_at:
                del self._store[key]
                return None

            return entry.get("value")

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store an item in the cache with an optional TTL in seconds.
        If ttl is not provided, defaults to self.default_ttl.
        """
        effective_ttl = self.default_ttl if ttl is None else ttl
        expires_at = (time.time() + effective_ttl) if effective_ttl and effective_ttl > 0 else None

        with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": expires_at,
            }

    def delete(self, key: str) -> bool:
        """
        Delete an item from the cache by key.
        Returns True if item existed, False otherwise.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """
        Clear all entries from the cache.
        """
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# SEMAXTIC CACHE
class SemanticCache:
    """
    Thread Safe in memory semantic cache using vectorizzed cosine similarity 
    Matches queries based on semantic embedding similarity>=threshold 
    """
    def __init__(self , default_ttl: int = 3600, max_entries: int = 1000, threshold: float = 0.94 , name: str = "semantic_cache"):
        self.default_ttl = default_ttl
        self.threshold = threshold
        self.max_entries = max_entries
        self.name = name
        self._entries: List[Dict[str, Any]] = []
        self._lock = Lock()

    def search(self , query_vector : List[float] , history_digest : str ="no_hist" , threshold : Optional[float]=None )->Optional[Tuple[Dict[str,Any],float]]:
        """
        Search the cache for the best matching entry based on semantic similarity.
        Returns the best match and similarity score, or None if no match is found.
        """ 
        # yaha pe history_digest ek identifier jo conversation context ko represent karta hai cache context isi se compare hota hai 
        # taki ek context dusre contexxt se reused na ho 
        effective_threshold = self.threshold if threshold is None else threshold
        now = time.time()
        with self._lock:
            # Purge expired entries
            self._entries = [e for e in self._entries if e.get("expires_at") is None or e["expires_at"] > now ]

            
            if not self._entries:
                return None
            
            #2 Filter Candidates Matching the same conversation context
            candidates = [e for e in self._entries if e.get("history_digest")== history_digest]

            
            if not candidates:
                return None


            #3 Compute cosine simliarity scores against query_vector
            # Convert query to numpy array
            q_vec = np.array(query_vector, dtype=np.float32)

            q_norm = np.linalg.norm(q_vec)
            if q_norm == 0:
                return None
                
            q_unit = q_vec / q_norm

            candidate_matrix = np.array([e["embedding"] for e in candidates] , dtype = np.float32)
            #dot product with pre normalized candidate vectors 
            similarities = np.dot(candidate_matrix , q_unit)
            best_idx = int(np.argmax(similarities))
            best_score = float(similarities[best_idx])

            if best_score>=effective_threshold:
                return candidates[best_idx]["value"], best_score

            else:
                return None

    def set(self , query_vector : List[float] , value : Any , history_digest : str = "no_hist" , ttl : Optional[int]=None):
        """
        Stores an entry with pre-normalized unit vector for fast sub-millisecond dot product
        """
        effective_ttl=self.default_ttl if ttl is None else ttl
        expires_at = (time.time() + effective_ttl) if effective_ttl and effective_ttl > 0 else None

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return
        
        q_unit = q_vec/q_norm

        with self._lock:
            #FIFO eviction if at capacity 
            if len(self._entries)>=self.max_entries:
                self._entries.pop(0) #remove oldest
            
            # add new entry 
            self._entries.append({
                "embedding": q_unit,
                "value": value,
                "history_digest": history_digest,
                "expires_at": expires_at,
                "added_at": time.time()
            })
    def clear(self) -> None:
        """Clear entire cache"""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        """Return current size (approximate if concurrent access)"""
        with self._lock:
            return len(self._entries)
    

# ---------------------------------------------------------------------------
# Cache Key Generation Utilities
# ---------------------------------------------------------------------------

def normalize_query_for_cache(query: str) -> str:
    """
    Normalizes a query string for cache key generation ONLY:
    - strip leading/trailing whitespace
    - collapse repeated internal whitespace
    - lowercase
    Does NOT alter the original query passed to Planner or retrieval.
    """
    if not query:
        return ""
    return " ".join(query.strip().lower().split())


def generate_embedding_cache_key(query: str, model: str = "models/gemini-embedding-2-preview") -> str:
    """
    Generates a deterministic cache key for Gemini query embeddings.
    Format: embedding:<model>:<normalized_query>
    """
    norm_q = normalize_query_for_cache(query)
    return f"embedding:{model}:{norm_q}"


def generate_response_cache_key(
    query: str,
    documents: List[Dict[str, Any]],
    sufficient: bool,
    missing_info: str = "",
    history_str: str = "",
    model: Optional[str] = None,
    prompt_version: str = "v2"
) -> str:
    """
    Generates a deterministic cache key for LLM responses.
    Accounts for:
    - normalized query
    - retrieved evidence digest (hash of sources + contents)
    - sufficiency status & missing information
    - conversation history digest (if present)
    - model identifier & prompt version

    Prevents stale answers when documents change in vector store.
    Never includes API keys, timestamps, or transient session IDs.
    """
    norm_q = normalize_query_for_cache(query)

    # Build deterministic evidence digest from retrieved documents
    # Each doc chunk text and source contribute directly to the digest
    evidence_parts = []
    for doc in documents:
        if isinstance(doc, dict):
            src = str(doc.get("source", "")).strip()
            content = str(doc.get("content", "")).strip()
        else:
            src = "Unknown"
            content = str(doc).strip()
        evidence_parts.append(f"{src}:{content}")

    # Hash the combined evidence
    raw_evidence_str = "||".join(evidence_parts)
    evidence_digest = hashlib.sha256(raw_evidence_str.encode("utf-8")).hexdigest()[:16] if evidence_parts else "no_docs"

    target_model = model or getattr(settings, "PORTKEY_MODEL", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile"
    suff_tag = "suff_1" if sufficient else f"suff_0:{normalize_query_for_cache(missing_info)[:32]}"
    history_digest = hashlib.sha256(history_str.strip().encode("utf-8")).hexdigest()[:16] if history_str and history_str.strip() else "no_hist"

    return f"llm_response:{target_model}:{prompt_version}:{norm_q}:{evidence_digest}:{suff_tag}:{history_digest}"


# ---------------------------------------------------------------------------
# Global Cache Instances
# ---------------------------------------------------------------------------

# Dedicated cache for Gemini query embeddings
embedding_cache = InMemoryCache(
    default_ttl=getattr(settings, "EMBEDDING_CACHE_TTL", 3600),
    name="embedding_cache"
)

# Dedicated cache for LLM responses
response_cache = InMemoryCache(
    default_ttl=getattr(settings, "RESPONSE_CACHE_TTL", 3600),
    name="response_cache"
)
#Semantic cache 

semantic_cache = SemanticCache(
    default_ttl=getattr(settings, "SEMANTIC_CACHE_TTL", 3600),
    max_entries=getattr(settings, "SEMANTIC_CACHE_MAX_ENTRIES", 1000),
    threshold=getattr(settings, "SEMANTIC_CACHE_THRESHOLD", 0.94),
    name="semantic_cache"
)
