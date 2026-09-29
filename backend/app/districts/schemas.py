# backend/app/districts/schemas.py
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DistrictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    requests_count: int = 0
    city: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None
    building: Optional[str] = None


class DistrictsOut(BaseModel):
    districts: list[DistrictOut]


class DistrictPatchIn(BaseModel):
    city: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None
    building: Optional[str] = None


class UploadCsvOut(BaseModel):
    ok: bool
    imported: int
    by_district: dict[str, int] = {}


class DeleteDistrictDataIn(BaseModel):
    period: list[str] = Field(min_length=1)


class DeleteDistrictDataOut(BaseModel):
    ok: bool
    deleted: int