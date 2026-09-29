# backend/app/routers/districts.py
import csv
import io
import os
import re
import uuid
from datetime import date, date as date_type, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select, func, delete as sa_delete

from backend.app.db.session import SessionDep
from backend.app.users.models import User
from backend.app.districts.models import District
from backend.app.orders.models import Order, RequestType, RequestStatus, OrderSource
from backend.app.security.deps import get_current_user
from backend.app.districts.schemas import (
    DistrictsOut, DistrictOut, DistrictPatchIn, UploadCsvOut,
    DeleteDistrictDataIn, DeleteDistrictDataOut,
)

router = APIRouter(prefix="/districts", tags=["districts"])


# ============================================================
#  Список районов / один район / обновление
# ============================================================
@router.get("", response_model=DistrictsOut)
async def list_districts(
    db: SessionDep,
    user: User = Depends(get_current_user),
):
    rows = (await db.execute(select(District))).scalars().all()

    out: list[DistrictOut] = []
    for d in rows:
        count = (await db.execute(
            select(func.count()).select_from(Order).where(Order.district_id == d.id)
        )).scalar_one()
        out.append(DistrictOut(
            id=d.id, name=d.name, requests_count=count,
            city=d.city, street=d.street, house=d.house, building=d.building,
        ))
    return DistrictsOut(districts=out)


@router.get("/{district_id}", response_model=DistrictOut)
async def get_district(
    district_id: uuid.UUID,
    db: SessionDep,
    user: User = Depends(get_current_user),
):
    d = await db.get(District, district_id)
    if not d:
        raise HTTPException(404, "Район не найден")
    return DistrictOut(
        id=d.id, name=d.name, requests_count=0,
        city=d.city, street=d.street, house=d.house, building=d.building,
    )


@router.patch("/{district_id}", response_model=DistrictOut)
async def patch_district(
    district_id: uuid.UUID,
    data: DistrictPatchIn,
    db: SessionDep,
    user: User = Depends(get_current_user),
):
    d = await db.get(District, district_id)
    if not d:
        raise HTTPException(404, "Район не найден")

    if data.city     is not None: d.city = data.city.strip() or None
    if data.street   is not None: d.street = data.street.strip() or None
    if data.house    is not None: d.house = data.house.strip() or None
    if data.building is not None: d.building = data.building.strip() or None

    await db.commit()
    await db.refresh(d)

    return DistrictOut(
        id=d.id, name=d.name, requests_count=0,
        city=d.city, street=d.street, house=d.house, building=d.building,
    )


# ============================================================
#  Парсинг CSV
# ============================================================

HEADER_SYNONYMS: dict[str, list[str]] = {
    "task_id":    ["заявка", "id", "номер заявки", "номер", "№", "task",
                   "task_id", "заявка №", "№ заявки", "номер заказа", "заказ"],
    "bk":         ["тип заявки bk", "тип bk", "bk", "тип заявки бк",
                   "заявка bk", "bk заявки"],
    "hd":         ["тип заявки hd", "тип hd", "hd", "заявка hd",
                   "hd заявки"],
    "start":      ["начало", "начало окна", "start", "время с",
                   "время начала", "окно с"],
    "end":        ["окончание", "конец", "окончание окна", "end",
                   "время по", "время окончания", "окно по"],
    "date":       ["дата", "date", "день", "дата визита",
                   "дата заявки", "дата работ", "плановая дата",
                   "день визита", "дата выполнения"],
    "district":   ["район", "district", "округ", "район города"],
    "address":    ["адрес", "address", "addr", "адрес объекта", "адрес работ"],
    "connection": ["подключение", "connection", "подкл"],
    "gigabit":    ["гигабитное подключение", "gigabit", "гигабит"],
    "office":     ["адрес офиса", "офис", "office", "адрес базы"],
}


def _normalize_header(h) -> str:
    if h is None:
        return ""
    s = str(h).strip().lower()
    s = re.sub(r"[«»\"'`.,;:!?\-_/\\]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


_HEADER_LOOKUP: dict[str, str] = {}
for _k, _syns in HEADER_SYNONYMS.items():
    for _syn in _syns:
        _HEADER_LOOKUP[_normalize_header(_syn)] = _k


def match_header(cell: str) -> str | None:
    return _HEADER_LOOKUP.get(_normalize_header(cell))


def clean_text(s) -> str:
    if s is None:
        return ""
    s = str(s).replace("\t", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    compact = re.sub(r"\s+", "", str(s))
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})(\d{1,2}:\d{2})", compact)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + " " + m.group(2), "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def _parse_date_any(s: str) -> date | None:
    if not s:
        return None
    s = s.strip()
    dt = parse_dt(s)
    if dt:
        return dt.date()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _detect_rows(text: str) -> list[list[str]]:
    best_rows, best_cols = None, 0
    for delim in (";", ",", "\t"):
        try:
            rows = list(csv.reader(text.splitlines(),
                                   delimiter=delim,
                                   skipinitialspace=True))
        except Exception:
            continue
        max_cols = max((len(r) for r in rows if r), default=0)
        if max_cols > best_cols:
            best_cols = max_cols
            best_rows = rows
    return best_rows or []


def _detect_header(rows: list[list[str]]) -> tuple[int | None, dict[str, int]]:
    for i, row in enumerate(rows):
        if not row:
            continue
        col_map: dict[str, int] = {}
        for j, cell in enumerate(row):
            key = match_header(cell)
            if key and key not in col_map:
                col_map[key] = j
        if len(col_map) >= 3:
            return i, col_map
    return None, {}


_BK_TO_TYPE: dict[str, RequestType] = {
    "подключение":          RequestType.CONNECTION,
    "дозаказ":              RequestType.REORDER,
    "локальная заявка":     RequestType.LOCAL_REQUEST,
    "глобальная проблема":  RequestType.GLOBAL_ISSUE,
}


def _map_bk_type(raw: str) -> RequestType:
    return _BK_TO_TYPE.get(clean_text(raw).lower(), RequestType.LOCAL_REQUEST)


# ============================================================
#  Участок по имени файла
# ============================================================

def _district_name_from_filename(filename: str) -> str:
    base = os.path.basename(filename or "")
    return os.path.splitext(base)[0].strip()


async def _get_or_create_district(db, name: str) -> District:
    name = name.strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Не удалось определить участок по имени файла",
        )
    district = (await db.execute(
        select(District).where(District.name == name)
    )).scalar_one_or_none()
    if district is None:
        district = District(id=uuid.uuid4(), name=name)
        db.add(district)
        await db.flush()
    return district


# ============================================================
#  Дедупликация
# ============================================================

async def _existing_external_ids(db, district_id) -> set[int]:
    rows = (await db.execute(
        select(Order.external_id).where(Order.district_id == district_id)
    )).scalars().all()
    return {int(x) for x in rows if x is not None}


# ============================================================
#  Загрузка CSV
# ============================================================
@router.post("/upload-csv", response_model=UploadCsvOut)
async def upload_csv(
    db: SessionDep,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Ожидается CSV-файл")

    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Пустой файл")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл должен быть в UTF-8")

    district = await _get_or_create_district(
        db, _district_name_from_filename(file.filename)
    )

    rows = _detect_rows(text)
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV пуст или не читается")

    header_idx, col_map = _detect_header(rows)
    if header_idx is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Не удалось найти строку-заголовок. Ожидаются колонки типа "
            "'Заявка', 'Тип заявки BK', 'Начало', 'Окончание', 'Адрес' и т.п.",
        )

    missing = [k for k in ("task_id", "address", "start") if k not in col_map]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"CSV должен содержать колонки: {', '.join(missing)}",
        )

    def get(row: list[str], key: str, default: str = "") -> str:
        j = col_map.get(key)
        if j is None or j >= len(row):
            return default
        return clean_text(row[j])

    existing_ids = await _existing_external_ids(db, district.id)
    seen_in_file: set[int] = set()
    print(f"[CSV] район «{district.name}»: уже в БД {len(existing_ids)} заявок", flush=True)

    imported = 0
    duplicates = 0
    skipped = 0
    by_district: dict[str, int] = {}
    today = date_type.today()

    for i, row in enumerate(rows):
        if i <= header_idx or not row:
            continue

        task_id = get(row, "task_id")
        if not re.match(r"^\d{4,6}$", task_id):
            skipped += 1
            continue
        external_id = int(task_id)

        if external_id in existing_ids:
            duplicates += 1
            continue
        if external_id in seen_in_file:
            duplicates += 1
            continue
        seen_in_file.add(external_id)

        start = parse_dt(get(row, "start"))
        end = parse_dt(get(row, "end"))
        if not (start and end):
            skipped += 1
            continue

        bk_type = _map_bk_type(get(row, "bk"))

        order = Order(external_id=external_id, district_id=district.id)
        db.add(order)

        order.district    = get(row, "district") or district.name
        order.district_id = district.id

        order.bk_type   = bk_type
        order.bk_status = get(row, "bk") or "new"
        order.hd_type   = get(row, "hd") or None
        order.address   = get(row, "address")
        order.gigabit_connection = get(row, "gigabit") or None

        order.skill    = bk_type.skill
        order.priority = bk_type.priority

        order.window_start = start.time()
        order.window_end   = end.time()

        date_cell = get(row, "date")
        visit_date = _parse_date_any(date_cell) if date_cell else None
        if visit_date is None:
            visit_date = start.date()
        order.visit_date = visit_date or today

        delta = int((end - start).total_seconds() // 60)
        order.duration_min = max(delta, 0)

        order.status = RequestStatus.NEW
        order.source = OrderSource.DISPATCHER

        if order.lat is None:
            order.lat = Decimal("0")
        if order.lon is None:
            order.lon = Decimal("0")

        imported += 1
        by_district[district.name] = by_district.get(district.name, 0) + 1

    await db.commit()

    print(f"[CSV] итог: импортировано={imported}, "
          f"дубликатов пропущено={duplicates}, "
          f"невалидных строк={skipped}", flush=True)

    return UploadCsvOut(
        ok=True,
        imported=imported,
        by_district=by_district,
        duplicates=duplicates,
        skipped=skipped,
    )


# ============================================================
#  Удаление по району
# ============================================================
@router.delete("/{district_id}/data", response_model=DeleteDistrictDataOut)
async def delete_data(
    district_id: uuid.UUID,
    data: DeleteDistrictDataIn,
    db: SessionDep,
    user: User = Depends(get_current_user),
):
    if not data.period:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не выбран период удаления")

    today = date.today()
    only_today    = "today"    in data.period and "previous" not in data.period
    only_previous = "previous" in data.period and "today"    not in data.period

    stmt = sa_delete(Order).where(Order.district_id == district_id)

    if only_today:
        stmt = stmt.where(Order.visit_date == today)
    elif only_previous:
        stmt = stmt.where(Order.visit_date != today)

    result = await db.execute(stmt)
    await db.commit()
    return DeleteDistrictDataOut(ok=True, deleted=result.rowcount or 0)