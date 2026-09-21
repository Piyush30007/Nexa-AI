import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- GEMINI EMBEDDINGS ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # --- VECTOR DB (QDRANT) ---
    QDRANT_URL = os.getenv("QDRANT_CLUSTER_ENDPOINT")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_COLLECTION = "enterprise_rag"

    # --- REASONING ENGINE (GROQ) ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_API_KEY = os.getenv("GROQ_FALLBACK_API_KEY")

    # --- LLM GATEWAY (PORTKEY) ---
    PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")
    PORTKEY_CONFIG_ID = os.getenv("PORTKEY_CONFIG_ID")
    PORTKEY_MODEL = os.getenv("PORTKEY_MODEL")
    GROQ_SLUG =  "rag"     # primary: @rag/llama-3.3-70b-versatile
    GROQ_SLUG_2 = "brag"  # fallback: @brag/llama-3.1-8b-instant

    
    # --- CACHING (IN-MEMORY FOR DEV) ---
    EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", "3600"))
    RESPONSE_CACHE_TTL = int(os.getenv("RESPONSE_CACHE_TTL", "3600"))

    # --- OBSERVABILITY ---
    LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true")
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "rag_scale_test")
    LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

    # --- AUTHENTICATION (CLERK) ---
    CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "")
    CLERK_AUTHORIZED_PARTIES = [
        p.strip()
        for p in os.getenv(
            "CLERK_AUTHORIZED_PARTIES",
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
        ).split(",")
        if p.strip()
    ]


# Apply LangChain environment variables for automatic tracing
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGSMITH_TRACING", "true")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "rag_scale_test")
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

settings = Settings()