import hashlib
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


async def current_principal(x_api_key: str | None = Header(default=None)) -> Principal:
    if not settings.demo_api_key and not settings.admin_api_key:
        return Principal(subject="local-demo", role="admin")
    if x_api_key and settings.admin_api_key and x_api_key == settings.admin_api_key:
        return Principal(subject="api-key-admin", role="admin")
    if x_api_key and settings.demo_api_key and x_api_key == settings.demo_api_key:
        return Principal(subject="api-key-analyst", role="analyst")
    raise HTTPException(status_code=401, detail="Missing or invalid API key")


async def admin_principal(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return principal
