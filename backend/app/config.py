import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "datanexus_dev_secret_key_change_in_production"
    
    # Storage
    STORAGE_DIR: str = str(BASE_DIR / "data" / "storage")
    MAX_UPLOAD_SIZE_MB: int = 25
    
    # Database (PostgreSQL or SQLite fallback for immediate local testing)
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'datanexus.db'}"
    
    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ELASTICSEARCH_INDEX: str = "datanexus_documents"
    ELASTICSEARCH_USERNAME: str = ""
    ELASTICSEARCH_PASSWORD: str = ""
    
    # Queue
    QUEUE_BROKER: str = "database"  # 'database', 'memory', or 'redis'
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Embeddings
    EMBEDDING_PROVIDER: str = "local_dense"  # 'local_dense', 'local_tfidf', or 'gemini'
    EMBEDDING_MODEL_NAME: str = "tfidf-l2-384"
    
    # LLM
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-1.5-flash"
    
    # CORS
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

settings = Settings()

# Ensure local directories exist
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
os.makedirs(str(BASE_DIR / "data" / "exports"), exist_ok=True)
os.makedirs(str(BASE_DIR / "data" / "staging"), exist_ok=True)
