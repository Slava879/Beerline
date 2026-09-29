# backend/app/services/status_auto.py
"""
Автообновление статусов заявок по времени.

Правила:
  * now >= planned.taken       → TAKEN       + departed_at = planned.taken
  * now >= planned.in_progress → IN_PROGRESS + started_at  = planned.in_progress
  * now >= planned.done        → DONE        + finished_at = planned.done

Никогда не откатывает назад, не трогает CANCELLED.
Если время уже проставлено (диспетчер кликнул вручную) — не перезаписывает.
Если диспетчер кликает вручную — set_status перезаписывает время на now.

Вызывается из /dashboard, /distribute, /maps/rebuild и раз в 60 секунд
с фронта через перезапрос /dashboard.
"""
from __future__ import annotations

from datetime import datetime, date as date_type, timedelta

from sqlalchemy import select

from backend.app.orders.models import Order, RequestStatus


TOL_TAKEN = timedelta(minutes=0)
TOL_START = timedelta(minutes=0)
TOL_DONE  = timedelta(minutes=0)

_ORDER_IDX = {
    RequestStatus.NEW:         0,
    RequestStatus.TAKEN:       1,
    RequestStatus.IN_PROGRESS: 2,
    RequestStatus.DONE:        3,
    RequestStatus.CANCELLED:   9,
}


def _parse_hhmm(s):
    if not s or not isinstance(s, str) or ":" not in s:
        return None
    try:
        h, m = s.split(":")[:2]
        return int(h), int(m)
    except Exception:
        return None


def _planned_dt(day: date_type, hhmm):
    parsed = _parse_hhmm(hhmm)
    if not parsed:
        return None
    h, m = parsed
    return datetime.combine(day, datetime.min.time()).replace(hour=h, minute=m)


async def auto_update_statuses(db, district_id=None, day: date_type | None = None) -> int:
    """
    Проходит по заявкам с заполненным extra["planned"] и двигает статусы вперёд,
    а также проставляет плановые времена в колонки, если они ещё пустые.
    Возвращает число изменённых заявок.
    """
    now = datetime.now()
    today = day or now.date()

    stmt = select(Order).where(
        Order.status.notin_([RequestStatus.DONE, RequestStatus.CANCELLED]),
        Order.extra.isnot(None),
    )
    if district_id:
        stmt = stmt.where(Order.district_id == district_id)
    if day:
        stmt = stmt.where(Order.visit_date == day)

    orders = (await db.execute(stmt)).scalars().all()
    changed = 0

    for o in orders:
        extra = o.extra if isinstance(o.extra, dict) else {}
        planned = extra.get("planned") if isinstance(extra.get("planned"), dict) else {}
        if not planned:
            continue

        order_day = o.visit_date or today
        if order_day > today:
            continue

        dt_taken = _planned_dt(order_day, planned.get("taken"))
        dt_start = _planned_dt(order_day, planned.get("in_progress"))
        dt_done  = _planned_dt(order_day, planned.get("done"))

        target: RequestStatus | None = None
        time_field: str | None = None
        target_time: datetime | None = None

        if dt_done and now >= dt_done + TOL_DONE:
            target, time_field, target_time = RequestStatus.DONE, "finished_at", dt_done
        elif dt_start and now >= dt_start + TOL_START:
            target, time_field, target_time = RequestStatus.IN_PROGRESS, "started_at", dt_start
        elif dt_taken and now >= dt_taken + TOL_TAKEN:
            target, time_field, target_time = RequestStatus.TAKEN, "departed_at", dt_taken

        if not target:
            continue
        if _ORDER_IDX.get(target, 0) <= _ORDER_IDX.get(o.status, 0):
            continue

        # Плановое время пишем, только если поле пустое
        # (не перетираем ручной ввод диспетчера)
        if time_field and target_time is not None:
            if getattr(o, time_field) is None:
                setattr(o, time_field, target_time)

        o.status = target
        changed += 1

    if changed:
        await db.commit()

    return changed