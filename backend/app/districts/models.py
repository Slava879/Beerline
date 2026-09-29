# backend/app/districts/models.py
from __future__ import annotations
import uuid
from decimal import Decimal

from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class District(Base):
    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Части адреса офиса
    city:     Mapped[str | None] = mapped_column(String(128))
    street:   Mapped[str | None] = mapped_column(String(255))
    house:    Mapped[str | None] = mapped_column(String(64))
    building: Mapped[str | None] = mapped_column(String(64))

    # Координаты офиса (заполняются при первом геокодировании)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))