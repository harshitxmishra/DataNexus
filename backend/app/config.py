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
    ELASTICSEARCH_TIMEOUT_SECONDS: float = 1.0
    ELASTICSEARCH_CA_CERTS: str = ""
    ELASTICSEARCH_VERIFY_CERTS: bool = True
    ELASTICSEARCH_MAX_RETRIES: int = 1
    ELASTICSEARCH_RETRY_ON_TIMEOUT: bool = True
    
    # Queue
    QUEUE_BROKER: str = "database"  # 'database', 'memory', or 'redis'
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Embeddings
    EMBEDDING_PROVIDER: str = "sentence_transformers"  # 'sentence_transformers', 'local_dense', or 'gemini'
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_MODEL_REVISION: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_CACHE_DIR: str = ""
    EMBEDDING_REPRESENTATION_VERSION: int = 2
    
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
