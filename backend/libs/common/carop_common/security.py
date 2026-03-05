from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings

bearer_scheme = HTTPBearer(auto_error=True)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc


async def current_principal(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    payload = decode_token(creds.credentials)
    if "sub" not in payload or "roles" not in payload:
        raise HTTPException(status_code=401, detail="Malformed token")
    return payload


def require_role(required_role: str) -> Callable:
    async def _role_check(principal: dict = Depends(current_principal)) -> dict:
        roles = principal.get("roles", [])
        if required_role not in roles and "admin" not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return principal

    return _role_check


async def correlation_id(request: Request) -> str:
    cid = request.headers.get("x-correlation-id")
    return cid or f"carop-{int(now_utc().timestamp() * 1000)}"
