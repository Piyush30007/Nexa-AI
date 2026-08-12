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

    #database link stuff 
    database_url: str = "sqlite:///./data/nexaai.db"

    #faiss storage 
    upload_dir: str = "./data/uploads"
    index_dir: str = "./data/index"

    #embediings 
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    #chunking 
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 100

    #reterival what we need 
    top_k: int = 5

    #if the retrerival score is lees than this model will say i doesnt know means it is out context 
    min_relevance_score: float = 0.40

    #react frontend 
    
    frontend_origin: str = "http://localhost:5173"

    #cost_estination for paid pricing for 2.5 flash model gemini for 1k input token 
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

        Path(
            self.database_url.replace("sqlite:///", "")
        ).parent.mkdir(
            parents=True,
            exist_ok=True,
        )


settings = Settings()
settings.ensure_dirs()