"""FastAPI dependencies for Supabase-authenticated requests."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.database.supabase import create_service_role_client, create_user_client

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated Supabase user and user-scoped Supabase client."""

    user_id: str
    email: str | None
    access_token: str
    supabase: Client


def _unauthorized(detail: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Verify a Supabase bearer token and return the authenticated user."""

    if credentials is None:
        raise _unauthorized("Missing bearer token")

    access_token = credentials.credentials.strip()
    if not access_token:
        raise _unauthorized("Missing bearer token")

    try:
        user_response = create_service_role_client().auth.get_user(access_token)
    except Exception as exc:
        raise _unauthorized() from exc

    auth_user = getattr(user_response, "user", None)
    user_id = getattr(auth_user, "id", None)
    if not user_id:
        raise _unauthorized()

    return CurrentUser(
        user_id=str(user_id),
        email=getattr(auth_user, "email", None),
        access_token=access_token,
        supabase=create_user_client(access_token),
    )


__all__ = ["CurrentUser", "get_current_user"]
