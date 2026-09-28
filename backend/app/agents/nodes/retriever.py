import logfire
from app.agents.state import AgentState
from app.services.retrieval.hybrid_service import hybrid_retrieve
from app.services.retrieval.ranking_services import rerank_documents

def retrieve_node(state: AgentState):
    """
    Performs hybrid retrieval (Dense Qdrant + Sparse BM25 with RRF)
    and FlashRank semantic reranking for technical queries.
    """
    query = state["current_query"]
    
    
    # Hybrid Retrieval Logic (Dense Vector + BM25 Sparse + RRF)
    with logfire.span("🔍 Knowledge Retrieval (Hybrid: Qdrant + BM25)"):
        logfire.info(f"Executing hybrid retrieval for: {query}")
        raw_results = hybrid_retrieve(query, limit=15)
        logfire.info(f"Retrieved {len(raw_results)} fused candidates (Dense + BM25)")
        
        # doc_contents = [doc['content'] for doc in raw_results]
        
        with logfire.span("⚖️ Semantic Reranking"):
            reranked_contents = rerank_documents(query, raw_results, top_n=5)
            for doc in reranked_contents:
                if "score" in doc:
                    doc["score"] = float(doc["score"])

                if "rerank_score" in doc:
                    doc["rerank_score"] = float(doc["rerank_score"])

            logfire.info("Reranking complete. Kept top 5 most relevant chunks.")
            
        # formatted_docs = [f"CONTENT: {doc['content']}\nSOURCE: {doc['source']}" for doc in reranked_contents]
        # print("formatted docs:", reranked_contents)
    
    return {
        "documents": reranked_contents,
        "status": f"Found technical context.",
        "plan": state["plan"] + ["Context Retrieved"]
    }   