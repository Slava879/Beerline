from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum
from sqlalchemy import String, DateTime, func, Enum as SQLEnum, Time, text, ForeignKey, Date
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, time, date
import uuid
from backend.app.db.base import Base

class TransportType(str, Enum):
    PEDESTRIAN = "pedestrian"
    BICYCLE = "bicycle"
    CAR = "car"

    @property
    def label(self) -> str:
        return _TRANSPORT_TYPE_LABELS[self]

_TRANSPORT_TYPE_LABELS: dict[TransportType, str] = {
    TransportType.PEDESTRIAN: "Пешеход",
    TransportType.BICYCLE: "Велосипед",
    TransportType.CAR: 'Автомобиль',
}


class Engineer(Base):
    __tablename__ = "engineers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)

    phone: Mapped[str | None] = mapped_column(String(32))
    birth_date: Mapped[date | None] = mapped_column(Date)

    shift_start: Mapped[time] = mapped_column(Time, index=True)
    shift_end: Mapped[time] = mapped_column(Time, index=True)

    skills: Mapped[list[str]] = mapped_column(JSONB)

    transport: Mapped[TransportType] = mapped_column(
        SQLEnum(
            TransportType,
            name='transport_type',
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
        default=TransportType.PEDESTRIAN,
        server_default=TransportType.PEDESTRIAN.value
    )

    available: Mapped[bool] = mapped_column(default=True, server_default=text('true'), index=True)
    status: Mapped[bool] = mapped_column(default=True, server_default=text('true'), index=True)
    off_shift_reason: Mapped[str | None] = mapped_column(String(255))
    equipment: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('districts.id', ondelete='SET NULL'), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    