import asyncio

from app.auth import CurrentUser
from app.main import app, read_auth_me


def test_auth_me_route_is_registered() -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/auth/me" in paths


def test_auth_me_returns_current_user() -> None:
    current_user = CurrentUser(
        user_id="auth-user-id",
        email="analyst@example.com",
        access_token="valid-token",
        supabase=object(),
    )

    response = asyncio.run(read_auth_me(current_user))

    assert response.model_dump() == {"user_id": "auth-user-id", "email": "analyst@example.com"}
