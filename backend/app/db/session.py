# backend/app/db/session.py
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.db.base import Base


class DatabaseManager:
    def __init__(self, db_url: str, create_schema: bool = False):
        self.__db_url = db_url
        self.__create_schema = create_schema
        self.__engine = None
        self.__session_maker = None

    async def __aenter__(self):
        self.__engine = create_async_engine(
            self.__db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.__session_maker = async_sessionmaker(
            self.__engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        if self.__create_schema:
            from backend.app import models  # noqa: F401 — регистрирует модели

            async with self.__engine.begin() as connect:
                await connect.run_sync(Base.metadata.create_all)

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.__engine is not None:
            await self.__engine.dispose()
            self.__engine = None
            self.__session_maker = None

    @property
    def session_maker(self) -> async_sessionmaker:
        if self.__session_maker is None:
            raise RuntimeError("DatabaseManager is not initialized")
        return self.__session_maker

    @asynccontextmanager
    async def get_session(self):
        """Для использования вне FastAPI-зависимостей (фоновые задачи, скрипты)."""
        session = self.session_maker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await _safe_close(session)


async def _safe_close(session: AsyncSession) -> None:
    """Закрывает сессию, глотает ошибки при отмене запроса."""
    try:
        await session.close()
    except Exception:
        # IllegalStateChangeError / InterfaceError при отмене — не падаем
        pass


async def get_session(request: Request):
    """
    FastAPI-зависимость. Отдаёт сессию на время запроса,
    закрывает её в finally с защитой от гонок при отмене.
    """
    db_manager: DatabaseManager = request.app.state.db_manager
    session = db_manager.session_maker()

    try:
        yield session
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
        raise
    finally:
        await _safe_close(session)


SessionDep = Annotated[AsyncSession, Depends(get_session)]