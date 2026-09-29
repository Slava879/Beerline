
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import (
    TokenService,
    PasswordService,
    RefreshTokenService,
    get_access_token_service,
    get_password_hasher,
    get_refresh_token_service,
)
from backend.app.db.session import SessionDep
from backend.app.security.deps import get_current_user_id
from backend.app.security.schemas import LoginRequest, RefreshRequest, TokenPair, RegisterRequest, LoginResponse
from backend.app.security.services import SecurityService
from backend.app.users.repositories import UserRepository


router = APIRouter(prefix="/auth", tags=["auth"])


def get_security_service(
    hasher: PasswordService = Depends(get_password_hasher),
    access: TokenService = Depends(get_access_token_service),
    refresh: RefreshTokenService = Depends(get_refresh_token_service),
) -> SecurityService:
    return SecurityService(
        user_repository=UserRepository(),
        password_hasher=hasher,
        access_tokens=access,
        refresh_tokens=refresh,
    )


@router.post("/register", response_model=LoginResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: SessionDep,
    service: SecurityService = Depends(get_security_service),
):
    return await service.register(body, session)

@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: SessionDep,
    service: SecurityService = Depends(get_security_service),
):
    return await service.login(body, session)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    session: SessionDep,
    service: SecurityService = Depends(get_security_service),
):
    return await service.refresh(body, session)


@router.post("/logout", status_code=204)
async def logout(
    session: SessionDep,
    user_id: int = Depends(get_current_user_id),
    service: SecurityService = Depends(get_security_service),
):
    await service.logout(user_id, session)