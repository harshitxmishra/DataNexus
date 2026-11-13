from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from backend.app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_security = HTTPBearer(auto_error=False)

def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Security(bearer_security)
) -> bool:
    """
    Validates API key from either 'X-API-Key' header or 'Authorization: Bearer <key>'.
    If API_KEY_ENABLED is False (development default), requests pass through unhindered.
    """
    if not settings.API_KEY_ENABLED:
        return True

    provided_key = None
    if header_key:
        provided_key = header_key.strip()
    elif bearer_token and bearer_token.credentials:
        provided_key = bearer_token.credentials.strip()

    if not provided_key or provided_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing DataNexus API key. Provide via 'X-API-Key' header or 'Bearer' token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return True

