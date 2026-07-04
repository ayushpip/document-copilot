"""Authentication API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class CurrentUserResponse(BaseModel):
    user_id: str
    email: str | None


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(user_id=current_user.user_id, email=current_user.email)
