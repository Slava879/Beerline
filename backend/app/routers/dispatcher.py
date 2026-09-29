# backend/app/routers/dispatcher.py
from datetime import datetime, time as dtime, date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update as sa_update

from backend.app.db.session import SessionDep
from backend.app.users.models import User
from backend.app.engineers.models import Engineer, TransportType
from backend.app.orders.models import Order, RequestStatus, RequestType
from backend.app.equipment.models import Equipment, EngineerEquipment
from backend.app.districts.models import District
from backend.app.security.deps import get_current_user
from backend.app.dispatcher.schemas import (
    DashboardOut, EngineerOut, PlannedRequestOut, UnallocatedRequestOut,
    Suggested, StageTimes, PlannedTimes, StatusIn, UrgentRequestIn, EngineerIn,
    EngineerDetailsOut, EngineerPatchIn, EngineerOrderOut,
    EndShiftIn, EquipmentOut, EquipmentListOut, IssueEquipmentIn,
    EngineerEquipmentOut, EquipmentCreateIn, EquipmentPatchIn,
    ReturnEquipmentIn, ClearEngineerEquipmentOut,
    DistributeOut, MapLinkOut, ResetRequestsOut, CoordsIn,
)
from backend.app.services.routing import (
    distribute_orders, latest_engineer_map, latest_common_map,
    rebuild_maps, find_suitable_engineers,
)
from backend.app.services.geocoding import geocode as geo_geocode
from backend.app.services.status_auto import auto_update_statuses

router = APIRouter(prefix="/dispatcher", tags=["dispatcher"])


_TRANSPORT_LABEL = {
    TransportType.CAR:        "Авто",
    TransportType.BICYCLE:    "Вело",
    TransportType.PEDESTRIAN: "Пеший",
}

_TRANSPORT_TO_ENUM = {
    "Автомобиль": TransportType.CAR,
    "Велосипед":  TransportType.BICYCLE,
    "Пеший":      TransportType.PEDESTRIAN,
}

_STATUS_LABEL = {
    RequestStatus.NEW:         "Ожидает",
    RequestStatus.TAKEN:       "В пути",
    RequestStatus.IN_PROGRESS: "В процессе",
    RequestStatus.DONE:        "Выполнена",
    RequestStatus.CANCELLED:   "Отменена",
}

_ROLE_TITLE = "Инженер-монтажник"

MIN_ACCEPT_SCORE = 6.0


def _has_coords(o: Order) -> bool:
    try:
        lat = float(o.lat or 0)
        lon = float(o.lon or 0)
    except Exception:
        return False
    return lat != 0 and lon != 0


def _fmt_shift(e: Engineer) -> str:
    if e.shift_start and e.shift_end:
        return f"{e.shift_start.strftime('%H:%M')}–{e.shift_end.strftime('%H:%M')}"
    return "—"


def _shift_label(e: Engineer) -> str:
    if e.shift_start and e.shift_end:
        return f"На смене ({e.shift_start.strftime('%H:%M')} – {e.shift_end.strftime('%H:%M')})"
    return "Не на смене"


def _eng(e: Engineer, request_count: int = 0) -> EngineerOut:
    return EngineerOut(
        id=str(e.id),
        name=e.name,
        mode=_TRANSPORT_LABEL.get(e.transport, "Пеший"),
        shift=_fmt_shift(e),
        requests=request_count,
        online=bool(e.available and e.status),
    )


def _fmt_window(o: Order) -> str:
    if o.window_start and o.window_end:
        return f"{o.window_start.strftime('%H:%M')} — {o.window_end.strftime('%H:%M')}"
    return ""


def _fmt_visit_date(o: Order) -> str:
    d = o.visit_date
    if d is None:
        d = o.created_at.date() if o.created_at else None
    if d is None:
        return ""
    return d.strftime("%d.%m.%Y")


def _type_label(o: Order) -> str:
    if o.bk_type is None:
        return ""
    try:
        return o.bk_type.label
    except Exception:
        val = o.bk_type.value if hasattr(o.bk_type, "value") else str(o.bk_type)
        return val


def _planned(o: Order) -> PlannedRequestOut:
    stage: dict[str, str] = {}
    if o.departed_at:  stage["taken"]       = o.departed_at.strftime("%H:%M")
    if o.started_at:   stage["in_progress"] = o.started_at.strftime("%H:%M")
    if o.finished_at:  stage["done"]        = o.finished_at.strftime("%H:%M")

    planned_raw: dict = {}
    if isinstance(o.extra, dict):
        p = o.extra.get("planned")
        if isinstance(p, dict):
            planned_raw = p

    for key in ("taken", "in_progress", "done"):
        if key not in stage and planned_raw.get(key):
            stage[key] = planned_raw[key]

    times = StageTimes(**stage) if stage else None

    planned = None
    if isinstance(o.extra, dict):
        planned_raw2 = o.extra.get("planned")
        if isinstance(planned_raw2, dict):
            planned = PlannedTimes(**planned_raw2)

    date_str = _fmt_visit_date(o)
    win_str  = _fmt_window(o)
    desc = f"{date_str} ({win_str}) | {o.address}".strip(" |")

    # ── Причина, почему назначена именно этому мастеру ──
    rparts: list[str] = []
    if o.skill:
        rparts.append(f"навык «{o.skill}»")
    if o.priority == 0:
        rparts.append("аварийный приоритет")
    if planned_raw.get("taken") and planned_raw.get("done"):
        rparts.append(
            f"план {planned_raw['taken']}–{planned_raw['done']}"
            + (f" в окне {win_str}" if win_str else "")
        )
    if o.lat and o.lon:
        rparts.append("адрес геокодирован")
    assignment_reason = ". ".join(rparts) if rparts else None

    return PlannedRequestOut(
        id=str(o.id),
        external_id=o.external_id,
        description=desc,
        status=o.status.value if hasattr(o.status, "value") else str(o.status),
        engineer_id=str(o.assigned_engineer_id) if o.assigned_engineer_id else None,
        stage_times=times,
        planned_times=planned,
        request_type=_type_label(o),
        has_coords=_has_coords(o),
        lat=float(o.lat) if o.lat else None,
        lon=float(o.lon) if o.lon else None,
        assignment_reason=assignment_reason,
    )


def _unalloc(o: Order) -> UnallocatedRequestOut:
    has = _has_coords(o)
    reason = None
    if not has:
        reason = "Не удалось геокодировать адрес — введите координаты вручную"

    return UnallocatedRequestOut(
        id=str(o.id),
        external_id=o.external_id,
        date=_fmt_visit_date(o),
        window=_fmt_window(o),
        address=o.address,
        service=o.skill or "",
        suggested=None,
        request_type=_type_label(o),
        has_coords=has,
        unassigned_reason=reason,
        lat=float(o.lat) if o.lat else None,
        lon=float(o.lon) if o.lon else None,
        cancelled_at=o.cancelled_at.strftime("%H:%M") if o.cancelled_at else None,
    )


def _eq_out(e: Equipment) -> EquipmentOut:
    return EquipmentOut(
        id=str(e.id),
        kind=e.kind,
        name=e.name,
        quantity=e.quantity,
        updated_at=e.updated_at.isoformat() if e.updated_at else None,
    )


async def _get_order(db, rid: str, user: User) -> Order:
    order = await db.get(Order, rid)
    if not order:
        raise HTTPException(404, "Заявка не найдена")
    return order


def _parse_hhmm(s):
    if not s:
        return None
    try:
        h, m = s.split(":")
        return dtime(int(h), int(m))
    except Exception:
        return None


def _parse_iso_date(s):
    if not s:
        return None
    try:
        return date_type.fromisoformat(s)
    except ValueError:
        return None


def _address_for_geocode(data) -> str:
    parts = []
    if data.city:
        parts.append(str(data.city).strip())
    if data.street:
        parts.append(str(data.street).strip())
    if data.house:
        hb = str(data.house).strip()
        if getattr(data, "building", None):
            hb += f"к{str(data.building).strip()}"
        parts.append(hb)
    return ", ".join(p for p in parts if p)


# ============================================================
#  Dashboard
# ============================================================

@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(db: SessionDep,
                    district_id: str = Query(...),
                    visit_date: str = Query(None),
                    user: User = Depends(get_current_user)):
    if visit_date:
        try:
            day = date_type.fromisoformat(visit_date)
        except ValueError:
            day = date_type.today()
    else:
        day = date_type.today()

    try:
        n = await auto_update_statuses(db, district_id=district_id, day=day)
        if n:
            print(f"[AUTO-STATUS] обновлено заявок: {n}", flush=True)
    except Exception as e:
        print(f"[AUTO-STATUS] ошибка: {e}", flush=True)

    engineers = (await db.execute(
        select(Engineer).where(Engineer.district_id == district_id)
    )).scalars().all()

    planned = (await db.execute(
        select(Order).where(
            Order.district_id == district_id,
            Order.assigned_engineer_id.isnot(None),
            Order.status != RequestStatus.CANCELLED,
            Order.visit_date == day,
        )
    )).scalars().all()

    unalloc = (await db.execute(
        select(Order).where(
            Order.district_id == district_id,
            Order.assigned_engineer_id.is_(None),
            Order.status != RequestStatus.CANCELLED,
            Order.visit_date == day,
        )
    )).scalars().all()

    cancelled_rows = (await db.execute(
        select(Order).where(
            Order.district_id == district_id,
            Order.status == RequestStatus.CANCELLED,
            Order.visit_date == day,
        )
    )).scalars().all()
    cancelled_rows = sorted(
        cancelled_rows,
        key=lambda o: (o.cancelled_at is None, o.cancelled_at or datetime.min),
        reverse=True,
    )

    print(f"[DASH] district={district_id} day={day} "
          f"planned={len(planned)} unalloc={len(unalloc)} "
          f"cancelled={len(cancelled_rows)}", flush=True)

    counts: dict[str, int] = {}
    for o in planned:
        if o.assigned_engineer_id:
            k = str(o.assigned_engineer_id)
            counts[k] = counts.get(k, 0) + 1

    return DashboardOut(
        engineers={str(e.id): _eng(e, counts.get(str(e.id), 0)) for e in engineers},
        planned_requests={str(o.id): _planned(o) for o in planned},
        unallocated_requests={str(o.id): _unalloc(o) for o in unalloc},
        cancelled_requests={str(o.id): _unalloc(o) for o in cancelled_rows},
    )


@router.get("/replanning-events")
async def replanning_events(db: SessionDep, district_id: str = Query(...),
                            user: User = Depends(get_current_user)):
    return []


# ============================================================
#  Заявки
# ============================================================

@router.post("/requests/{rid}/assign/{eid}", response_model=PlannedRequestOut)
async def assign(rid: str, eid: str, db: SessionDep,
                 user: User = Depends(get_current_user)):
    order = await _get_order(db, rid, user)
    eng = await db.get(Engineer, eid)
    if not eng or eng.district_id != order.district_id:
        raise HTTPException(404, "Инженер не найден в этом районе")
    if not eng.available:
        raise HTTPException(409, "Инженер offline")

    order.assigned_engineer_id = eng.id
    order.status = RequestStatus.NEW
    await db.commit()
    await db.refresh(order)
    return _planned(order)


@router.post("/requests/{rid}/return")
async def return_to_pool(rid: str, db: SessionDep,
                         user: User = Depends(get_current_user)):
    order = await _get_order(db, rid, user)
    if order.status in (RequestStatus.IN_PROGRESS, RequestStatus.DONE):
        raise HTTPException(409, "Нельзя вернуть: работа уже начата")
    order.assigned_engineer_id = None
    order.status = RequestStatus.NEW
    await db.commit()
    return {"ok": True}


@router.post("/requests/{rid}/auto-assign", response_model=PlannedRequestOut)
async def auto_assign(rid: str, db: SessionDep,
                      user: User = Depends(get_current_user)):
    order = await _get_order(db, rid, user)
    eng = (await db.execute(
        select(Engineer).where(
            Engineer.district_id == order.district_id,
            Engineer.available.is_(True),
        ).limit(1)
    )).scalar_one_or_none()
    if not eng:
        raise HTTPException(409, "Нет доступных мастеров")
    order.assigned_engineer_id = eng.id
    order.status = RequestStatus.NEW
    await db.commit()
    await db.refresh(order)
    return _planned(order)


@router.post("/requests/{rid}/confirm", response_model=PlannedRequestOut)
async def confirm(rid: str, db: SessionDep,
                  user: User = Depends(get_current_user)):
    order = await _get_order(db, rid, user)
    order.status = RequestStatus.NEW
    await db.commit()
    await db.refresh(order)
    return _planned(order)


@router.post("/requests/{rid}/status", response_model=PlannedRequestOut)
async def set_status(rid: str, data: StatusIn, db: SessionDep,
                     user: User = Depends(get_current_user)):
    order = await _get_order(db, rid, user)

    raw = data.status
    if isinstance(raw, RequestStatus):
        new_status = raw
    else:
        try:
            new_status = RequestStatus(str(raw).strip().lower())
        except ValueError:
            raise HTTPException(400, f"Неизвестный статус: {data.status}")

    order.status = new_status
    now = datetime.now()

    if new_status == RequestStatus.TAKEN:
        order.departed_at = now
    elif new_status == RequestStatus.IN_PROGRESS:
        order.started_at = now
    elif new_status == RequestStatus.DONE:
        order.finished_at = now
    elif new_status == RequestStatus.CANCELLED:
        order.cancelled_at = now
        order.assigned_engineer_id = None

    await db.commit()
    await db.refresh(order)
    return _planned(order)


@router.patch("/requests/{rid}/coords")
async def set_coords(rid: str, data: CoordsIn, db: SessionDep,
                     user: User = Depends(get_current_user)):
    order = await _get_order(db, rid, user)
    try:
        lat = float(data.lat)
        lon = float(data.lon)
    except (TypeError, ValueError):
        raise HTTPException(400, "Некорректные координаты")
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise HTTPException(400, "Координаты вне допустимого диапазона")

    order.lat = lat
    order.lon = lon
    await db.commit()
    await db.refresh(order)

    if order.assigned_engineer_id:
        return _planned(order)
    return _unalloc(order)


@router.post("/requests/{rid}/restore")
async def restore_cancelled(rid: str, db: SessionDep,
                            user: User = Depends(get_current_user)):
    order = await _get_order(db, rid, user)
    if order.status != RequestStatus.CANCELLED:
        raise HTTPException(400, "Заявка не была отменена")

    order.status = RequestStatus.NEW
    order.cancelled_at = None
    order.cancel_reason = None
    order.assigned_engineer_id = None

    await db.commit()
    await db.refresh(order)
    return _unalloc(order)


@router.get("/requests/{rid}/suitable-engineers")
async def suitable_engineers(
    rid: str,
    district_id: str = Query(...),
    visit_date: str = Query(None),
    db: SessionDep = None,
    user: User = Depends(get_current_user),
):
    vd = None
    if visit_date:
        try:
            vd = date_type.fromisoformat(visit_date)
        except ValueError:
            vd = None

    result = await find_suitable_engineers(db, district_id, rid, vd)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Не удалось подобрать мастеров"))
    return result


@router.post("/requests/urgent", response_model=UnallocatedRequestOut, status_code=201)
async def create_urgent(data: UrgentRequestIn, db: SessionDep,
                        user: User = Depends(get_current_user)):
    max_id = (await db.execute(select(func.max(Order.external_id)))).scalar() or 8000

    is_urgent = data.priority == "urgent"

    type_map = {
        "connection":    RequestType.CONNECTION,
        "reorder":       RequestType.REORDER,
        "local":         RequestType.LOCAL_REQUEST,
        "local_request": RequestType.LOCAL_REQUEST,
        "global":        RequestType.GLOBAL_ISSUE,
        "global_issue":  RequestType.GLOBAL_ISSUE,
    }
    raw_type = type_map.get(getattr(data, "request_type", "local"),
                            RequestType.LOCAL_REQUEST)

    if is_urgent:
        bk_type = RequestType.GLOBAL_ISSUE
    else:
        if raw_type == RequestType.GLOBAL_ISSUE:
            raise HTTPException(400, "Глобальная проблема доступна только для аварийных заявок")
        bk_type = raw_type

    # ── Имя района (в колонку district должен идти текст, не UUID) ──
    district_obj = await db.get(District, data.district_id)
    district_name = district_obj.name if district_obj else ""
    if not district_name:
        raise HTTPException(400, "Район не найден")

    # ── Адрес в формате «Город Москва, ул.Х, д. Y» ──
    def _fmt_address() -> str:
        city = (data.city or "").strip()
        street = (data.street or "").strip()
        house = (data.house or "").strip()
        building = (getattr(data, "building", "") or "").strip()

        if city:
            if not city.lower().startswith("город ") and not city.lower().startswith("г."):
                city = f"Город {city}"

        if street:
            low = street.lower()
            has_prefix = any(low.startswith(p) for p in (
                "ул.", "улица", "пр-кт", "пр-т", "пр.", "просп",
                "пер.", "переулок", "б-р", "бул.", "бульвар",
                "наб.", "набережная", "пл.", "площадь", "ш.", "шоссе",
                "ал.", "аллея", "туп.", "тупик", "дор.", "дорога",
                "пр-д", "проезд",
            ))
            if not has_prefix:
                street = f"ул.{street}"

        if house and not house.lower().startswith("д."):
            house = f"д. {house}"
        if building:
            house = f"{house} стр. {building}" if house else f"стр. {building}"

        return ", ".join(p for p in (city, street, house) if p)

    full_address = _fmt_address() or data.address

    # ── Геокодинг ──
    addr_for_geo = _address_for_geocode(data)
    lat, lon = 0.0, 0.0
    geocoded = False
    if addr_for_geo:
        print(f"[URGENT] геокодируем «{addr_for_geo}»", flush=True)
        try:
            loc = geo_geocode(addr_for_geo, tag="urgent")
        except Exception as e:
            print(f"[URGENT] геокодер упал: {e}", flush=True)
            loc = None
        if loc is not None:
            lat, lon = float(loc[0]), float(loc[1])
            geocoded = True
            print(f"[URGENT] ✓ {lat:.5f}, {lon:.5f}", flush=True)
        else:
            print(f"[URGENT] ✗ не геокодирован", flush=True)

    now = datetime.now()
    ws = _parse_hhmm(data.window_start) or now.time().replace(second=0, microsecond=0)
    we = _parse_hhmm(data.window_end) or (
        now + __import__("datetime").timedelta(hours=2)
    ).time().replace(second=0, microsecond=0)

    bk_status_value = bk_type.label
    hd_type_value   = bk_type.label
    gigabit_value   = "Нет"

    order = Order(
        external_id=max_id + 1,
        district_id=data.district_id,
        district=district_name,
        address=full_address,
        bk_type=bk_type,
        skill=bk_type.skill,
        priority=bk_type.priority,
        bk_status=bk_status_value,
        hd_type=hd_type_value,
        gigabit_connection=gigabit_value,
        status=RequestStatus.NEW,
        window_start=ws,
        window_end=we,
        visit_date=date_type.today(),
        duration_min=120,
        lat=lat,
        lon=lon,
        extra={
            "client_name":  data.client_name,
            "client_phone": data.client_phone,
            "city":         data.city,
            "street":       data.street,
            "house":        data.house,
            "building":     data.building,
            "entrance":     data.entrance,
            "floor":        data.floor,
            "apartment":    data.apartment,
            "asap":         is_urgent,
            "geocoded":     geocoded,
        },
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # ── Никакого авто-перераспределения. ──
    # Заявка просто добавляется в пул, диспетчер сам решит,
    # когда нажать «Распределить заявки».
    print(f"[URGENT] заявка #{order.external_id} добавлена в пул "
          f"(без авто-перераспределения)", flush=True)

    result = _unalloc(order)
    result.geocoded = geocoded
    return result


# ============================================================
#  Сброс
# ============================================================

@router.post("/requests/reset", response_model=ResetRequestsOut)
async def reset_requests(district_id: str = Query(...),
                         mode: str = Query("planned"),
                         visit_date: str = Query(None),
                         db: SessionDep = None,
                         user: User = Depends(get_current_user)):
    if mode not in ("planned", "all"):
        raise HTTPException(400, "mode должен быть planned или all")

    day = None
    if visit_date:
        try:
            day = date_type.fromisoformat(visit_date)
        except ValueError:
            day = None
    if day is None:
        day = date_type.today()

    base_conditions = [Order.district_id == district_id]

    if mode == "planned":
        base_conditions.append(Order.assigned_engineer_id.isnot(None))
        base_conditions.append(Order.status == RequestStatus.NEW)
        base_conditions.append(Order.visit_date == day)
    else:
        base_conditions.append(Order.status != RequestStatus.CANCELLED)
        base_conditions.append(Order.visit_date == day)

    reset_orders = (await db.execute(
        select(Order).where(*base_conditions)
    )).scalars().all()

    reset_count = 0
    for o in reset_orders:
        o.assigned_engineer_id = None
        o.status = RequestStatus.NEW
        o.departed_at = None
        o.started_at = None
        o.finished_at = None
        o.cancelled_at = None
        o.cancel_reason = None
        if isinstance(o.extra, dict):
            extra = dict(o.extra)
            extra.pop("planned", None)
            o.extra = extra
        reset_count += 1

    await db.commit()

    try:
        engs = (await db.execute(
            select(Engineer).where(Engineer.district_id == district_id)
        )).scalars().all()
        returned_links = 0
        for eng in engs:
            links = (await db.execute(
                select(EngineerEquipment).where(EngineerEquipment.engineer_id == eng.id)
            )).scalars().all()
            for link in links:
                eq = await db.get(Equipment, link.equipment_id)
                if eq:
                    eq.quantity += link.quantity
                await db.delete(link)
                returned_links += 1
        await db.commit()
        print(f"[RESET] оборудования возвращено: {returned_links}", flush=True)
    except Exception as e:
        print(f"[RESET] ошибка возврата оборудования: {e}", flush=True)

    try:
        await rebuild_maps(db, district_id, day)
    except Exception as e:
        print(f"[RESET] rebuild_maps: {e}", flush=True)

    print(f"[RESET] сброшено заявок: {reset_count} (mode={mode}, day={day})",
          flush=True)

    return ResetRequestsOut(ok=True, reset=reset_count)


# ============================================================
#  Инженеры
# ============================================================

@router.post("/engineers", response_model=EngineerOut, status_code=201)
async def create_engineer(data: EngineerIn, db: SessionDep,
                          user: User = Depends(get_current_user)):
    eng = Engineer(
        name=data.fio,
        district_id=data.district_id,
        transport=_TRANSPORT_TO_ENUM.get(data.transport, TransportType.PEDESTRIAN),
        phone=data.phone,
        birth_date=_parse_iso_date(data.birth_date),
        shift_start=_parse_hhmm(data.shift_start) or dtime(8, 0),
        shift_end=_parse_hhmm(data.shift_end) or dtime(17, 0),
        skills=data.skills or [],
        equipment=None,
        available=True,
        status=True,
    )
    db.add(eng)
    await db.commit()
    await db.refresh(eng)
    return _eng(eng)


@router.get("/engineers/{eid}", response_model=EngineerDetailsOut)
async def engineer_details(eid: str, db: SessionDep,
                           user: User = Depends(get_current_user)):
    eng = await db.get(Engineer, eid)
    if not eng:
        raise HTTPException(404, "Инженер не найден")

    rows = (await db.execute(
        select(EngineerEquipment, Equipment)
        .join(Equipment, Equipment.id == EngineerEquipment.equipment_id)
        .where(EngineerEquipment.engineer_id == eng.id)
        .where(EngineerEquipment.quantity > 0)
    )).all()

    equipment = [
        EngineerEquipmentOut(
            id=str(eq.id), kind=eq.kind, name=eq.name,
            count=int(link.quantity or 0),
            state="Новое", serial="—",
        )
        for (link, eq) in rows
    ]

    today = date_type.today()
    orders = (await db.execute(
        select(Order).where(
            Order.assigned_engineer_id == eng.id,
            Order.visit_date == today,
        ).order_by(Order.window_start)
    )).scalars().all()

    today_orders = []
    for o in orders:
        eta = f"ETA {o.started_at.strftime('%H:%M')}" if o.started_at else None
        today_orders.append(EngineerOrderOut(
            id=str(o.id), short_id=str(o.external_id), address=o.address,
            status=o.status.value if hasattr(o.status, "value") else str(o.status),
            status_label=_STATUS_LABEL.get(o.status, "—"),
            eta=eta, window=_fmt_window(o) or None,
        ))

    return EngineerDetailsOut(
        id=str(eng.id), name=eng.name, role_title=_ROLE_TITLE,
        transport_label=_TRANSPORT_LABEL.get(eng.transport, "Пеший"),
        on_shift=bool(eng.available), shift_label=_shift_label(eng),
        shift_start=eng.shift_start.strftime("%H:%M") if eng.shift_start else "08:00",
        shift_end=eng.shift_end.strftime("%H:%M") if eng.shift_end else "17:00",
        off_shift_reason=eng.off_shift_reason,
        phone=eng.phone, skills=eng.skills or [],
        location=getattr(eng, "location", None),
        equipment=equipment, today_orders=today_orders,
    )


@router.patch("/engineers/{eid}", response_model=EngineerOut)
async def patch_engineer(eid: str, data: EngineerPatchIn, db: SessionDep,
                         user: User = Depends(get_current_user)):
    eng = await db.get(Engineer, eid)
    if not eng:
        raise HTTPException(404, "Инженер не найден")
    if data.fio:
        eng.name = data.fio
    if data.phone is not None:
        eng.phone = data.phone
    if data.transport:
        eng.transport = _TRANSPORT_TO_ENUM.get(data.transport, eng.transport)
    if data.shift_start:
        eng.shift_start = _parse_hhmm(data.shift_start) or eng.shift_start
    if data.shift_end:
        eng.shift_end = _parse_hhmm(data.shift_end) or eng.shift_end
    if data.skills is not None:
        eng.skills = data.skills
    await db.commit()
    await db.refresh(eng)
    return _eng(eng)


@router.post("/engineers/{eid}/shift/end")
async def engineer_end_shift(eid: str, data: EndShiftIn, db: SessionDep,
                             user: User = Depends(get_current_user)):
    eng = await db.get(Engineer, eid)
    if not eng:
        raise HTTPException(404, "Инженер не найден")

    reset_stmt = (
        sa_update(Order)
        .where(
            Order.assigned_engineer_id == eng.id,
            Order.status.notin_([RequestStatus.DONE, RequestStatus.CANCELLED]),
        )
        .values(assigned_engineer_id=None, status=RequestStatus.NEW)
    )
    reset_result = await db.execute(reset_stmt)
    reset_count = reset_result.rowcount or 0

    eng.available = False
    eng.off_shift_reason = data.reason
    await db.commit()

    print(f"[SHIFT] мастер {eng.name} снят со смены, "
          f"заявок в пул: {reset_count}", flush=True)

    try:
        if eng.district_id:
            await rebuild_maps(db, eng.district_id)
    except Exception as e:
        print(f"[SHIFT] rebuild_maps: {e}", flush=True)

    return {"ok": True, "reset_requests": reset_count}


@router.post("/engineers/{eid}/shift/start")
async def engineer_start_shift(eid: str, db: SessionDep,
                               user: User = Depends(get_current_user)):
    eng = await db.get(Engineer, eid)
    if not eng:
        raise HTTPException(404, "Инженер не найден")
    eng.available = True
    eng.off_shift_reason = None
    await db.commit()
    return {"ok": True}


@router.post("/engineers/{eid}/tml/print")
async def engineer_print_tml(eid: str, db: SessionDep,
                             user: User = Depends(get_current_user)):
    eng = await db.get(Engineer, eid)
    if not eng:
        raise HTTPException(404, "Инженер не найден")
    return {"ok": True, "message": "Акт ТМЦ отправлен на печать"}


# ============================================================
#  Оборудование
# ============================================================

@router.get("/equipment", response_model=EquipmentListOut)
async def list_equipment(db: SessionDep,
                         user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(Equipment).order_by(Equipment.kind, Equipment.name)
    )).scalars().all()
    return EquipmentListOut(equipment=[_eq_out(e) for e in rows])


@router.post("/equipment", response_model=EquipmentOut, status_code=201)
async def create_equipment(data: EquipmentCreateIn, db: SessionDep,
                           user: User = Depends(get_current_user)):
    eq = Equipment(kind=data.kind, name=data.name, quantity=data.quantity)
    db.add(eq)
    await db.commit()
    await db.refresh(eq)
    return _eq_out(eq)


@router.patch("/equipment/{eq_id}", response_model=EquipmentOut)
async def patch_equipment(eq_id: str, data: EquipmentPatchIn, db: SessionDep,
                          user: User = Depends(get_current_user)):
    eq = await db.get(Equipment, eq_id)
    if not eq:
        raise HTTPException(404, "Оборудование не найдено")

    if data.kind:
        eq.kind = data.kind
    if data.name:
        eq.name = data.name
    if data.quantity is not None:
        eq.quantity = data.quantity
    elif data.delta is not None:
        eq.quantity = max(0, eq.quantity + data.delta)

    await db.commit()
    await db.refresh(eq)
    return _eq_out(eq)


@router.delete("/equipment/{eq_id}")
async def delete_equipment(eq_id: str, db: SessionDep,
                           user: User = Depends(get_current_user)):
    eq = await db.get(Equipment, eq_id)
    if not eq:
        raise HTTPException(404, "Оборудование не найдено")

    used = (await db.execute(
        select(EngineerEquipment).where(EngineerEquipment.equipment_id == eq.id).limit(1)
    )).scalar_one_or_none()
    if used:
        raise HTTPException(400, "Нельзя удалить: оборудование есть у инженеров")

    await db.delete(eq)
    await db.commit()
    return {"ok": True}


@router.post("/engineers/{eid}/equipment")
async def issue_equipment(eid: str, data: IssueEquipmentIn, db: SessionDep,
                          user: User = Depends(get_current_user)):
    eng = await db.get(Engineer, eid)
    if not eng:
        raise HTTPException(404, "Инженер не найден")

    eq = await db.get(Equipment, data.equipment_id)
    if not eq:
        raise HTTPException(404, "Оборудование не найдено")
    if eq.quantity < data.quantity:
        raise HTTPException(400, f"Недостаточно на складе: доступно {eq.quantity}")

    link = await db.get(EngineerEquipment, {
        "engineer_id": eng.id,
        "equipment_id": eq.id,
    })
    if link:
        link.quantity += data.quantity
    else:
        db.add(EngineerEquipment(
            engineer_id=eng.id,
            equipment_id=eq.id,
            quantity=data.quantity,
        ))

    eq.quantity -= data.quantity
    await db.commit()
    return {"ok": True}


@router.post("/engineers/{eid}/equipment/{eq_id}/return")
async def return_equipment_partial(eid: str, eq_id: str,
                                   data: ReturnEquipmentIn,
                                   db: SessionDep,
                                   user: User = Depends(get_current_user)):
    link = await db.get(EngineerEquipment, {
        "engineer_id": eid,
        "equipment_id": eq_id,
    })
    if not link:
        raise HTTPException(404, "Оборудование у инженера не найдено")
    if data.quantity > link.quantity:
        raise HTTPException(400, f"У инженера только {link.quantity} шт")

    eq = await db.get(Equipment, eq_id)
    if eq:
        eq.quantity += data.quantity

    link.quantity -= data.quantity
    if link.quantity == 0:
        await db.delete(link)

    await db.commit()
    return {"ok": True}


@router.delete("/engineers/{eid}/equipment/{eq_id}")
async def revoke_equipment(eid: str, eq_id: str, db: SessionDep,
                           user: User = Depends(get_current_user)):
    link = await db.get(EngineerEquipment, {
        "engineer_id": eid,
        "equipment_id": eq_id,
    })
    if not link:
        raise HTTPException(404, "Оборудование у инженера не найдено")

    eq = await db.get(Equipment, eq_id)
    if eq:
        eq.quantity += link.quantity

    await db.delete(link)
    await db.commit()
    return {"ok": True}


@router.delete("/engineers/{eid}/equipment",
               response_model=ClearEngineerEquipmentOut)
async def clear_engineer_equipment(eid: str, db: SessionDep,
                                   user: User = Depends(get_current_user)):
    eng = await db.get(Engineer, eid)
    if not eng:
        raise HTTPException(404, "Инженер не найден")

    links = (await db.execute(
        select(EngineerEquipment).where(EngineerEquipment.engineer_id == eng.id)
    )).scalars().all()

    cleared = 0
    for link in links:
        eq = await db.get(Equipment, link.equipment_id)
        if eq:
            eq.quantity += link.quantity
        await db.delete(link)
        cleared += 1

    await db.commit()
    return ClearEngineerEquipmentOut(ok=True, cleared=cleared)


# ============================================================
#  Распределение и карты
# ============================================================

@router.post("/distribute", response_model=DistributeOut)
async def distribute(district_id: str = Query(...),
                     visit_date: str = Query(None),
                     regeocode: bool = Query(False),
                     db: SessionDep = None,
                     user: User = Depends(get_current_user)):
    vd = None
    if visit_date:
        try:
            vd = date_type.fromisoformat(visit_date)
        except ValueError:
            vd = None
    result = await distribute_orders(db, district_id, vd, regeocode)
    return DistributeOut(**result)


@router.get("/maps/latest", response_model=MapLinkOut)
async def get_latest_map(district_id: str = Query(...),
                         user: User = Depends(get_current_user)):
    return MapLinkOut(map_url=latest_common_map(district_id))


@router.get("/engineers/{eid}/map", response_model=MapLinkOut)
async def get_engineer_map(eid: str, district_id: str = Query(...),
                           user: User = Depends(get_current_user)):
    return MapLinkOut(map_url=latest_engineer_map(district_id, eid))


@router.post("/maps/rebuild")
async def rebuild_maps_endpoint(district_id: str = Query(...),
                                visit_date: str = Query(None),
                                db: SessionDep = None,
                                user: User = Depends(get_current_user)):
    vd = None
    if visit_date:
        try:
            vd = date_type.fromisoformat(visit_date)
        except ValueError:
            vd = None

    result = await rebuild_maps(db, district_id, vd)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Не удалось перерисовать карты"))
    return result