import pytest

from app.database import supabase


class DummySettings:
    supabase_url = "https://project.supabase.co"
    supabase_anon_key = "anon-key"
    supabase_service_role_key = "service-role-key"


def test_create_service_role_client_uses_service_role_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_create_client(url: str, key: str, options: object | None = None) -> object:
        calls.append((url, key, options))
        return object()

    supabase.create_service_role_client.cache_clear()
    monkeypatch.setattr(supabase, "settings", DummySettings())
    monkeypatch.setattr(supabase, "create_client", fake_create_client)

    first_client = supabase.create_service_role_client()
    second_client = supabase.create_service_role_client()

    assert first_client is second_client
    assert calls == [("https://project.supabase.co", "service-role-key", None)]


def test_create_user_client_sets_bearer_token_options(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_create_client(url: str, key: str, options: object | None = None) -> object:
        calls.append((url, key, options))
        return object()

    monkeypatch.setattr(supabase, "settings", DummySettings())
    monkeypatch.setattr(supabase, "create_client", fake_create_client)

    supabase.create_user_client(" user-jwt ")

    url, key, options = calls[0]
    assert url == "https://project.supabase.co"
    assert key == "anon-key"
    assert options is not None
    assert options.headers == {"Authorization": "Bearer user-jwt"}
    assert options.auto_refresh_token is False
    assert options.persist_session is False


def test_create_user_client_rejects_blank_token() -> None:
    with pytest.raises(ValueError, match="access_token is required"):
        supabase.create_user_client(" ")
