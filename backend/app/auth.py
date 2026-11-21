from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_security = HTTPBearer(auto_error=False)

def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Security(bearer_security),
    query_key: Optional[str] = None
) -> bool:
    """
    Validates API key from either 'X-API-Key' header, 'Authorization: Bearer <key>', or 'api_key' query param.
    If API_KEY_ENABLED is False (development default), requests pass through unhindered.
    """
    if not settings.API_KEY_ENABLED:
        return True

    provided_key = None
    if header_key and isinstance(header_key, str):
        provided_key = header_key.strip()
    elif bearer_token and getattr(bearer_token, "credentials", None) and isinstance(bearer_token.credentials, str):
        provided_key = bearer_token.credentials.strip()
    elif query_key and isinstance(query_key, str):
        provided_key = query_key.strip()

    if not provided_key or provided_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing DataNexus API key. Provide via 'X-API-Key' header, 'Bearer' token, or 'api_key' query parameter.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return True

