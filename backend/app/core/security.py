import hashlib
import jwt
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

from backend.app.core.config import settings

from functools import lru_cache


class PasswordService:
    def __init__(self, schemes: list[str] | None = None):
        self.__context = CryptContext(schemes=schemes or ['argon2'])

    def get_password_hash(self, password: str) -> str:
        return self.__context.hash(password)

    def compare_passwords(self, raw_password: str, password_hash: str) -> bool:
        return self.__context.verify(raw_password, password_hash)


class TokenService:
    def __init__(self, SECRET_KEY: str, algorithm: str = 'HS256', lifetime: timedelta = timedelta(minutes=15)):
        self.__SECRET_KEY = SECRET_KEY
        self.__algorithm = algorithm
        self.__lifetime = lifetime

    def create_token(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            'sub': str(user_id),
            'type': 'access',
            'iat': now,
            'exp': now + self.__lifetime,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(
            payload,
            key=self.__SECRET_KEY,
            algorithm=self.__algorithm
        )

    def decode_token(self, token: str) -> int | None:
        try:
            payload = jwt.decode(
                token,
                key=self.__SECRET_KEY,
                algorithms=[self.__algorithm],
            )
        except jwt.ExpiredSignatureError as e:
            return None
        except jwt.InvalidTokenError as e:
            return None

        if payload.get("type") != "access":
            return None

        try:
            return int(payload["sub"])
        except (KeyError, ValueError) as e:
            return None


class RefreshTokenService:
    def __init__(self, lifetime: timedelta = timedelta(days=30)):
        self.__lifetime = lifetime

    def generate(self) -> tuple[str, str, datetime]:
        raw = secrets.token_urlsafe(64)
        token_hash = self.hash(raw)
        expires_at = datetime.now(timezone.utc) + self.__lifetime
        return raw, token_hash, expires_at

    @staticmethod
    def hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

@lru_cache
def get_password_hasher() -> PasswordService:
    return PasswordService(schemes=["argon2"])


@lru_cache
def get_access_token_service() -> TokenService:
    return TokenService(
        SECRET_KEY=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        lifetime=timedelta(minutes=settings.ACCESS_TOKEN_LIFETIME_MINUTES),
    )


@lru_cache
def get_refresh_token_service() -> RefreshTokenService:
    return RefreshTokenService(
        lifetime=timedelta(days=settings.REFRESH_TOKEN_LIFETIME_DAYS),
    )