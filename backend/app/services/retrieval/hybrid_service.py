import logfire
from app.services.retrieval.qdrant_service import search_enterprise_knowledge
from app.services.retrieval.bm25_service import search_bm25


def rrf_fuse(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = 60,
    limit: int = 15,
) -> list[dict]:
    """
    Combines dense vector search results and sparse BM25 keyword search results
    using Reciprocal Rank Fusion (RRF).

    Formula:
        RRF_Score(d) = sum( 1 / (k + rank_i(d)) )
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    # Score dense candidates
    for rank, doc in enumerate(dense_results):
        content = doc.get("content", "").strip()
        if not content:
            continue
        scores[content] = scores.get(content, 0.0) + (1.0 / (k + rank + 1))
        if content not in doc_map:
            doc_map[content] = doc

    # Score sparse (BM25) candidates
    for rank, doc in enumerate(sparse_results):
        content = doc.get("content", "").strip()
        if not content:
            continue
        scores[content] = scores.get(content, 0.0) + (1.0 / (k + rank + 1))
        if content not in doc_map:
            doc_map[content] = doc

    # Sort combined pool by fused RRF score
    sorted_contents = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)

    fused_results = []
    for content in sorted_contents[:limit]:
        item = dict(doc_map[content])
        item["rrf_score"] = scores[content]
        fused_results.append(item)

    return fused_results


def hybrid_retrieve(query: str, limit: int = 15) -> list[dict]:
    """
    Executes Hybrid Retrieval (Dense Vector Search + BM25 Sparse Search)
    and fuses candidate passages with Reciprocal Rank Fusion (RRF).
    """
    with logfire.span("🔄 Hybrid Retrieval (Dense + BM25)"):
        # 1. Dense Semantic Search (Qdrant)
        dense_candidates = []
        try:
            dense_candidates = search_enterprise_knowledge(query, limit=limit)
            logfire.info(f"Qdrant Dense retrieved {len(dense_candidates)} candidates.")
        except Exception as e:
            logfire.warning(f"Dense Qdrant search skipped/failed: {e}")

        # 2. Sparse Lexical Search (BM25)
        sparse_candidates = []
        try:
            sparse_candidates = search_bm25(query, limit=limit)
            logfire.info(f"BM25 Sparse retrieved {len(sparse_candidates)} candidates.")
        except Exception as e:
            logfire.warning(f"BM25 sparse search skipped/failed: {e}")

        # 3. Fuse with RRF
        if not dense_candidates and not sparse_candidates:
            return []

        if not dense_candidates:
            return sparse_candidates[:limit]

        if not sparse_candidates:
            return dense_candidates[:limit]

        fused = rrf_fuse(dense_candidates, sparse_candidates, k=60, limit=limit)
        logfire.info(f"Hybrid RRF fusion produced {len(fused)} unified candidates.")
        return fused
