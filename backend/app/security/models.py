from sqlalchemy import String, DateTime, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column

from datetime import datetime
import uuid

from backend.app.db.base import Base


class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked: Mapped[bool] = mapped_column(default=False, server_default=text('false'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())