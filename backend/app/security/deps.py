from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import SessionDep
from backend.app.security.services import TokenService
from backend.app.users.models import User, UserRole
from backend.app.users.repositories import UserRepository


# ─── Схема авторизации ────────────────────────────────────────

# auto_error=False — не падаем сами, вернём кастомный 401
bearer_scheme = HTTPBearer(auto_error=False)


# ─── Фабрики зависимостей ─────────────────────────────────────

def get_access_token_service() -> TokenService:
    from backend.app.core.security import get_access_token_service as _get
    return _get()


# ─── Проверка access-токена ───────────────────────────────────

async def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    tokens: Annotated[TokenService, Depends(get_access_token_service)],
) -> int:
    """
    Извлекает user_id из access-токена.
    Бросает 401, если токен отсутствует, невалиден или истёк.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    user_id = tokens.decode_token(credentials.credentials)
    if user_id is None:
        raise unauthorized

    return user_id


# ─── Загрузка User из БД ──────────────────────────────────────

async def get_current_user(
    user_id: Annotated[int, Depends(get_current_user_id)],
    session: SessionDep,
) -> User:
    """
    Загружает User из БД по user_id из токена.
    Бросает 401, если пользователь удалён или деактивирован.
    """
    repo = UserRepository()
    user = await repo.find_by_id(user_id, session)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


# ─── RBAC — проверка ролей ────────────────────────────────────

def require_roles(*allowed: UserRole):
    """
    Фабрика зависимостей для проверки ролей.

    Использование:
        @router.get("/admin", dependencies=[Depends(require_roles(UserRole.ADMIN))])
        async def admin_panel(): ...

    Или если нужен сам user:
        async def admin_panel(user: User = Depends(require_roles(UserRole.ADMIN))):
            ...
    """
    async def checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


# ─── Алиасы для эндпоинтов ────────────────────────────────────

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
CurrentUser = Annotated[User, Depends(get_current_user)]