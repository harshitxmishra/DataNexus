"""
DataNexus v2.0.0 — Cloud-Native Hybrid Storage Adapter.

Abstracts raw binary storage behind a clean StorageBackend interface:
  - LocalStorageBackend: local filesystem storage with path sanitization and SHA-256 deduplication
  - S3StorageBackend: AWS S3 storage keyed by SHA-256 hash, SSE-S3 encryption, and presigned URLs for PDF.js

Gated behind STORAGE_BACKEND=s3|local (default: local).
"""

import hashlib
import io
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile

from backend.app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "text/csv": ".csv",
    "application/vnd.ms-excel": ".csv",
}


def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters and directory traversal patterns."""
    basename = os.path.basename(filename)
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", basename)
    return sanitized or "unnamed_document"


class StorageBackend(ABC):
    """Abstract interface for raw binary storage."""

    @abstractmethod
    def save(self, content: bytes, filename: str, file_hash: str) -> str:
        """Persist binary and return storage path / identifier."""
        pass

    @abstractmethod
    def read(self, storage_path: str) -> bytes:
        """Read binary from storage path / identifier."""
        pass

    @abstractmethod
    def delete(self, storage_path: str) -> bool:
        """Delete binary at storage path / identifier."""
        pass

    @abstractmethod
    def get_download_url(self, storage_path: str, filename: str) -> Optional[str]:
        """Return direct/presigned download URL if supported, else None."""
        pass

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """Check if file exists in storage."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or settings.STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, filename: str, file_hash: str) -> str:
        safe_stored_filename = f"{file_hash[:12]}_{filename}"
        target_path = self.storage_dir / safe_stored_filename
        with open(target_path, "wb") as f:
            f.write(content)
        return str(target_path)

    def read(self, storage_path: str) -> bytes:
        path = Path(storage_path)
        if not path.is_file():
            raise FileNotFoundError(f"Stored file not found: {storage_path}")
        return path.read_bytes()

    def delete(self, storage_path: str) -> bool:
        try:
            path = Path(storage_path)
            if path.is_file():
                path.unlink()
                return True
        except Exception as e:
            logger.warning(f"Failed deleting local file {storage_path}: {e}")
        return False

    def get_download_url(self, storage_path: str, filename: str) -> Optional[str]:
        return None

    def exists(self, storage_path: str) -> bool:
        return Path(storage_path).is_file()


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend with server-side encryption and presigned URLs."""

    def __init__(self):
        self.bucket_name = getattr(settings, "AWS_S3_BUCKET", "")
        self.region = getattr(settings, "AWS_REGION", "us-east-1")
        self.url_expiry = getattr(settings, "S3_PRESIGNED_URL_EXPIRY", 3600)
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            import boto3
            from botocore.config import Config

            kwargs = {
                "region_name": self.region,
                "config": Config(signature_version="s3v4", retries={"max_attempts": 3})
            }
            access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
            secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
            if access_key and secret_key:
                kwargs["aws_access_key_id"] = access_key
                kwargs["aws_secret_access_key"] = secret_key

            self._client = boto3.client("s3", **kwargs)
            logger.info(f"S3StorageBackend initialized for bucket '{self.bucket_name}' in {self.region}")
        except Exception as e:
            logger.warning(f"S3 client initialization failed: {e}")
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None and bool(self.bucket_name)

    def _get_key(self, storage_path: str) -> str:
        """Strip 's3://bucket/' prefix if present, otherwise treat as S3 object key."""
        if storage_path.startswith("s3://"):
            parts = storage_path[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else parts[0]
        return storage_path

    def save(self, content: bytes, filename: str, file_hash: str) -> str:
        if not self.is_available():
            raise RuntimeError("S3 storage backend is not properly configured or client failed to initialize.")

        ext = os.path.splitext(filename)[1].lower() or ".bin"
        s3_key = f"documents/{file_hash[:16]}_{filename}"
        
        content_type = "application/pdf" if ext == ".pdf" else "application/octet-stream"

        try:
            self._client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
                ServerSideEncryption="AES256",
                Metadata={
                    "original_filename": filename,
                    "sha256": file_hash,
                }
            )
            return f"s3://{self.bucket_name}/{s3_key}"
        except Exception as e:
            logger.error(f"S3 upload failed for {s3_key}: {e}")
            raise

    def read(self, storage_path: str) -> bytes:
        if not self.is_available():
            raise RuntimeError("S3 storage backend unavailable.")
        s3_key = self._get_key(storage_path)
        try:
            resp = self._client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return resp["Body"].read()
        except Exception as e:
            logger.error(f"S3 get_object failed for {s3_key}: {e}")
            raise FileNotFoundError(f"S3 file not found or unreadable: {storage_path}")

    def delete(self, storage_path: str) -> bool:
        if not self.is_available():
            return False
        s3_key = self._get_key(storage_path)
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception as e:
            logger.warning(f"S3 delete_object failed for {s3_key}: {e}")
            return False

    def get_download_url(self, storage_path: str, filename: str) -> Optional[str]:
        if not self.is_available():
            return None
        s3_key = self._get_key(storage_path)
        try:
            url = self._client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,
                    "ResponseContentDisposition": f'inline; filename="{filename}"'
                },
                ExpiresIn=self.url_expiry
            )
            return url
        except Exception as e:
            logger.warning(f"Failed generating presigned URL for {s3_key}: {e}")
            return None

    def exists(self, storage_path: str) -> bool:
        if not self.is_available():
            return False
        s3_key = self._get_key(storage_path)
        try:
            self._client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception:
            return False


class StorageService:
    """
    Facade storage service orchestrating storage backends, validation,
    hash computation, and local disk synchronization for extraction tools.
    """

    def __init__(self, backend: Optional[StorageBackend] = None):
        self._local_backend = LocalStorageBackend()
        self._s3_backend = S3StorageBackend() if getattr(settings, "STORAGE_BACKEND", "local") == "s3" else None
        self._backend = backend or (self._s3_backend if self._s3_backend and self._s3_backend.is_available() else self._local_backend)

    @property
    def backend_type(self) -> str:
        return "s3" if isinstance(self._backend, S3StorageBackend) else "local"

    def calculate_file_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of binary content."""
        hasher = hashlib.sha256()
        hasher.update(content)
        return hasher.hexdigest()

    async def save_upload(self, file: UploadFile) -> Tuple[str, str, int, str, str]:
        """
        Validate, hash, and persist uploaded file.
        Returns: (file_hash, storage_path, file_size, sanitized_name, detected_type)
        """
        filename = sanitize_filename(file.filename or "uploaded_file")
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Cannot upload an empty file.")

        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        file_hash = self.calculate_file_hash(content)
        detected_type = file.content_type or "application/octet-stream"

        # Extension and magic byte checking
        ext = os.path.splitext(filename)[1].lower()
        if content.startswith(b"%PDF") or ext == ".pdf":
            detected_type = "application/pdf"
        elif content.startswith(b"\x89PNG") or ext == ".png":
            detected_type = "image/png"
        elif content.startswith(b"\xff\xd8\xff") or ext in [".jpg", ".jpeg"]:
            detected_type = "image/jpeg"
        elif ext == ".csv":
            detected_type = "text/csv"
        elif detected_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file format: {detected_type} ({ext}). Supported: PDF, PNG, JPG, CSV."
            )

        # In S3 mode, also ensure local cached copy exists so pypdf can stream/read locally if needed
        storage_path = self._backend.save(content, filename, file_hash)
        
        # If storing in S3, keep a local copy in local storage dir for fast offline parsing
        if isinstance(self._backend, S3StorageBackend):
            try:
                self._local_backend.save(content, filename, file_hash)
            except Exception as e:
                logger.debug(f"Local disk caching alongside S3 skipped: {e}")

        return file_hash, storage_path, file_size, filename, detected_type

    def read_file(self, storage_path: str) -> bytes:
        """Read bytes from active backend or fallback to local."""
        try:
            return self._backend.read(storage_path)
        except Exception:
            # Fallback to local if storage path points to local or local cache exists
            if self._local_backend.exists(storage_path):
                return self._local_backend.read(storage_path)
            raise

    def delete_file(self, storage_path: str) -> bool:
        """Delete from primary backend and local cache."""
        deleted = self._backend.delete(storage_path)
        if self._local_backend.exists(storage_path):
            self._local_backend.delete(storage_path)
        return deleted

    def get_download_url(self, storage_path: str, filename: str) -> Optional[str]:
        """Return presigned URL if backend supports it."""
        return self._backend.get_download_url(storage_path, filename)

    def ensure_local_copy(self, storage_path: str, filename: str, file_hash: str) -> str:
        """
        Guarantee that a valid local filesystem path exists for pypdf and extraction tools.
        If storage_path is an S3 URI, reads from S3 and caches locally.
        """
        if os.path.isfile(storage_path):
            return storage_path

        # If s3 URI or remote, write to local storage dir
        content = self.read_file(storage_path)
        return self._local_backend.save(content, filename, file_hash)


storage_service = StorageService()
