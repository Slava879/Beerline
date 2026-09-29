from enum import Enum
from datetime import datetime

from sqlalchemy import String, DateTime, func, text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class UserRole(str, Enum):
    CLIENT = 'client'
    DISPATCHER = 'dispatcher'
    ENGINEER = 'engineer'

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name='user_role',
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
        default=UserRole.DISPATCHER,
        server_default=UserRole.DISPATCHER.value
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())