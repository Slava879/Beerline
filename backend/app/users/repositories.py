from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.users.models import User


class UserRepository:

    async def find_by_id(self, user_id: int, session: AsyncSession) -> User | None:
        return await session.get(User, user_id)

    async def find_by_login(self, login: str, session: AsyncSession) -> User | None:
        q = select(User).where(User.login == login)
        return (await session.execute(q)).scalar_one_or_none()

    async def exists_by_login(self, login: str, session: AsyncSession) -> bool:
        q = select(exists().where(User.login == login))
        return (await session.execute(q)).scalar()