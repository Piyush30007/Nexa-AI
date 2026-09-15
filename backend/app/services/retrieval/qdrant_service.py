import requests
import logfire

from app.config import settings
from app.services.embedding import embed_query


def search_enterprise_knowledge(query: str, limit: int = 8):
    """
    Performs a high-precision search in the enterprise knowledge base.
    Uses Qdrant REST API.
    """
    try:
        query_vector = embed_query(query)

        url = (
            f"{settings.QDRANT_URL}/collections/"
            f"{settings.QDRANT_COLLECTION}/points/query"
        )

        response = requests.post(
            url,
            headers={
                "api-key": settings.QDRANT_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "query": query_vector,
                "limit": limit,
                "with_payload": True,
            },
            timeout=30,
        )

        response.raise_for_status()

        points = response.json()["result"]["points"]

        results = []

        for res in points:
            payload = res.get("payload", {})

            results.append({
                "content": payload.get("text", ""),
                "source": payload.get("source", "Unknown"),
                "score": res.get("score", 0.0),
            })

        return results

    except Exception as e:
        logfire.error(f"Qdrant Search Failed: {e}")
        raise