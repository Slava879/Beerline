# backend/app/services/routing.py
"""
Адаптер между БД и algorithm.py.

Ключевые правила:
  * приоритет заявки доминирует над regret-эвристикой;
  * невозможные по времени/навыку/оборудованию пары не назначаются;
  * что не влезает — остаётся в unassigned и возвращается в UI;
  * дефолтных координат больше нет: если адрес офиса не задан или не
    геокодируется — распределение не запускается, UI получает ошибку;
  * заявки, у которых нет координат и не удалось их определить —
    попадают в unassigned;
  * окно заявки берётся из БД (window_start / window_end). Для срочных,
    созданных через UI, там уже стоит «момент создания + 2ч»;
  * есть подбор мастеров под заявку (find_suitable_engineers) —
    с проверкой навыка, оборудования и времени;
  * текущий мастер заявки исключается из списка подходящих;
  * время выезда в extra["planned"]["taken"] считается как
    «фактический старт работ − время в пути», чтобы не было абсурда
    вида «выехал в 10:00 при окне 14:00–16:00».
"""
from __future__ import annotations

import uuid
from datetime import date as date_type, datetime, time as dtime, timedelta
from pathlib import Path
import math

from sqlalchemy import select, update as sa_update
import time

from backend.app.services import algorithm as algo
from backend.app.services.geocoding import geocode
from backend.app.engineers.models import Engineer, TransportType
from backend.app.orders.models import Order, RequestStatus, RequestType
from backend.app.districts.models import District
from backend.app.equipment.models import Equipment, EngineerEquipment


STATIC_ROOT = Path(__file__).resolve().parents[2] / "static"
MAPS_DIR = STATIC_ROOT / "maps"
MAPS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
#  Переводы значений между БД и алгоритмом
# ============================================================

TYPE_TO_BK = {
    RequestType.CONNECTION:    "Подключение",
    RequestType.REORDER:       "Дозаказ",
    RequestType.LOCAL_REQUEST: "Локальная заявка",
    RequestType.GLOBAL_ISSUE:  "Глобальная проблема",
}

TRANS_TO_ALGO = {
    TransportType.CAR:        "автомобиль",
    TransportType.BICYCLE:    "велосипед",
    TransportType.PEDESTRIAN: "пешеход",
}

SKILL_TO_ALGO = {
    "Подключение":         "подключение",
    "Глобальная проблема": "глобальные проблемы",
    "Дозаказ":             "дозаказ",
    "Локальная заявка":    "локальные работы",
}

SKILL_DB_TO_ALGO = {
    "подключение":         "подключение",
    "глобальные проблемы": "глобальные проблемы",
    "дозаказ":             "дозаказ",
    "локальные работы":    "локальные работы",
    "Подключение":         "подключение",
    "Глобальная проблема": "глобальные проблемы",
    "Дозаказ":             "дозаказ",
    "Локальная заявка":    "локальные работы",
}

KIND_MAP = {"router": "router", "stb": "receiver"}

_DB_STATUS_TO_ALGO = {
    "new":         "planned",
    "taken":       "en_route",
    "in_progress": "in_progress",
    "done":        "completed",
    "cancelled":   "cancelled",
}


def _db_status_value(order: Order) -> str:
    s = order.status
    return s.value if hasattr(s, "value") else str(s)


# ============================================================
#  Мастера
# ============================================================

def _make_engineers_from_db(engineers_db, day):
    algo_engineers = []
    id_map = {}

    for idx, eng in enumerate(engineers_db, 1):
        if not eng.available:
            continue

        transport = TRANS_TO_ALGO.get(eng.transport, "пешеход")
        skills = {
            SKILL_TO_ALGO[s]
            for s in (eng.skills or [])
            if s in SKILL_TO_ALGO
        }
        if not skills:
            continue

        shift_start_t = eng.shift_start or dtime(8, 0)
        shift_end_t   = eng.shift_end   or dtime(17, 0)

        shift_start = day.replace(hour=shift_start_t.hour,
                                  minute=shift_start_t.minute,
                                  second=0, microsecond=0)
        shift_end = day.replace(hour=shift_end_t.hour,
                                minute=shift_end_t.minute,
                                second=0, microsecond=0)

        algo_engineers.append({
            "id":                  idx,
            "name":                eng.name,
            "skills":              skills,
            "transport":           transport,
            "shift_start":         shift_start,
            "shift_end":           shift_end,
            "speed_kmh":           algo.TRANSPORT_SPEED_KMH[transport],
            "is_active":           True,
            "equipment_allocated": {"router": 0, "stb": 0},
        })
        id_map[idx] = eng.id

    return algo_engineers, id_map


# ============================================================
#  Задачи
# ============================================================

def _make_tasks_from_db(orders_db, day):
    algo_tasks = []
    id_map = {}

    for order in orders_db:
        bk = TYPE_TO_BK.get(order.bk_type, "Локальная заявка")

        priority_db = order.priority
        if priority_db is None:
            priority_db = algo.PRIORITY.get(bk, 9)

        is_urgent = (bk == "Глобальная проблема") or (priority_db == 0)

        ws = order.window_start or dtime(10, 0)
        we = order.window_end   or dtime(22, 0)
        start = day.replace(hour=ws.hour, minute=ws.minute,
                            second=0, microsecond=0)
        end = day.replace(hour=we.hour, minute=we.minute,
                          second=0, microsecond=0)
        if end <= start:
            end = start + timedelta(hours=2)

        lat = float(order.lat or 0)
        lon = float(order.lon or 0)
        if not lat or not lon:
            continue

        norm = algo.NORMS.get(bk, algo.DEFAULT_NORM)
        task_id_str = str(order.external_id)

        priority = -1 if is_urgent else algo.PRIORITY.get(bk, 9)

        skill = SKILL_DB_TO_ALGO.get(order.skill or "")
        if not skill:
            skill = algo.TASK_SKILL.get(bk, "локальные работы")

        task = {
            "id":         task_id_str,
            "bk":         bk,
            "hd":         order.hd_type or "",
            "start":      start,
            "end":        end,
            "district":   order.district or "",
            "address":    order.address or "",
            "connection": "",
            "gigabit":    order.gigabit_connection or "",
            "status":     _DB_STATUS_TO_ALGO.get(_db_status_value(order), "planned"),
            "is_urgent":  is_urgent,
            "norm":       norm["name"],
            "road_min":   norm["road"],
            "service":    norm["tech"] + norm["docs"],
            "base_norm":  norm["base"],
            "skill":      skill,
            "priority":   priority,
            "urgent_ref_time": datetime.now() if is_urgent else None,
            "lat":        lat,
            "lon":        lon,
        }
        algo_tasks.append(task)
        id_map[task_id_str] = order.id

    return algo_tasks, id_map


def _describe_unassigned(task):
    bk = task.get("bk", "?")
    eq = algo.TASK_EQUIPMENT.get(bk, {"router": 0, "stb": 0})

    if bk == "Глобальная проблема":
        return ("Нет мастера с навыком «глобальные проблемы», "
                "чья смена покрывает окно заявки")

    parts = [f"тип: {bk}"]
    if eq["router"] or eq["stb"]:
        parts.append(
            f"нужно оборудование router×{eq['router']}, stb×{eq['stb']}"
        )
    parts.append("нет мастера, который успевает по времени и навыку")
    return ", ".join(parts)


# ============================================================
#  Адрес офиса и координаты
# ============================================================

def _district_office_address(district: District) -> str:
    parts = []
    if district.city:
        parts.append(district.city.strip())
    if district.street:
        parts.append(district.street.strip())
    if district.house:
        hb = district.house.strip()
        if district.building:
            hb += f"к{district.building.strip()}"
        parts.append(hb)
    return ", ".join(p for p in parts if p)


def _district_has_address(district: District) -> bool:
    return bool(district.city or district.street or district.house)


def _has_coords(lat, lon) -> bool:
    try:
        lat = float(lat or 0)
        lon = float(lon or 0)
    except Exception:
        return False
    return lat != 0 and lon != 0


async def _geocode_office(db, district: District, regeocode: bool):
    print(f"[DIST] Офис участка «{district.name}»", flush=True)

    if not _district_has_address(district):
        print("[DIST] ✗ адрес офиса не задан", flush=True)
        return None

    if not regeocode and _has_coords(district.lat, district.lon):
        print(f"[DIST] ✓ используем сохранённые координаты "
              f"{float(district.lat):.5f}, {float(district.lon):.5f}", flush=True)
        return float(district.lat), float(district.lon)

    address = _district_office_address(district)
    print(f"[DIST] геокодируем офис: «{address}»", flush=True)
    loc = geocode(address, tag="office")
    if loc is None:
        print("[DIST] ✗ не удалось геокодировать офис", flush=True)
        return None

    district.lat = loc[0]
    district.lon = loc[1]
    await db.flush()
    print(f"[DIST] ✓ офис сохранён: {loc[0]:.5f}, {loc[1]:.5f}", flush=True)
    return loc


async def _geocode_orders(db, orders_db, regeocode: bool):
    print(f"[DIST] Геокодирование заявок: всего {len(orders_db)}, "
          f"regeocode={regeocode}", flush=True)

    ok_orders = []
    failed_ids = set()
    skipped = 0

    for i, order in enumerate(orders_db, 1):
        has_coords = _has_coords(order.lat, order.lon)
        if has_coords and not regeocode:
            skipped += 1
            print(f"[DIST] [{i}/{len(orders_db)}] #{order.external_id} — "
                  f"уже с координатами, пропускаем", flush=True)
            ok_orders.append(order)
            continue

        parts = []
        if order.district:
            parts.append(order.district)
        if order.address:
            parts.append(order.address)
        address = ", ".join(p for p in parts if p)

        print(f"[DIST] [{i}/{len(orders_db)}] #{order.external_id} — «{address}»", flush=True)

        loc = geocode(address) if address else None
        if loc is None:
            failed_ids.add(order.id)
            print(f"[DIST] [{i}/{len(orders_db)}] #{order.external_id} — ✗ не геокодирован", flush=True)
            continue

        order.lat = loc[0]
        order.lon = loc[1]
        ok_orders.append(order)

    await db.flush()
    print(f"[DIST] Геокодирование завершено: ok={len(ok_orders)}, "
          f"failed={len(failed_ids)}, skip={skipped}", flush=True)
    return ok_orders, failed_ids


async def distribute_orders(db, district_id: uuid.UUID,
                            visit_date: date_type | None = None,
                            regeocode: bool = False):
    t_start = time.time()
    day_date = visit_date or date_type.today()
    day = datetime.combine(day_date, dtime(0, 0))
    algo.DAY = day

    print(f"\n{'='*60}", flush=True)
    print(f"[DIST] Старт распределения: district_id={district_id}, "
          f"visit_date={day_date}, regeocode={regeocode}", flush=True)
    print(f"{'='*60}", flush=True)

    district = await db.get(District, district_id)
    if not district:
        print("[DIST] ✗ район не найден", flush=True)
        return {"ok": False, "error": "Район не найден"}

    if not _district_has_address(district):
        print("[DIST] ✗ адрес офиса не задан", flush=True)
        return {
            "ok": False,
            "error": (
                "У участка не задан адрес офиса. Откройте «Выбрать участок» "
                "и заполните город / улицу / дом."
            ),
        }

    print(f"[DIST] Шаг 1/6: геокодирование офиса…", flush=True)
    office_loc = await _geocode_office(db, district, regeocode)
    if office_loc is None:
        return {
            "ok": False,
            "error": (
                f"Не удалось определить координаты офиса участка "
                f"«{district.name}». Проверьте адрес и повторите."
            ),
        }
    await db.commit()

    print(f"[DIST] Шаг 2/6: сброс заявок на {day_date}…", flush=True)
    await db.execute(
        sa_update(Order)
        .where(
            Order.district_id == district_id,
            Order.visit_date == day_date,
            Order.status == RequestStatus.NEW,
            Order.assigned_engineer_id.isnot(None),
        )
        .values(assigned_engineer_id=None)
    )
    await db.commit()

    engineers_db = (await db.execute(
        select(Engineer).where(Engineer.district_id == district_id)
    )).scalars().all()

    orders_db_raw = (await db.execute(
        select(Order).where(
            Order.district_id == district_id,
            Order.visit_date == day_date,
            Order.assigned_engineer_id.is_(None),
            Order.status != RequestStatus.CANCELLED,
        )
    )).scalars().all()

    print(f"[DIST] Мастеров: {len(engineers_db)}, "
          f"нераспределённых заявок: {len(orders_db_raw)}", flush=True)

    if not engineers_db:
        return {"ok": False, "error": "Нет мастеров в этом районе"}
    if not orders_db_raw:
        return {"ok": False, "error": "Нет нераспределённых заявок на эту дату"}

    print(f"[DIST] Шаг 3/6: геокодирование заявок…", flush=True)
    orders_db, failed_ids = await _geocode_orders(db, orders_db_raw, regeocode)
    await db.commit()

    if not orders_db:
        return {
            "ok": False,
            "error": "Не удалось определить координаты ни одной заявки.",
        }

    print(f"[DIST] Шаг 4/6: подготовка данных для алгоритма…", flush=True)
    algo_engineers, eng_id_map = _make_engineers_from_db(engineers_db, day)
    algo_tasks, ord_id_map = _make_tasks_from_db(orders_db, day)

    print(f"[DIST] В алгоритм: мастеров {len(algo_engineers)}, "
          f"задач {len(algo_tasks)}", flush=True)

    if not algo_engineers:
        return {"ok": False, "error": "Нет активных мастеров с навыками"}
    if not algo_tasks:
        return {"ok": False, "error": "Нет заявок с определёнными координатами"}

    print(f"[DIST] Шаг 5/6: распределение…", flush=True)
    pending = list(algo_tasks)
    pending.sort(key=lambda x: (x["priority"], x["end"]))

    routes = algo.regret_insert(pending, algo_engineers, office_loc, check_eq=False)
    print(f"[DIST]   regret_insert готов: {sum(len(r) for r in routes.values())} назначено, "
          f"{len(pending)} осталось", flush=True)

    routes = algo.local_search(routes, algo_engineers, office_loc, check_eq=False)
    print(f"[DIST]   local_search готов", flush=True)

    if pending:
        routes = algo.regret_insert(pending, algo_engineers, office_loc,
                                    check_eq=False, routes_init=routes)

    routes = algo.minimize_engineers(routes, algo_engineers, office_loc,
                                     check_eq=False)
    print(f"[DIST]   minimize_engineers готов", flush=True)

    if pending:
        routes = algo.regret_insert(pending, algo_engineers, office_loc,
                                    check_eq=False, routes_init=routes)

    algo.allocate_equipment(routes, algo_engineers)

    for eid, tasks in routes.items():
        for i, t in enumerate(tasks, 1):
            t["seq"] = i

    print(f"[DIST] Шаг 6/6: сохранение в БД…", flush=True)
    now = datetime.now()
    algo.update_task_statuses(routes, algo_engineers, office_loc, now)

    assigned_task_ids = set()
    assigned_count = 0

    for eng_int_id, route in routes.items():
        uuid_eid = eng_id_map.get(eng_int_id)
        if uuid_eid is None:
            continue
        for task in route:
            order_uuid = ord_id_map.get(task["id"])
            if order_uuid is None:
                continue
            order = await db.get(Order, order_uuid)
            if not order:
                continue
            order.assigned_engineer_id = uuid_eid
            order.status = RequestStatus.NEW
            assigned_task_ids.add(task["id"])
            assigned_count += 1

    await db.commit()
    print(f"[DIST]   назначено: {assigned_count}", flush=True)

    await _save_planned_times(db, routes, office_loc, algo_engineers,
                              eng_id_map, ord_id_map)
    await _reset_and_issue_equipment(db, engineers_db, algo_engineers,
                                     eng_id_map, routes)

    unassigned = [
        {
            "id":      task["id"],
            "address": task["address"],
            "reason":  _describe_unassigned(task),
        }
        for task in algo_tasks
        if task["id"] not in assigned_task_ids
    ]

    for order in orders_db_raw:
        if order.id in failed_ids:
            unassigned.append({
                "id":      str(order.external_id),
                "address": order.address or "",
                "reason":  "Не удалось определить координаты адреса",
            })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    district_dir = MAPS_DIR / str(district_id)
    district_dir.mkdir(parents=True, exist_ok=True)

    map_data = algo.build_map_data(routes, algo_engineers, office_loc, now)

    common_path = district_dir / f"all_{ts}.html"
    algo._render_map(map_data, "Маршруты всех мастеров", str(common_path))

    per_engineer = {}
    for m in map_data:
        eng_int_id = m["id"]
        uuid_eid = eng_id_map.get(eng_int_id)
        if uuid_eid is None:
            continue
        path = district_dir / f"engineer_{uuid_eid}_{ts}.html"
        algo._render_map([m], f"Маршрут мастера {eng_int_id}", str(path))
        per_engineer[str(uuid_eid)] = (
            f"/static/maps/{district_id}/engineer_{uuid_eid}_{ts}.html"
        )

    elapsed = time.time() - t_start
    print(f"{'='*60}", flush=True)
    print(f"[DIST] ГОТОВО за {elapsed:.1f}с: назначено {assigned_count} "
          f"из {len(algo_tasks)}, нераспределённых {len(unassigned)}", flush=True)
    print(f"{'='*60}\n", flush=True)

    return {
        "ok":           True,
        "assigned":     assigned_count,
        "total":        len(algo_tasks),
        "unassigned":   unassigned,
        "map_url":      f"/static/maps/{district_id}/all_{ts}.html",
        "per_engineer": per_engineer,
        "timestamp":    ts,
    }


# ============================================================
#  Оборудование
# ============================================================

async def _reset_and_issue_equipment(db, engineers_db, algo_engineers,
                                     eng_id_map, routes):
    for eng in engineers_db:
        links = (await db.execute(
            select(EngineerEquipment).where(EngineerEquipment.engineer_id == eng.id)
        )).scalars().all()
        for link in links:
            eq = await db.get(Equipment, link.equipment_id)
            if eq:
                eq.quantity += link.quantity
            await db.delete(link)
    await db.flush()

    for eng_int_id, route in routes.items():
        uuid_eid = eng_id_map.get(eng_int_id)
        if uuid_eid is None:
            continue
        eng = next((e for e in algo_engineers if e["id"] == eng_int_id), None)
        if eng is None:
            continue

        need = algo.route_equipment_needed(route)
        if eng["transport"] == "автомобиль":
            need["router"] += algo.EQUIPMENT_BUFFER
            need["stb"]    += algo.EQUIPMENT_BUFFER

        for algo_kind, count in need.items():
            if count <= 0:
                continue
            db_kind = KIND_MAP.get(algo_kind, algo_kind)
            eq = (await db.execute(
                select(Equipment).where(Equipment.kind == db_kind).limit(1)
            )).scalar_one_or_none()
            if eq is None:
                print(f"  ⚠ Нет на складе вида {db_kind}", flush=True)
                continue
            if eq.quantity < count:
                print(f"  ⚠ Недостаточно {db_kind}: нужно {count}, есть {eq.quantity}",
                      flush=True)
                count = eq.quantity
            if count <= 0:
                continue
            eq.quantity -= count
            db.add(EngineerEquipment(
                engineer_id=uuid_eid,
                equipment_id=eq.id,
                quantity=count,
            ))
    await db.commit()


# ============================================================
#  Плановые времена
# ============================================================

async def _save_planned_times(db, routes, office_loc, algo_engineers,
                              eng_id_map, ord_id_map):
    eng_by_int_id = {e["id"]: e for e in algo_engineers}

    for eng_int_id, route in routes.items():
        eng = eng_by_int_id.get(eng_int_id)
        if not eng or not route:
            continue
        ev = algo.evaluate_route(eng, route, office_loc,
                                 equipment_full_route=route)
        for item in ev["schedule"]:
            task = item["task"]
            order_uuid = ord_id_map.get(task["id"])
            if order_uuid is None:
                continue
            order = await db.get(Order, order_uuid)
            if not order:
                continue

            # Время выезда — за travel-минут до фактического старта работ,
            # а НЕ момент окончания предыдущей заявки/начало смены.
            # Иначе мастер «выезжает в 08:00» на заявку с окном 14:00–16:00
            # и просто ждёт на месте 6 часов.
            departure = item["start"] - timedelta(
                minutes=algo.effective_travel_min(item["travel_min"])
            )

            extra = dict(order.extra or {})
            extra["planned"] = {
                "taken":       departure.strftime("%H:%M"),
                "in_progress": item["start"].strftime("%H:%M"),
                "done":        item["end"].strftime("%H:%M"),
            }
            order.extra = extra
    await db.commit()


# ============================================================
#  Перерисовка карт
# ============================================================

async def rebuild_maps(db, district_id: uuid.UUID,
                       visit_date: date_type | None = None):
    day_date = visit_date or date_type.today()
    day = datetime.combine(day_date, dtime(0, 0))

    district = await db.get(District, district_id)
    if not district or not _has_coords(district.lat, district.lon):
        return {"ok": False, "error": "Нет координат офиса участка"}

    office_loc = (float(district.lat), float(district.lon))

    engineers_db = (await db.execute(
        select(Engineer).where(Engineer.district_id == district_id)
    )).scalars().all()

    orders_db = (await db.execute(
        select(Order).where(
            Order.district_id == district_id,
            Order.visit_date == day_date,
            Order.assigned_engineer_id.isnot(None),
            Order.status != RequestStatus.CANCELLED,
        )
    )).scalars().all()

    algo_engineers, eng_id_map = _make_engineers_from_db(engineers_db, day)
    uuid_to_int = {str(uuid_v): int_k for int_k, uuid_v in eng_id_map.items()}

    orders_by_eng: dict[str, list] = {}
    for o in orders_db:
        uuid_str = str(o.assigned_engineer_id)
        orders_by_eng.setdefault(uuid_str, []).append(o)

    routes = {}
    for uuid_str, orders in orders_by_eng.items():
        eng_int_id = uuid_to_int.get(uuid_str)
        if eng_int_id is None:
            continue

        def sort_key(o):
            extra = o.extra if isinstance(o.extra, dict) else {}
            planned = extra.get("planned") if isinstance(extra.get("planned"), dict) else {}
            taken = planned.get("taken") or "99:99"
            ws = o.window_start.strftime("%H:%M") if o.window_start else "99:99"
            return (taken, ws)

        orders_sorted = sorted(orders, key=sort_key)

        tasks, _ = _make_tasks_from_db(orders_sorted, day)
        if tasks:
            routes[eng_int_id] = tasks

    if not routes:
        return {"ok": True, "map_url": None, "per_engineer": {}, "timestamp": None}

    algo.allocate_equipment(routes, algo_engineers)

    for eid, tasks in routes.items():
        for i, t in enumerate(tasks, 1):
            t["seq"] = i

    now = datetime.now()
    algo.update_task_statuses(routes, algo_engineers, office_loc, now)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    district_dir = MAPS_DIR / str(district_id)
    district_dir.mkdir(parents=True, exist_ok=True)

    map_data = algo.build_map_data(routes, algo_engineers, office_loc, now)

    common_path = district_dir / f"all_{ts}.html"
    algo._render_map(map_data, "Маршруты всех мастеров", str(common_path))

    per_engineer = {}
    for m in map_data:
        eng_int_id = m["id"]
        uuid_eid = eng_id_map.get(eng_int_id)
        if uuid_eid is None:
            continue
        path = district_dir / f"engineer_{uuid_eid}_{ts}.html"
        algo._render_map([m], f"Маршрут мастера {eng_int_id}", str(path))
        per_engineer[str(uuid_eid)] = (
            f"/static/maps/{district_id}/engineer_{uuid_eid}_{ts}.html"
        )

    print(f"[REBUILD] Карты перерисованы: district={district_id}, "
          f"мастеров={len(per_engineer)}, ts={ts}", flush=True)

    return {
        "ok":           True,
        "map_url":      f"/static/maps/{district_id}/all_{ts}.html",
        "per_engineer": per_engineer,
        "timestamp":    ts,
    }


# ============================================================
#  Подбор мастеров под заявку
# ============================================================

async def find_suitable_engineers(db, district_id, order_id, visit_date=None):
    """
    Возвращает список мастеров, которым можно назначить заявку.

    Особенности:
      * текущий мастер заявки (если она уже распределена) исключается;
      * для каждого кандидата считается время в пути до новой заявки;
      * для каждого кандидата считается, на сколько минут сдвинутся
        его последующие заявки после вставки новой.
    """
    day_date = visit_date or date_type.today()
    day = datetime.combine(day_date, dtime(0, 0))
    algo.DAY = day

    order = await db.get(Order, order_id)
    if not order:
        return {"ok": False, "error": "Заявка не найдена"}

    district = await db.get(District, district_id)
    if not district or not _has_coords(district.lat, district.lon):
        return {"ok": False, "error": "Нет координат офиса участка"}
    office_loc = (float(district.lat), float(district.lon))

    new_tasks, _ = _make_tasks_from_db([order], day)
    if not new_tasks:
        return {"ok": False, "error": "У заявки нет координат"}
    new_task = new_tasks[0]

    skill_needed = new_task.get("skill") or algo.TASK_SKILL.get(
        new_task["bk"], "локальные работы"
    )

    engineers_db = (await db.execute(
        select(Engineer).where(Engineer.district_id == district_id)
    )).scalars().all()
    algo_engineers, eng_id_map = _make_engineers_from_db(engineers_db, day)

    orders_db = (await db.execute(
        select(Order).where(
            Order.district_id == district_id,
            Order.visit_date == day_date,
            Order.assigned_engineer_id.isnot(None),
            Order.status != RequestStatus.CANCELLED,
            Order.id != order_id,
        )
    )).scalars().all()
    orders_by_eng: dict[str, list] = {}
    for o in orders_db:
        orders_by_eng.setdefault(str(o.assigned_engineer_id), []).append(o)

    current_engineer_id = (
        str(order.assigned_engineer_id) if order.assigned_engineer_id else None
    )

    stock: dict[str, int] = {}
    for eq in (await db.execute(select(Equipment))).scalars().all():
        stock[eq.kind] = int(eq.quantity or 0)

    equipment_by_eng: dict[str, dict[str, int]] = {}
    if engineers_db:
        ee_rows = (await db.execute(
            select(EngineerEquipment, Equipment)
            .join(Equipment, Equipment.id == EngineerEquipment.equipment_id)
            .where(EngineerEquipment.engineer_id.in_([e.id for e in engineers_db]))
            .where(EngineerEquipment.quantity > 0)
        )).all()
        for link, eq in ee_rows:
            equipment_by_eng.setdefault(str(link.engineer_id), {})[eq.kind] = (
                int(link.quantity or 0)
            )

    def _equipment_available(eng_db, required: dict) -> bool:
        need_router = required.get("router", 0)
        need_stb    = required.get("stb", 0)

        have = equipment_by_eng.get(str(eng_db.id), {})
        have_router = have.get("router", 0)
        have_stb    = have.get("receiver", 0)

        need_router_extra = max(0, need_router - have_router)
        need_stb_extra    = max(0, need_stb    - have_stb)

        if need_router_extra > stock.get("router", 0):
            return False
        if need_stb_extra > stock.get("receiver", 0):
            return False
        return True

    suitable: list[dict] = []

    for eng in algo_engineers:
        uuid_eid = str(eng_id_map[eng["id"]])

        # Пропускаем текущего мастера заявки
        if uuid_eid == current_engineer_id:
            continue

        if skill_needed not in eng["skills"]:
            continue

        eng_orders = orders_by_eng.get(uuid_eid, [])
        existing_tasks, _ = _make_tasks_from_db(eng_orders, day)
        existing_tasks.sort(key=lambda t: (t["start"], t["end"]))

        init_time, init_loc = (eng["shift_start"], office_loc)
        ev_before = algo.evaluate_route(
            eng, existing_tasks, office_loc,
            start_time=init_time, start_loc=init_loc,
            equipment_full_route=existing_tasks,
        )
        cost_before = (
            algo.route_cost(ev_before) if ev_before.get("feasible") else 0.0
        )

        best_pos = None
        best_ev  = None
        best_cost = None

        eng_db = next(
            (e for e in engineers_db if e.id == eng_id_map[eng["id"]]), None
        )
        if eng_db is None:
            continue

        for pos in range(len(existing_tasks) + 1):
            cand = existing_tasks[:pos] + [new_task] + existing_tasks[pos:]

            if algo._light_transport_over_limit(eng, cand):
                continue
            needed = algo.route_equipment_needed(cand)
            if eng["transport"] == "автомобиль":
                needed["router"] += algo.EQUIPMENT_BUFFER
                needed["stb"]    += algo.EQUIPMENT_BUFFER
            if not _equipment_available(eng_db, needed):
                continue

            ev = algo.evaluate_route(
                eng, cand, office_loc,
                start_time=init_time, start_loc=init_loc,
                equipment_full_route=cand,
            )
            if not ev.get("feasible", True):
                continue

            c = algo.route_cost(ev)
            if best_cost is None or c < best_cost:
                best_cost = c
                best_pos  = pos
                best_ev   = ev

        if best_pos is None:
            continue

        is_free = (len(existing_tasks) == 0)
        has_wait_window = False
        wait_window_str = None

        travel_min = None
        if best_ev is not None:
            travel_min = int(round(best_ev["schedule"][best_pos]["travel_min"]))

        shifts: list[dict] = []
        if best_ev is not None and ev_before.get("feasible") and not is_free:
            orig_sched = ev_before["schedule"]
            new_sched  = best_ev["schedule"]
            for i, orig_item in enumerate(orig_sched):
                if i < best_pos:
                    continue
                new_item = new_sched[i + 1]
                delta = (new_item["start"] - orig_item["start"]).total_seconds() / 60.0
                if abs(delta) >= 1:
                    shifts.append({
                        "id":         orig_item["task"]["id"],
                        "old_start":  orig_item["start"].strftime("%H:%M"),
                        "old_end":    orig_item["end"].strftime("%H:%M"),
                        "new_start":  new_item["start"].strftime("%H:%M"),
                        "new_end":    new_item["end"].strftime("%H:%M"),
                        "delta_min":  int(round(delta)),
                    })

        if not is_free and best_ev is not None:
            schedule = best_ev["schedule"]
            idx_in = best_pos
            prev_end = (
                schedule[idx_in - 1]["end"] if idx_in > 0 else eng["shift_start"]
            )
            next_start = (
                schedule[idx_in + 1]["start"]
                if idx_in + 1 < len(schedule) else eng["shift_end"]
            )
            inserted_start = schedule[idx_in]["start"]
            inserted_end   = schedule[idx_in]["end"]

            gap_before = (inserted_start - prev_end).total_seconds() / 60.0
            gap_after  = (next_start - inserted_end).total_seconds() / 60.0

            parts = []
            if gap_before >= 15:
                parts.append(f"{int(gap_before)} мин до")
            if gap_after >= 15:
                parts.append(f"{int(gap_after)} мин после")
            if parts:
                has_wait_window = True
                wait_window_str = " · ".join(parts)

        added_cost = (
            best_cost - cost_before
            if math.isfinite(cost_before) and cost_before > 0
            else best_cost
        )

        between_before = None
        between_after = None
        if existing_tasks and best_pos > 0:
            t_before = existing_tasks[best_pos - 1]
            between_before = {
                "id": t_before["id"],
                "end": t_before["end"].strftime("%H:%M"),
            }
        if best_pos < len(existing_tasks):
            t_after = existing_tasks[best_pos]
            between_after = {
                "id": t_after["id"],
                "start": t_after["start"].strftime("%H:%M"),
            }

        suitable.append({
            "engineer": {
                "id":          uuid_eid,
                "name":        eng["name"],
                "transport":   eng["transport"],
                "shift_start": eng["shift_start"].strftime("%H:%M"),
                "shift_end":   eng["shift_end"].strftime("%H:%M"),
                "skills":      sorted(eng["skills"]),
            },
            "current_load":    len(existing_tasks),
            "insert_at":       best_pos + 1,
            "is_free":         is_free,
            "has_wait_window": has_wait_window,
            "wait_window":     wait_window_str,
            "between_before":  between_before,
            "between_after":   between_after,
            "added_cost":      round(float(added_cost), 1),
            "schedule_end":    best_ev["end_day"].strftime("%H:%M"),
            "total_km":        round(float(best_ev["total_km"]), 1),
            "travel_min":      travel_min,
            "shifts":          shifts,
            "is_current":      False,
        })

    def _sort_key(item):
        free = 0 if item["is_free"] else 1
        wait = 0 if item["has_wait_window"] else 1
        return (free, wait, item["added_cost"])

    suitable.sort(key=_sort_key)

    return {
        "ok": True,
        "order": {
            "id":                  str(order.id),
            "external_id":         order.external_id,
            "address":             order.address or "",
            "bk_type":             TYPE_TO_BK.get(order.bk_type, ""),
            "window": (
                f"{order.window_start.strftime('%H:%M')}–"
                f"{order.window_end.strftime('%H:%M')}"
                if order.window_start and order.window_end else ""
            ),
            "current_engineer_id": current_engineer_id,
            "skill_needed":        skill_needed,
        },
        "suitable": suitable,
    }


# ============================================================
#  Последние сгенерированные карты
# ============================================================

def latest_engineer_map(district_id, engineer_id):
    district_dir = MAPS_DIR / str(district_id)
    if not district_dir.exists():
        return None
    matches = sorted(
        district_dir.glob(f"engineer_{engineer_id}_*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        return None
    return f"/static/maps/{district_id}/{matches[0].name}"


def latest_common_map(district_id):
    district_dir = MAPS_DIR / str(district_id)
    if not district_dir.exists():
        return None
    matches = sorted(
        district_dir.glob("all_*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        return None
    return f"/static/maps/{district_id}/{matches[0].name}"