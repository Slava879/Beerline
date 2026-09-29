# backend/app/equipment/models.py
from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class Equipment(Base):
    """Склад оборудования."""
    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str]      = mapped_column(String(64), index=True)   # "router", "receiver"
    name: Mapped[str]      = mapped_column(String(255))              # "Router Beeline Wi-Fi 6 Pro"
    quantity: Mapped[int]  = mapped_column(Integer, default=0)       # на складе
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EngineerEquipment(Base):
    """Оборудование, выданное инженеру."""
    __tablename__ = "engineer_equipment"

    engineer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engineers.id", ondelete="CASCADE"), primary_key=True
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0)