import time 
import logfire 
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import settings 
from app.services.cache import embedding_cache, generate_embedding_cache_key 

BATCH_sIZE = 50
_GEMINI_DIM = 3072
# _FALLBACK_DIM = 768

 
_active_mmodel = None 
_model_type : str | None = None #gemini or fallback 

def  _probe_gemini():
    """Try One embed vall to verify if Gemini is available, and set the model type accordingly"""
    try :
        model = GoogleGenerativeAIEmbeddings(
            model = "models/gemini-embedding-2-preview",
            google_api_key = settings.GEMINI_API_KEY,
        )
        model.embed_query("probe")
        logfire.info("Gemini embedding ready (gemini embedding-2-preview , 3072 dim)")
        return model 
    except Exception as e:
        # logfire.warning(f"Gemini embedding not available, falling back to fallback embedding (768 dim): {e}")
        logfire.error(f"Gemini embedding is not available: {e}")
        return None

def  _load_fallback():
    from sentence_transformers import SentenceTransformer
    logfire.info("Loading fallback embedding model (all-mpnet-base-v2, 768 dim)")
    return SentenceTransformer("all-mpnet-base-v2")

def __init__():
    global _active_mmodel, _model_type
    if _active_mmodel is not None:
        return 
    gemini_model = _probe_gemini()
    # if gemini_model is not None:
    #     _active_mmodel = gemini_model
    #     _model_type = "gemini"
    # else:
    #     _active_mmodel = _load_fallback()
    #     _model_type = "fallback"
    if gemini_model is None:
        raise RuntimeError("Gemini Embedding model is unavailable")
    
    _active_mmodel = gemini_model 
    _model_type = "gemini"

def  get_embedding_dim()->int : 
    """
    Returns the current embedding dimension (-1 if unknown)
    """
    __init__()
    
    # return _GEMINI_DIM if _model_type == "gemini" else _FALLBACK_DIM if _model_type == "fallback" else -1
    return _GEMINI_DIM

def _embed_batch(batch : list[str])->list[list[float]]:
    
    if _model_type == "gemini":
        for attempt in range(4):
            try:
                return _active_mmodel.embed_documents(batch)
            except Exception as e:
                err = str(e).lower()
                is_rate_limit = any(x in err for x in ["rate limit", "quota exceeded", "429" , "too many requests" , "quota" , "resource exhausted" , "rate"])
                if is_rate_limit and attempt < 3:
                    wait = 2 ** attempt
                    logfire.warning(f"Rate limit error on Gemini embedding, retrying in {wait} seconds: {e}")
                    time.sleep(wait)
                else:
                    logfire.error(f"Error embedding batch with Gemini: {e}")
                    raise
                
        raise RuntimeError("Gemini rate limit persisted after 4 attempts.")
        
    else :
        # return _active_mmodel.encode(batch , show_progress_bar=False).tolist()
        raise RuntimeError("Gemini Embedding Model is unavailable")


def embed_query(query: str) -> list[float]:
    cache_key = generate_embedding_cache_key(query, model="models/gemini-embedding-2-preview")
    cached = embedding_cache.get(cache_key)
    if cached is not None:
        logfire.info("Embedding Cache HIT")
        return cached

    logfire.info("Embedding Cache MISS")
    __init__()
    embedding = _active_mmodel.embed_query(query)
    embedding_cache.set(cache_key, embedding, ttl=settings.EMBEDDING_CACHE_TTL)
    return embedding

def embed_texts(text : list[str])->list[list[float]]:
    __init__()
    all_embeddings : list[list[float]] = []
    for i in range(0, len(text), BATCH_sIZE):
        batch = text[i:i+BATCH_sIZE]
        with logfire.span("Embed batch" , model = _model_type , start = i , size = len(batch)):
            all_embeddings.extend(_embed_batch(batch))
            
    return all_embeddings