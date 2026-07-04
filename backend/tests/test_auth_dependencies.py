from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import dependencies


def bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_verifies_token_and_returns_user_client(monkeypatch: pytest.MonkeyPatch) -> None:
    user_client = object()
    calls = []

    class DummyAuth:
        def get_user(self, access_token: str) -> object:
            calls.append(access_token)
            return SimpleNamespace(user=SimpleNamespace(id="auth-user-id", email="analyst@example.com"))

    monkeypatch.setattr(
        dependencies,
        "create_service_role_client",
        lambda: SimpleNamespace(auth=DummyAuth()),
    )
    monkeypatch.setattr(dependencies, "create_user_client", lambda access_token: user_client)

    current_user = dependencies.get_current_user(bearer(" token-value "))

    assert calls == ["token-value"]
    assert current_user.user_id == "auth-user-id"
    assert current_user.email == "analyst@example.com"
    assert current_user.access_token == "token-value"
    assert current_user.supabase is user_client


def test_get_current_user_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_current_user(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing bearer token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_get_current_user_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyAuth:
        def get_user(self, access_token: str) -> object:
            raise RuntimeError("token rejected")

    monkeypatch.setattr(
        dependencies,
        "create_service_role_client",
        lambda: SimpleNamespace(auth=DummyAuth()),
    )

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_current_user(bearer("bad-token"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


def test_get_current_user_rejects_missing_auth_user(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyAuth:
        def get_user(self, access_token: str) -> object:
            return SimpleNamespace(user=None)

    monkeypatch.setattr(
        dependencies,
        "create_service_role_client",
        lambda: SimpleNamespace(auth=DummyAuth()),
    )

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_current_user(bearer("bad-token"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
