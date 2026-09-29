# backend/app/dispatcher/schemas.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
#  Инженеры
# ============================================================

class EngineerOut(BaseModel):
    id:       str
    name:     str
    mode:     str = ""
    shift:    str = ""
    requests: int = 0
    online:   bool = False


class EngineerOrderOut(BaseModel):
    id:           str
    short_id:     str | None = None
    address:      str = ""
    status:       str = ""
    status_label: str = ""
    eta:          str | None = None
    window:       str | None = None


class EngineerEquipmentOut(BaseModel):
    id:     str
    kind:   str
    name:   str
    count:  int = 0
    state:  str = ""
    serial: str = ""


class EngineerDetailsOut(BaseModel):
    id:                str
    name:              str
    role_title:        str = ""
    transport_label:   str = ""
    on_shift:          bool = False
    shift_label:       str = ""
    shift_start:       str = ""
    shift_end:         str = ""
    off_shift_reason:  str | None = None
    phone:             str | None = None
    skills:            list[str] = []
    location:          dict | None = None
    equipment:         list[EngineerEquipmentOut] = []
    today_orders:      list[EngineerOrderOut] = []


class EngineerIn(BaseModel):
    fio:         str
    district_id: str
    transport:   str = "Пеший"
    phone:       str | None = None
    birth_date:  str | None = None
    shift_start: str | None = None
    shift_end:   str | None = None
    skills:      list[str] = []


class EngineerPatchIn(BaseModel):
    fio:         str | None = None
    phone:       str | None = None
    transport:   str | None = None
    shift_start: str | None = None
    shift_end:   str | None = None
    skills:      list[str] | None = None


class EndShiftIn(BaseModel):
    reason: str | None = None


# ============================================================
#  Заявки
# ============================================================

class StageTimes(BaseModel):
    taken:       str | None = None
    in_progress: str | None = None
    done:        str | None = None


class PlannedTimes(BaseModel):
    taken:       str | None = None
    in_progress: str | None = None
    done:        str | None = None


class Suggested(BaseModel):
    engineer_id:   str | None = None
    engineer_name: str | None = None
    distance_km:   float | None = None
    eta_min:       int | None = None


class PlannedRequestOut(BaseModel):
    id:                 str
    external_id:        int | None = None
    description:        str = ""
    status:             str = ""
    engineer_id:        str | None = None
    stage_times:        StageTimes | None = None
    planned_times:      PlannedTimes | None = None
    request_type:       str | None = None
    has_coords:         bool = False
    lat:                float | None = None
    lon:                float | None = None
    seq:                int | None = None
    assignment_reason:  str | None = None   # «Почему назначена этому мастеру»


class UnallocatedRequestOut(BaseModel):
    id:                str
    external_id:       int | None = None
    date:              str = ""
    window:            str = ""
    address:           str = ""
    service:           str = ""
    suggested:         Suggested | None = None
    request_type:      str | None = None
    has_coords:        bool = False
    unassigned_reason: str | None = None
    geocoded:          bool = False
    lat:               float | None = None
    lon:               float | None = None
    cancelled_at:      str | None = None
    auto_assigned:     bool = False         # заявка автоматически назначена после urgent
    engineer_name:     str | None = None    # кто назначил


class StatusIn(BaseModel):
    status: str


class CoordsIn(BaseModel):
    lat: float
    lon: float


class UrgentRequestIn(BaseModel):
    district_id:  str
    priority:     str = "urgent"
    request_type: str = "global"
    address:      str
    service:      str = ""
    client_name:  str | None = None
    client_phone: str | None = None
    city:         str | None = None
    street:       str | None = None
    house:        str | None = None
    building:     str | None = None
    entrance:     str | None = None
    floor:        str | None = None
    apartment:    str | None = None
    window_start: str | None = None
    window_end:   str | None = None


# ============================================================
#  Dashboard
# ============================================================

class DashboardOut(BaseModel):
    engineers:            dict[str, EngineerOut]
    planned_requests:     dict[str, PlannedRequestOut]
    unallocated_requests: dict[str, UnallocatedRequestOut]
    cancelled_requests:   dict[str, UnallocatedRequestOut] = Field(default_factory=dict)


# ============================================================
#  Оборудование
# ============================================================

class EquipmentOut(BaseModel):
    id:         str
    kind:       str
    name:       str
    quantity:   int = 0
    updated_at: str | None = None


class EquipmentListOut(BaseModel):
    equipment: list[EquipmentOut] = []


class EquipmentCreateIn(BaseModel):
    kind:     str
    name:     str
    quantity: int = 0


class EquipmentPatchIn(BaseModel):
    kind:     str | None = None
    name:     str | None = None
    quantity: int | None = None
    delta:    int | None = None


class IssueEquipmentIn(BaseModel):
    equipment_id: str
    quantity:     int = 1


class ReturnEquipmentIn(BaseModel):
    quantity: int = 1


class ClearEngineerEquipmentOut(BaseModel):
    ok:      bool = True
    cleared: int = 0


# ============================================================
#  Распределение / карты / сброс
# ============================================================

class DistributeOut(BaseModel):
    ok:           bool = True
    assigned:     int = 0
    total:        int = 0
    unassigned:   list[dict] = []
    map_url:      str | None = None
    per_engineer: dict[str, str] = {}
    timestamp:    str | None = None
    error:        str | None = None


class MapLinkOut(BaseModel):
    map_url: str | None = None


class ResetRequestsOut(BaseModel):
    ok:    bool = True
    reset: int = 0