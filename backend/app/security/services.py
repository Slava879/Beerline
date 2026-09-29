from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import (
    PasswordService,
    RefreshTokenService,
    TokenService,
)
from backend.app.security.models import RefreshToken
from backend.app.security.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserRead,
)
from backend.app.users.models import User, UserRole
from backend.app.users.repositories import UserRepository


class SecurityService:
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordService,
        access_tokens: TokenService,
        refresh_tokens: RefreshTokenService,
    ):
        self.__users = user_repository
        self.__hasher = password_hasher
        self.__access = access_tokens
        self.__refresh = refresh_tokens

    # ─── Логин ────────────────────────────────────────────────

    async def login(
        self, body: LoginRequest, session: AsyncSession
    ) -> LoginResponse:
        user = await self.__users.find_by_login(body.login, session)

        if user is None:
            # Явно конструируем RegisterRequest — у LoginRequest нет поля role
            return await self.register(
                RegisterRequest(
                    login=body.login,
                    password=body.password,
                ),
                session,
            )

        if not self.__hasher.compare_passwords(
            body.password, user.password_hash
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)

        pair = await self.__issue_pair(user.id, session)

        return LoginResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            user=UserRead.model_validate(user),
        )

    # ─── Регистрация ──────────────────────────────────────────

    async def register(
        self, body: RegisterRequest, session: AsyncSession
    ) -> LoginResponse:
        if await self.__users.exists_by_login(body.login, session):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Login already taken",
            )

        role = self.__resolve_role(body.role)

        user = User(
            login=body.login,
            password_hash=self.__hasher.get_password_hash(body.password),
            role=role,
        )
        session.add(user)
        await session.flush()

        pair = await self.__issue_pair(user.id, session)

        return LoginResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            user=UserRead.model_validate(user),
        )

    # ─── Refresh (без user) ──────────────────────────────────

    async def refresh(
        self, body: RefreshRequest, session: AsyncSession
    ) -> TokenPair:
        token_hash = self.__refresh.hash(body.refresh_token)

        rt = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash
            )
        )

        if rt is None or rt.revoked:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)
        if rt.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)

        user = await self.__users.find_by_id(rt.user_id, session)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)

        rt.revoked = True
        await session.flush()

        return await self.__issue_pair(user.id, session)

    # ─── Logout ───────────────────────────────────────────────

    async def logout(self, user_id: int, session: AsyncSession) -> None:
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await session.commit()

    # ─── Приватные хелперы ────────────────────────────────────

    @staticmethod
    def __resolve_role(role: UserRole | None) -> UserRole:
        if role is None:
            return UserRole.DISPATCHER
        if role == UserRole.ADMIN:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Cannot self-assign admin role",
            )
        return role

    async def __issue_pair(
        self, user_id: int, session: AsyncSession
    ) -> TokenPair:
        access = self.__access.create_token(user_id)
        raw_refresh, token_hash, expires_at = self.__refresh.generate()

        session.add(
            RefreshToken(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        await session.commit()

        return TokenPair(
            access_token=access,
            refresh_token=raw_refresh,
        )