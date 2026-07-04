"""Supabase client construction for backend database access."""

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from app.config import settings


@lru_cache(maxsize=1)
def create_service_role_client() -> Client:
    """Return the backend-only Supabase client using the service-role key."""

    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def create_user_client(access_token: str) -> Client:
    """Return a Supabase client scoped to the authenticated user's bearer token."""

    token = access_token.strip()
    if not token:
        raise ValueError("access_token is required")

    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(
            headers={"Authorization": f"Bearer {token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


__all__ = ["create_service_role_client", "create_user_client"]
