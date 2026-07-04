"""FastAPI application entrypoint for Document Copilot."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import CurrentUserResponse, read_current_user
from app.auth import CurrentUser, get_current_user
from app.config import settings

app = FastAPI(title="Document Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/me", response_model=CurrentUserResponse, tags=["auth"])
async def read_auth_me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    return await read_current_user(current_user)
