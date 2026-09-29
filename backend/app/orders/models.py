from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum
from sqlalchemy import (
    String, DateTime, ForeignKey, func,
    Enum as SQLEnum, Numeric, Time, Date,
)
from sqlalchemy.dialects.postgresql import JSONB
from decimal import Decimal
from datetime import datetime, time, date
import uuid
from backend.app.db.base import Base


class OrderSource(str, Enum):
    CLIENT = 'client'
    DISPATCHER = 'dispatcher'


class RequestType(str, Enum):
    CONNECTION = "connection"
    REORDER = "reorder"
    LOCAL_REQUEST = "local_request"
    GLOBAL_ISSUE = "global_issue"

    @property
    def label(self) -> str:
        return _REQUEST_TYPE_LABELS[self]

    @property
    def priority(self) -> int:
        """Единый приоритет для алгоритма и сортировки в БД."""
        return _REQUEST_TYPE_PRIORITY[self]

    @property
    def skill(self) -> str:
        """Навык, который должен быть у мастера для этой заявки."""
        return _REQUEST_TYPE_SKILL[self]


_REQUEST_TYPE_LABELS: dict[RequestType, str] = {
    RequestType.CONNECTION:    "Подключение",
    RequestType.REORDER:       "Дозаказ",
    RequestType.LOCAL_REQUEST: "Локальная заявка",
    RequestType.GLOBAL_ISSUE:  "Глобальная проблема",
}

# Единый источник правды по приоритету — совпадает с algorithm.PRIORITY
_REQUEST_TYPE_PRIORITY: dict[RequestType, int] = {
    RequestType.GLOBAL_ISSUE:  0,
    RequestType.CONNECTION:    1,
    RequestType.REORDER:       2,
    RequestType.LOCAL_REQUEST: 2,
}

# Единый источник правды по навыку — совпадает с algorithm.TASK_SKILL.values()
_REQUEST_TYPE_SKILL: dict[RequestType, str] = {
    RequestType.CONNECTION:    "подключение",
    RequestType.GLOBAL_ISSUE:  "глобальные проблемы",
    RequestType.REORDER:       "дозаказ",
    RequestType.LOCAL_REQUEST: "локальные работы",
}


class RequestStatus(str, Enum):
    NEW = "new"
    TAKEN = 'taken'
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return _REQUEST_STATUS_LABELS[self]


_REQUEST_STATUS_LABELS = {
    RequestStatus.NEW: "Новая",
    RequestStatus.TAKEN: "Мастер выехал",
    RequestStatus.IN_PROGRESS: "В работе",
    RequestStatus.DONE: "Выполнена",
    RequestStatus.CANCELLED: "Отменена",
}


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[int] = mapped_column(index=True)

    bk_type: Mapped[RequestType] = mapped_column(
        SQLEnum(
            RequestType,
            name='request_type',
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
        default=RequestType.LOCAL_REQUEST,
        server_default=RequestType.LOCAL_REQUEST.value
    )
    bk_status: Mapped[str] = mapped_column(String(64), index=True)
    hd_type: Mapped[str | None] = mapped_column(String(64))

    district: Mapped[str] = mapped_column(String(64), index=True)
    gigabit_connection: Mapped[str | None] = mapped_column(String(64))

    address: Mapped[str] = mapped_column(String(255))
    lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    lon: Mapped[Decimal] = mapped_column(Numeric(9, 6))

    duration_min: Mapped[int] = mapped_column()
    skill: Mapped[str] = mapped_column(String(64))

    window_start: Mapped[time] = mapped_column(Time)
    window_end: Mapped[time] = mapped_column(Time)

    visit_date: Mapped[date | None] = mapped_column(Date, index=True)

    priority: Mapped[int] = mapped_column(index=True)
    transport_required: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[RequestStatus] = mapped_column(
        SQLEnum(
            RequestStatus,
            name='request_status',
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
        default=RequestStatus.NEW,
        server_default=RequestStatus.NEW.value
    )

    assigned_engineer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('engineers.id', ondelete='SET NULL'), index=True
    )

    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('districts.id', ondelete='SET NULL'), index=True
    )

    departed_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    finished_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    transferred_from: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('engineers.id', ondelete='SET NULL'), index=True
    )

    source: Mapped[OrderSource] = mapped_column(
        SQLEnum(
            OrderSource,
            name='order_source',
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
        default=OrderSource.DISPATCHER,
        server_default=OrderSource.DISPATCHER.value
    )
    extra: Mapped[dict | None] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )