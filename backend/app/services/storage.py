import os
import hashlib
import re
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException
from backend.app.config import settings

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
    # Remove any non-alphanumeric except dots, dashes, underscores
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", basename)
    return sanitized or "unnamed_document"

class StorageService:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or settings.STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

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

        # Store using hash-prefixed safe name
        safe_stored_filename = f"{file_hash[:12]}_{filename}"
        target_path = self.storage_dir / safe_stored_filename

        with open(target_path, "wb") as f:
            f.write(content)

        return file_hash, str(target_path), file_size, filename, detected_type

    def read_file(self, storage_path: str) -> bytes:
        path = Path(storage_path)
        if not path.is_file():
            raise FileNotFoundError(f"Stored file not found: {storage_path}")
        return path.read_bytes()

    def delete_file(self, storage_path: str) -> bool:
        try:
            path = Path(storage_path)
            if path.is_file():
                path.unlink()
                return True
        except Exception:
            return False
        return False

storage_service = StorageService()
