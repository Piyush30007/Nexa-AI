from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
#  gemini things will here 
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    # database link stuff (resolved relative to BASE_DIR)
    database_url: str = f"sqlite:///{Path(BASE_DIR / 'data' / 'nexaai.db').resolve().as_posix()}"

    # faiss storage & uploads (resolved relative to BASE_DIR)
    upload_dir: str = str(BASE_DIR / "data" / "uploads")
    index_dir: str = str(BASE_DIR / "data" / "index")
    sample_docs_dir: str = str(BASE_DIR / "sample_docs")

    # embeddings 
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    # chunking 
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 100

    # retrieval parameters
    top_k: int = 5

    # if retrieval score is less than this, query is considered out of context
    min_relevance_score: float = 0.40

    # react frontend 
    frontend_origin: str = "http://localhost:5173"

    # cost estimation for 1k tokens
    cost_per_1k_input_tokens: float = 0.0003
    cost_per_1k_output_tokens: float = 0.0025

    def ensure_dirs(self):
        Path(self.upload_dir).mkdir(
            parents=True,
            exist_ok=True,
        )

        Path(self.index_dir).mkdir(
            parents=True,
            exist_ok=True,
        )

        Path(self.sample_docs_dir).mkdir(
            parents=True,
            exist_ok=True,
        )

        if self.database_url.startswith("sqlite:///"):
            Path(
                self.database_url.replace("sqlite:///", "")
            ).parent.mkdir(
                parents=True,
                exist_ok=True,
            )


settings = Settings()
settings.ensure_dirs()