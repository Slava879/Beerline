# backend/app/services/algorithm.py
"""
Ядро алгоритма распределения заявок.
Данные приходят из routing.py.

Правило по времени:
  * мастер ДОЛЖЕН УСПЕТЬ ПРИЕХАТЬ в окно заявки (arrival ≤ task.end);
  * если работа заканчивается позже окна — это штраф, а не запрет;
  * смена мастера — жёсткое ограничение (end_day ≤ shift_end).
"""
import json
import math
import random
from datetime import datetime, timedelta

import requests


# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

MAPBOX_TOKEN = (
    "pk.eyJ1Ijoic2xhdmE4NzkiLCJhIjoiY211NGlzaHNsMGllMDJ5c2ZoMmhsODkwYiJ9."
    "pVhaQb2qdf0k6Y4iiWv6vg"
)
MAPBOX_DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox"
MAPBOX_MAX_COORDS = 200

TRANSPORT_TO_MAPBOX_PROFILE = {
    "пешеход":    "walking",
    "велосипед":  "cycling",
    "автомобиль": "driving",
}

NORMS = {
    "Подключение":         {"name": "Подключение клиентов Базовая",
                            "road": 20, "tech": 60, "docs": 10, "base": 90},
    "Глобальная проблема": {"name": "Аварий на ТКД",
                            "road": 20, "tech": 80, "docs": 0,  "base": 100},
    "Дозаказ":             {"name": "Дозаказ оборудования",
                            "road": 20, "tech": 10, "docs": 10, "base": 40},
    "Локальная заявка":    {"name": "Локальная заявка/ремонт у клиента",
                            "road": 20, "tech": 30, "docs": 0,  "base": 50},
}
DEFAULT_NORM = NORMS["Локальная заявка"]

PRIORITY = {
    "Глобальная проблема": 0,
    "Подключение":         1,
    "Дозаказ":             2,
    "Локальная заявка":    2,
}

TASK_SKILL = {
    "Подключение":         "подключение",
    "Глобальная проблема": "глобальные проблемы",
    "Дозаказ":             "дозаказ",
    "Локальная заявка":    "локальные работы",
}

TASK_EQUIPMENT = {
    "Подключение":         {"router": 1, "stb": 1},
    "Дозаказ":             {"router": 1, "stb": 0},
    "Глобальная проблема": {"router": 0, "stb": 0},
    "Локальная заявка":    {"router": 0, "stb": 0},
}

TRANSPORT_SPEED_KMH = {"пешеход": 10.0, "велосипед": 10.0, "автомобиль": 20.0}

NEW_ENGINEER_PENALTY = 3000.0
WAIT_COST_PER_MIN    = 0.5

LATE_PENALTY_PER_MIN         = 60.0
OVERTIME_PENALTY_PER_MIN     = 15.0
LONG_TRAVEL_PENALTY_PER_MIN  = 300.0
MAX_TRAVEL_MIN               = 20

URGENT_EARLINESS_PENALTY_PER_MIN = 50.0

EQUIPMENT_MISMATCH_PENALTY   = 300.0
EQUIPMENT_MATCH_BONUS        = 30.0

WINDOW_LATE_TOLERANCE_MIN    = 0
SHIFT_OVERTIME_TOLERANCE_MIN = 0

ALNS_ITERATIONS          = 60
ALNS_NO_IMPROVE_LIMIT    = 25
ALNS_DESTROY_MIN_RATIO   = 0.15
ALNS_DESTROY_MAX_RATIO   = 0.5
ALNS_TEMPERATURE_RATIO   = 0.10
ALNS_TEMPERATURE_FLOOR   = 200.0
ALNS_COOLING             = 0.98
ALNS_SEED                = 42
ALNS_RHO                 = 0.2
ALNS_SIGMA1              = 10
ALNS_SIGMA2              = 5
ALNS_SIGMA3              = 2
ALNS_SIGMA4              = 0
ALNS_WEIGHT_UPDATE_PERIOD = 5

KOEF_ROAD = 1.4

EQUIPMENT_BUFFER = 2
LIGHT_TRANSPORT_MAX_EQUIPMENT = 3

COLOR_PLANNED    = "#4363d8"
COLOR_IN_TRANSIT = "#f58231"
COLOR_DONE       = "#3cb44b"
COLOR_RETURN     = "#888888"
COLOR_OFFICE     = "#111111"

STATUS_RU = {
    "planned":     "запланирована",
    "en_route":    "мастер в пути",
    "arrived":     "мастер на месте (ожидание)",
    "in_progress": "в работе",
    "completed":   "выполнена",
    "cancelled":   "отменена",
}

LOCKED_STATUSES = {"en_route", "arrived", "in_progress", "completed"}


# =============================================================================
# ДИСТАНЦИИ
# =============================================================================

_travel_cache = {}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def travel_minutes(loc1, loc2, speed_kmh):
    key = (round(loc1[0], 6), round(loc1[1], 6),
           round(loc2[0], 6), round(loc2[1], 6))
    km = _travel_cache.get(key)
    if km is None:
        km = haversine_km(loc1[0], loc1[1], loc2[0], loc2[1]) * KOEF_ROAD
        _travel_cache[key] = km
    return km / speed_kmh * 60.0, km


def effective_travel_min(travel_min):
    return max(MAX_TRAVEL_MIN, travel_min)


# =============================================================================
# ОБОРУДОВАНИЕ
# =============================================================================

def route_equipment_needed(tasks):
    needed = {"router": 0, "stb": 0}
    for t in tasks:
        eq = TASK_EQUIPMENT.get(t["bk"], {"router": 0, "stb": 0})
        needed["router"] += eq["router"]
        needed["stb"]    += eq["stb"]
    return needed


def route_equipment_total(tasks):
    total = 0
    for t in tasks:
        eq = TASK_EQUIPMENT.get(t["bk"], {"router": 0, "stb": 0})
        total += eq.get("router", 0) + eq.get("stb", 0)
    return total


def _light_transport_over_limit(eng, full_route):
    if eng["transport"] not in ("пешеход", "велосипед"):
        return False
    return route_equipment_total(full_route) > LIGHT_TRANSPORT_MAX_EQUIPMENT


def check_equipment(eng, full_route):
    needed = route_equipment_needed(full_route)
    alloc = eng.get("equipment_allocated", {"router": 0, "stb": 0})
    if alloc["router"] < needed["router"] or alloc["stb"] < needed["stb"]:
        return False
    if eng["transport"] in ("пешеход", "велосипед"):
        if needed["router"] + needed["stb"] > LIGHT_TRANSPORT_MAX_EQUIPMENT:
            return False
    return True


def allocate_equipment(routes, engineers):
    eng_by_id = {e["id"]: e for e in engineers}
    for e in engineers:
        e["equipment_allocated"] = {"router": 0, "stb": 0}
    for eid, route in routes.items():
        eng = eng_by_id.get(eid)
        if eng is None:
            continue
        needed = route_equipment_needed(route)
        if eng["transport"] == "автомобиль":
            eng["equipment_allocated"]["router"] = needed["router"] + EQUIPMENT_BUFFER
            eng["equipment_allocated"]["stb"]    = needed["stb"]    + EQUIPMENT_BUFFER
        else:
            eng["equipment_allocated"]["router"] = needed["router"]
            eng["equipment_allocated"]["stb"]    = needed["stb"]


def transport_equipment_bonus(task, eng):
    eq = TASK_EQUIPMENT.get(task["bk"], {"router": 0, "stb": 0})
    needs_eq = (eq["router"] + eq["stb"]) > 0
    is_light = eng["transport"] in ("пешеход", "велосипед")
    if is_light:
        return EQUIPMENT_MISMATCH_PENALTY if needs_eq else -EQUIPMENT_MATCH_BONUS
    return 0.0


# =============================================================================
# ОЦЕНКА МАРШРУТА
# =============================================================================

def evaluate_route(engineer, tasks, office_loc,
                   start_time=None, start_loc=None,
                   equipment_full_route=None):
    """
    `tasks` — суффикс маршрута (то, что мы реально проверяем по времени).
    `equipment_full_route` — полный маршрут (prefix + suffix), нужен
    для проверки лимита оборудования у пешеходов/велосипедистов.

    Жёсткие ограничения:
      * нельзя начать раньше смены мастера;
      * мастер должен прибыть в окно заявки (arrival <= task.end);
      * работа мастера и возврат должны уложиться в смену.

    Штрафы (без запрета):
      * если работа заканчивается позже task.end;
      * если конец дня позже shift_end (при shift_tol > 0);
      * долгая дорога между точками;
      * переработка.
    """
    t = start_time if start_time is not None else engineer["shift_start"]
    loc = start_loc if start_loc is not None else office_loc
    schedule = []
    total_km = 0.0
    total_wait = 0.0
    penalty = 0.0
    feasible = True

    win_tol   = timedelta(minutes=WINDOW_LATE_TOLERANCE_MIN)
    shift_tol = timedelta(minutes=SHIFT_OVERTIME_TOLERANCE_MIN)

    for task in tasks:
        travel_min, leg_km = travel_minutes(loc, (task["lat"], task["lon"]),
                                            engineer["speed_kmh"])
        total_km += leg_km
        if travel_min > MAX_TRAVEL_MIN:
            penalty += ((travel_min / MAX_TRAVEL_MIN) ** 3) * LONG_TRAVEL_PENALTY_PER_MIN

        arrival = t + timedelta(minutes=effective_travel_min(travel_min))
        start = max(arrival, task["start"])
        wait = (start - arrival).total_seconds() / 60.0
        total_wait += wait
        end = start + timedelta(minutes=task["service"])

        # ── Жёсткие ограничения ──
        # 1. Нельзя начать до смены мастера
        if start < engineer["shift_start"]:
            feasible = False

        # 2. Мастер ДОЛЖЕН УСПЕТЬ ПРИЕХАТЬ в окно заявки:
        #    прибытие не позже окончания окна (+допуск)
        if arrival > task["end"]:
            feasible = False

        # 3. Смена мастера — жёстко
        if end > engineer["shift_end"] + shift_tol:
            feasible = False

        # ── Штрафы ──
        # Работа может закончиться позже окна клиента — это штраф, не запрет.
        if end > task["end"]:
            penalty += ((end - task["end"]).total_seconds() / 60.0) * LATE_PENALTY_PER_MIN

        # Переработка смены — тоже штраф (на случай shift_tol > 0)
        if end > engineer["shift_end"]:
            penalty += ((end - engineer["shift_end"]).total_seconds() / 60.0) * OVERTIME_PENALTY_PER_MIN

        schedule.append({
            "task":       task,
            "travel_min": travel_min,
            "leg_km":     leg_km,
            "arrival":    arrival,
            "start":      start,
            "end":        end,
            "wait_min":   wait,
        })
        t = end
        loc = (task["lat"], task["lon"])

    back_min, back_km = travel_minutes(loc, office_loc, engineer["speed_kmh"])
    total_km += back_km
    end_day = t + timedelta(minutes=back_min)

    if end_day > engineer["shift_end"] + shift_tol:
        feasible = False
        penalty += ((end_day - engineer["shift_end"]).total_seconds() / 60.0) * OVERTIME_PENALTY_PER_MIN

    eq_route = equipment_full_route if equipment_full_route is not None else tasks
    if _light_transport_over_limit(engineer, eq_route):
        feasible = False

    return {
        "schedule":   schedule,
        "end_day":    end_day,
        "total_km":   total_km,
        "total_wait": total_wait,
        "return_min": back_min,
        "penalty":    penalty,
        "feasible":   feasible,
    }


def route_cost(ev, is_new_route=False):
    if not ev.get("feasible", True):
        return float("inf")
    c = ev["total_km"] + WAIT_COST_PER_MIN * ev["total_wait"] + ev["penalty"]
    if is_new_route:
        c += NEW_ENGINEER_PENALTY
    return c


def urgent_penalty(ev, task):
    if not task.get("is_urgent"):
        return 0.0
    ref = task.get("urgent_ref_time")
    if ref is None:
        return 0.0
    tid = task.get("id")
    for item in ev["schedule"]:
        if item["task"].get("id") == tid:
            delta = (item["start"] - ref).total_seconds() / 60.0
            if delta > 0:
                return delta * URGENT_EARLINESS_PENALTY_PER_MIN
            return 0.0
    return 0.0


def default_master_state(engineers, office_loc, now=None):
    st = {}
    for e in engineers:
        start = e["shift_start"]
        if now is not None and now > start:
            start = now
        st[e["id"]] = (start, office_loc)
    return st


def update_task_statuses(routes, engineers, office_loc, now):
    eng_by_id = {e["id"]: e for e in engineers}
    for eid, route in routes.items():
        if not route:
            continue
        eng = eng_by_id[eid]
        ev = evaluate_route(eng, route, office_loc,
                            equipment_full_route=route)
        for item in ev["schedule"]:
            task = item["task"]
            departure = item["arrival"] - timedelta(
                minutes=effective_travel_min(item["travel_min"]))
            if now >= item["end"]:
                task["status"] = "completed"
            elif now >= item["start"]:
                task["status"] = "in_progress"
            elif now >= item["arrival"]:
                task["status"] = "arrived"
            elif now >= departure:
                task["status"] = "en_route"
            else:
                task["status"] = "planned"


def split_locked_and_pending(routes, engineers, office_loc, now):
    prefixes = {}
    pending = []
    master_state = {}

    for eng in engineers:
        eid = eng["id"]
        route = routes.get(eid, [])
        if not route:
            prefixes[eid] = []
            start = eng["shift_start"] if now <= eng["shift_start"] else now
            master_state[eid] = (start, office_loc)
            continue

        ev = evaluate_route(eng, route, office_loc,
                            equipment_full_route=route)
        locked_count = 0
        for item in ev["schedule"]:
            if item["task"].get("status", "planned") in LOCKED_STATUSES:
                locked_count += 1
            else:
                break

        if locked_count == 0:
            prefixes[eid] = []
            start = eng["shift_start"] if now <= eng["shift_start"] else now
            master_state[eid] = (start, office_loc)
            for item in ev["schedule"]:
                pending.append(item["task"])
        else:
            locked_items = ev["schedule"][:locked_count]
            prefixes[eid] = [it["task"] for it in locked_items]
            last = locked_items[-1]
            start = max(last["end"], now)
            master_state[eid] = (start, (last["task"]["lat"], last["task"]["lon"]))
            for item in ev["schedule"][locked_count:]:
                pending.append(item["task"])

    return prefixes, pending, master_state


# =============================================================================
# ОБЩАЯ ОЦЕНКА
# =============================================================================

def route_score(eid, route, eng_by_id, prefixes, master_state, office_loc):
    prefix_len = len(prefixes.get(eid, []))
    suffix = route[prefix_len:]
    if not suffix:
        return 0.0
    init_time, init_loc = master_state[eid]
    eng = eng_by_id.get(eid)
    if eng is None:
        return 0.0

    ev = evaluate_route(eng, suffix, office_loc, init_time, init_loc,
                        equipment_full_route=route)
    if not ev.get("feasible", True):
        return float("inf")
    c = route_cost(ev)
    for t in suffix:
        c += transport_equipment_bonus(t, eng)
        c += urgent_penalty(ev, t)
    if prefix_len == 0:
        c += NEW_ENGINEER_PENALTY
    return c


def solution_cost(routes, engineers, office_loc, prefixes, master_state):
    eng_by_id = {e["id"]: e for e in engineers if e.get("is_active", True)}
    total = 0.0
    for eid, route in routes.items():
        c = route_score(eid, route, eng_by_id, prefixes,
                        master_state, office_loc)
        if not math.isfinite(c):
            return float("inf")
        total += c
    return total


# =============================================================================
# REORDER ДЛЯ СРОЧНОЙ
# =============================================================================

def _reorder_for_urgent(eid, routes, engineers, office_loc,
                        prefixes, master_state, urgent_task, max_iter=40):
    eng = next((e for e in engineers if e["id"] == eid), None)
    if eng is None:
        return
    route = routes.get(eid, [])
    if urgent_task not in route:
        return

    prefix_len = len(prefixes.get(eid, []))
    init_time, init_loc = master_state[eid]
    prefix = route[:prefix_len]
    suffix = list(route[prefix_len:])
    if len(suffix) < 2:
        return

    def evaluate(suf):
        ev = evaluate_route(eng, suf, office_loc, init_time, init_loc,
                            equipment_full_route=prefix + suf)
        base = route_cost(ev)
        if not math.isfinite(base):
            return float("inf")
        return urgent_penalty(ev, urgent_task) * 1000.0 + base

    best_suffix = suffix
    best_score = evaluate(best_suffix)
    it = 0
    improved = True
    while improved and it < max_iter:
        improved = False
        it += 1
        n = len(best_suffix)

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                cand = best_suffix[:]
                item = cand.pop(i)
                cand.insert(j, item)
                sc = evaluate(cand)
                if sc < best_score - 1e-6:
                    best_score = sc
                    best_suffix = cand
                    improved = True
                    break
            if improved:
                break
        if improved:
            continue

        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = (best_suffix[:i]
                        + list(reversed(best_suffix[i:j + 1]))
                        + best_suffix[j + 1:])
                sc = evaluate(cand)
                if sc < best_score - 1e-6:
                    best_score = sc
                    best_suffix = cand
                    improved = True
                    break
            if improved:
                break

    routes[eid] = prefix + best_suffix


# =============================================================================
# REGRET-INSERTION
# =============================================================================

def regret_insert(pending, engineers, office_loc, prefixes=None,
                  master_state=None, check_eq=False, routes_init=None,
                  now=None):
    active = [e for e in engineers if e.get("is_active", True)]

    if prefixes is None:
        prefixes = {e["id"]: [] for e in active}
    if master_state is None:
        master_state = default_master_state(active, office_loc, now)

    if routes_init is not None:
        routes = {eid: list(r) for eid, r in routes_init.items()}
    else:
        routes = {eid: list(prefixes[eid]) for eid in prefixes}
    for e in active:
        routes.setdefault(e["id"], list(prefixes.get(e["id"], [])))

    while pending:
        best_task = None
        best_rank = -float("inf")
        best_choice = None

        for task in pending:
            skill = TASK_SKILL.get(task["bk"])
            if not skill:
                continue
            is_urgent = task.get("is_urgent", False)
            candidates = []
            for eng in active:
                if skill not in eng["skills"]:
                    continue
                route = routes[eng["id"]]
                prefix_len = len(prefixes.get(eng["id"], []))
                init_time, init_loc = master_state[eng["id"]]
                is_new = (len(route) == 0)

                for pos in range(prefix_len, len(route) + 1):
                    cand = route[:pos] + [task] + route[pos:]

                    if _light_transport_over_limit(eng, cand):
                        continue
                    if check_eq and not check_equipment(eng, cand):
                        continue

                    suffix = cand[prefix_len:]
                    ev = evaluate_route(eng, suffix, office_loc,
                                        init_time, init_loc,
                                        equipment_full_route=cand)
                    base = route_cost(ev, is_new_route=is_new)
                    if not math.isfinite(base):
                        continue
                    cost = base + transport_equipment_bonus(task, eng)
                    cost += urgent_penalty(ev, task)
                    candidates.append((cost, eng["id"], pos))
            if not candidates:
                continue
            candidates.sort(key=lambda x: x[0])
            best_c = candidates[0][0]
            regret = 1e9 if len(candidates) == 1 else (candidates[1][0] - best_c)
            rank = regret
            if is_urgent:
                rank += 1e9
            if rank > best_rank:
                best_rank = rank
                best_task = task
                best_choice = candidates[0]

        if best_task is None:
            break
        _, eid, pos = best_choice
        routes[eid] = routes[eid][:pos] + [best_task] + routes[eid][pos:]

        if best_task.get("is_urgent"):
            _reorder_for_urgent(eid, routes, engineers, office_loc,
                                prefixes, master_state, best_task)

        pending.remove(best_task)

    return routes


def force_assign_remaining(pending, routes, engineers, office_loc,
                           prefixes=None, master_state=None,
                           check_eq=False, now=None):
    if not pending:
        return
    active = [e for e in engineers if e.get("is_active", True)]
    if prefixes is None:
        prefixes = {eid: [] for eid in routes}
    if master_state is None:
        master_state = default_master_state(active, office_loc, now)

    for task in list(pending):
        skill = TASK_SKILL.get(task["bk"])
        if not skill:
            continue
        is_urgent = task.get("is_urgent", False)
        best = None

        for eng in active:
            if skill not in eng["skills"]:
                continue
            route = routes.get(eng["id"], [])
            prefix_len = len(prefixes.get(eng["id"], []))
            init_time, init_loc = master_state[eng["id"]]
            is_new = (len(route) == 0)

            for pos in range(prefix_len, len(route) + 1):
                cand = route[:pos] + [task] + route[pos:]

                if _light_transport_over_limit(eng, cand):
                    continue
                if check_eq and not check_equipment(eng, cand):
                    continue

                suffix = cand[prefix_len:]
                ev = evaluate_route(eng, suffix, office_loc,
                                    init_time, init_loc,
                                    equipment_full_route=cand)
                base = route_cost(ev, is_new_route=is_new)
                if not math.isfinite(base):
                    continue
                c = base + transport_equipment_bonus(task, eng)
                c += urgent_penalty(ev, task)

                if best is None or c < best[0]:
                    best = (c, eng["id"], cand)

        if best is not None:
            _, eid, new_route = best
            routes[eid] = new_route
            if is_urgent:
                _reorder_for_urgent(eid, routes, engineers, office_loc,
                                    prefixes, master_state, task)
            pending.remove(task)


# =============================================================================
# ЛОКАЛЬНЫЙ ПОИСК
# =============================================================================

def _swap_between_routes(routes, eng_by_id, prefixes, cost_fn, check_eq=False):
    eids = list(routes.keys())
    for a_idx in range(len(eids)):
        for b_idx in range(a_idx + 1, len(eids)):
            a_id, b_id = eids[a_idx], eids[b_idx]
            a_route = routes[a_id]
            b_route = routes[b_id]
            a_prefix_len = len(prefixes.get(a_id, []))
            b_prefix_len = len(prefixes.get(b_id, []))
            a_suffix = a_route[a_prefix_len:]
            b_suffix = b_route[b_prefix_len:]
            if not a_suffix or not b_suffix:
                continue
            old_total = cost_fn(a_id, a_route) + cost_fn(b_id, b_route)
            if not math.isfinite(old_total):
                continue
            best = None
            for ai, ta in enumerate(a_suffix):
                skill_a = TASK_SKILL.get(ta["bk"])
                if not skill_a:
                    continue
                for bi, tb in enumerate(b_suffix):
                    skill_b = TASK_SKILL.get(tb["bk"])
                    if not skill_b:
                        continue
                    eng_a = eng_by_id[a_id]
                    eng_b = eng_by_id[b_id]
                    if skill_b not in eng_a["skills"]:
                        continue
                    if skill_a not in eng_b["skills"]:
                        continue
                    new_a = a_suffix[:ai] + [tb] + a_suffix[ai + 1:]
                    new_b = b_suffix[:bi] + [ta] + b_suffix[bi + 1:]

                    full_a = list(prefixes.get(a_id, [])) + new_a
                    full_b = list(prefixes.get(b_id, [])) + new_b

                    if _light_transport_over_limit(eng_a, full_a):
                        continue
                    if _light_transport_over_limit(eng_b, full_b):
                        continue
                    if check_eq:
                        if not check_equipment(eng_a, full_a):
                            continue
                        if not check_equipment(eng_b, full_b):
                            continue

                    new_total = (cost_fn(a_id, a_route[:a_prefix_len] + new_a)
                                 + cost_fn(b_id, b_route[:b_prefix_len] + new_b))
                    if not math.isfinite(new_total):
                        continue
                    if new_total < old_total - 1e-6 and (best is None
                                                         or new_total < best[0]):
                        best = (new_total, new_a, new_b)
            if best is not None:
                _, new_a, new_b = best
                routes[a_id] = a_route[:a_prefix_len] + new_a
                routes[b_id] = b_route[:b_prefix_len] + new_b
                return True
    return False


def local_search(routes, engineers, office_loc, prefixes=None,
                 master_state=None, max_iter=60, check_eq=False, now=None):
    eng_by_id = {e["id"]: e for e in engineers if e.get("is_active", True)}
    if prefixes is None:
        prefixes = {eid: [] for eid in routes}
    if master_state is None:
        master_state = default_master_state(list(eng_by_id.values()),
                                            office_loc, now)

    def score(eid, route):
        return route_score(eid, route, eng_by_id, prefixes,
                           master_state, office_loc)

    # --- 2-opt внутри маршрута ---
    for _ in range(max_iter):
        improved = False
        for eid in list(routes.keys()):
            route = routes[eid]
            prefix_len = len(prefixes.get(eid, []))
            suffix = route[prefix_len:]
            if len(suffix) < 2:
                continue
            best_cost = score(eid, route)
            best_suffix = suffix
            changed = False
            for i in range(len(suffix) - 1):
                for j in range(i + 1, len(suffix)):
                    cand = (suffix[:i] + list(reversed(suffix[i:j + 1]))
                            + suffix[j + 1:])
                    c = score(eid, route[:prefix_len] + cand)
                    if c < best_cost - 1e-6:
                        best_cost = c
                        best_suffix = cand
                        changed = True
            if changed:
                routes[eid] = route[:prefix_len] + best_suffix
                improved = True
        if not improved:
            break

    # --- Relocate ---
    for _ in range(max_iter):
        improved = False
        for src_id in list(routes.keys()):
            src_route = routes[src_id]
            src_prefix_len = len(prefixes.get(src_id, []))
            src_suffix = src_route[src_prefix_len:]
            if not src_suffix:
                continue
            for ti, task in enumerate(src_suffix):
                new_src_suffix = src_suffix[:ti] + src_suffix[ti + 1:]
                src_old_c = score(src_id, src_route)
                src_new_c = score(src_id,
                                  src_route[:src_prefix_len] + new_src_suffix)
                if not math.isfinite(src_old_c) or not math.isfinite(src_new_c):
                    continue
                d_src = src_new_c - src_old_c
                skill = TASK_SKILL.get(task["bk"])
                if not skill:
                    continue
                best = None
                for dst_id, dst_route in routes.items():
                    if dst_id == src_id:
                        continue
                    eng = eng_by_id.get(dst_id)
                    if not eng or skill not in eng["skills"]:
                        continue
                    dst_prefix_len = len(prefixes.get(dst_id, []))
                    dst_suffix = dst_route[dst_prefix_len:]
                    dst_old_c = score(dst_id, dst_route)
                    if not math.isfinite(dst_old_c):
                        continue
                    for pos in range(len(dst_suffix) + 1):
                        new_dst_suffix = (dst_suffix[:pos] + [task]
                                          + dst_suffix[pos:])
                        full_dst = (list(prefixes.get(dst_id, []))
                                    + new_dst_suffix)

                        if _light_transport_over_limit(eng, full_dst):
                            continue
                        if check_eq:
                            if not check_equipment(eng, full_dst):
                                continue

                        c = score(dst_id,
                                  dst_route[:dst_prefix_len] + new_dst_suffix)
                        if not math.isfinite(c):
                            continue
                        d_total = d_src + (c - dst_old_c)
                        if d_total < -1e-6 and (best is None
                                                or d_total < best[0]):
                            best = (d_total, dst_id,
                                    dst_prefix_len + pos, new_src_suffix)
                if best is not None:
                    _, dst_id, dst_pos_full, new_src_suffix = best
                    routes[src_id] = src_route[:src_prefix_len] + new_src_suffix
                    dst_route = routes[dst_id]
                    routes[dst_id] = (dst_route[:dst_pos_full]
                                      + [task] + dst_route[dst_pos_full:])
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break

    # --- Or-opt внутри маршрута ---
    for seg_len in (3, 2):
        for _ in range(max_iter):
            improved = False
            for eid in list(routes.keys()):
                route = routes[eid]
                prefix_len = len(prefixes.get(eid, []))
                suffix = route[prefix_len:]
                if len(suffix) < seg_len + 1:
                    continue
                best_cost = score(eid, route)
                best_suffix = suffix
                changed = False
                for i in range(len(suffix) - seg_len + 1):
                    segment = suffix[i:i + seg_len]
                    rest = suffix[:i] + suffix[i + seg_len:]
                    for j in range(len(rest) + 1):
                        if j == i:
                            continue
                        cand = rest[:j] + segment + rest[j:]
                        c = score(eid, route[:prefix_len] + cand)
                        if c < best_cost - 1e-6:
                            best_cost = c
                            best_suffix = cand
                            changed = True
                if changed:
                    routes[eid] = route[:prefix_len] + best_suffix
                    improved = True
            if not improved:
                break

    # --- Or-opt между маршрутами ---
    for seg_len in (3, 2):
        for _ in range(max_iter):
            improved = False
            for src_id in list(routes.keys()):
                src_route = routes[src_id]
                src_prefix_len = len(prefixes.get(src_id, []))
                src_suffix = src_route[src_prefix_len:]
                if len(src_suffix) < seg_len:
                    continue
                for si in range(len(src_suffix) - seg_len + 1):
                    segment = src_suffix[si:si + seg_len]
                    skills_needed = set()
                    for t in segment:
                        sk = TASK_SKILL.get(t["bk"])
                        if sk:
                            skills_needed.add(sk)
                    if not skills_needed:
                        continue
                    new_src_suffix = (src_suffix[:si]
                                      + src_suffix[si + seg_len:])
                    src_old_c = score(src_id, src_route)
                    src_new_c = score(src_id,
                                      src_route[:src_prefix_len]
                                      + new_src_suffix)
                    if (not math.isfinite(src_old_c)
                            or not math.isfinite(src_new_c)):
                        continue
                    d_src = src_new_c - src_old_c
                    best = None
                    for dst_id, dst_route in routes.items():
                        if dst_id == src_id:
                            continue
                        eng = eng_by_id.get(dst_id)
                        if (not eng
                                or not skills_needed.issubset(eng["skills"])):
                            continue
                        dst_prefix_len = len(prefixes.get(dst_id, []))
                        dst_suffix = dst_route[dst_prefix_len:]
                        dst_old_c = score(dst_id, dst_route)
                        if not math.isfinite(dst_old_c):
                            continue
                        for pos in range(len(dst_suffix) + 1):
                            new_dst_suffix = (dst_suffix[:pos] + segment
                                              + dst_suffix[pos:])
                            full_dst = (list(prefixes.get(dst_id, []))
                                        + new_dst_suffix)

                            if _light_transport_over_limit(eng, full_dst):
                                continue
                            if check_eq:
                                if not check_equipment(eng, full_dst):
                                    continue

                            c = score(dst_id,
                                      dst_route[:dst_prefix_len]
                                      + new_dst_suffix)
                            if not math.isfinite(c):
                                continue
                            d_total = d_src + (c - dst_old_c)
                            if d_total < -1e-6 and (best is None
                                                    or d_total < best[0]):
                                best = (d_total, dst_id,
                                        dst_prefix_len + pos, new_src_suffix)
                    if best is not None:
                        _, dst_id, dst_pos_full, new_src_suffix = best
                        routes[src_id] = (src_route[:src_prefix_len]
                                          + new_src_suffix)
                        dst_route = routes[dst_id]
                        routes[dst_id] = (dst_route[:dst_pos_full]
                                          + segment
                                          + dst_route[dst_pos_full:])
                        improved = True
                        break
                if improved:
                    break
            if not improved:
                break

    for _ in range(max_iter):
        if not _swap_between_routes(routes, eng_by_id, prefixes, score,
                                    check_eq=check_eq):
            break

    return {eid: r for eid, r in routes.items() if r}


# =============================================================================
# МИНИМИЗАЦИЯ МАСТЕРОВ
# =============================================================================

def minimize_engineers(routes, engineers, office_loc, prefixes=None,
                       master_state=None, max_passes=4, check_eq=False,
                       now=None):
    eng_by_id = {e["id"]: e for e in engineers if e.get("is_active", True)}
    if prefixes is None:
        prefixes = {eid: [] for eid in routes}
    if master_state is None:
        master_state = default_master_state(list(eng_by_id.values()),
                                            office_loc, now)

    def cost_of(eid, route):
        return route_score(eid, route, eng_by_id, prefixes,
                           master_state, office_loc)

    def total_cost(routes_dict):
        total = 0.0
        for eid, r in routes_dict.items():
            c = cost_of(eid, r)
            if not math.isfinite(c):
                return float("inf")
            total += c
        return total

    def _try_free_engineer(src_id, src_route, test_routes):
        for task in list(src_route):
            skill = TASK_SKILL.get(task["bk"])
            if not skill:
                return False, None
            best = None
            for dst_id, dst_route in test_routes.items():
                if dst_id == src_id:
                    continue
                eng = eng_by_id.get(dst_id)
                if not eng or skill not in eng["skills"]:
                    continue
                dst_prefix_len = len(prefixes.get(dst_id, []))
                dst_suffix = dst_route[dst_prefix_len:]
                init_time, init_loc = master_state[dst_id]
                for pos in range(len(dst_suffix) + 1):
                    new_suffix = dst_suffix[:pos] + [task] + dst_suffix[pos:]
                    full_dst = (list(prefixes.get(dst_id, [])) + new_suffix)

                    if _light_transport_over_limit(eng, full_dst):
                        continue
                    if check_eq and not check_equipment(eng, full_dst):
                        continue

                    ev = evaluate_route(eng, new_suffix, office_loc,
                                        init_time, init_loc,
                                        equipment_full_route=full_dst)
                    base = route_cost(ev)
                    if not math.isfinite(base):
                        continue
                    c = base + transport_equipment_bonus(task, eng)
                    c += urgent_penalty(ev, task)
                    if not math.isfinite(c):
                        continue
                    if best is None or c < best[0]:
                        best = (c, dst_id, new_suffix, dst_prefix_len)
            if best is None:
                return False, None
            _, dst_id, new_suffix, dst_prefix_len = best
            test_routes[dst_id] = (test_routes[dst_id][:dst_prefix_len]
                                   + new_suffix)
            test_routes[src_id] = [t for t in test_routes[src_id]
                                   if t is not task]
        if test_routes.get(src_id):
            return False, None
        return True, test_routes

    for _ in range(max_passes):
        candidates = [(eid, route) for eid, route in routes.items()
                      if route and not prefixes.get(eid)]
        candidates.sort(key=lambda x: len(x[1]))
        if not candidates:
            break

        changed = False
        for src_id, src_route in candidates:
            if not routes.get(src_id):
                continue
            test_routes = {eid: list(routes[eid]) for eid in routes}
            ok, new_routes = _try_free_engineer(src_id, src_route, test_routes)
            if ok:
                old_total = total_cost(routes)
                new_total = total_cost(new_routes)
                if (math.isfinite(new_total)
                        and new_total < old_total - 1e-6):
                    for eid in new_routes:
                        routes[eid] = new_routes[eid]
                    changed = True
                    break
        if changed:
            continue

        swap_freed = False
        for src_id, src_route in candidates:
            if not routes.get(src_id) or prefixes.get(src_id):
                continue
            eng_src = eng_by_id[src_id]

            for si, src_task in enumerate(src_route):
                skill_src = TASK_SKILL.get(src_task["bk"])
                if not skill_src:
                    continue
                src_without_task = [t for t in src_route if t is not src_task]
                best_swap = None

                for dst_id in routes:
                    if dst_id == src_id:
                        continue
                    eng_dst = eng_by_id.get(dst_id)
                    if eng_dst is None:
                        continue
                    dst_route = routes[dst_id]
                    dst_prefix_len = len(prefixes.get(dst_id, []))
                    dst_suffix = dst_route[dst_prefix_len:]
                    if not dst_suffix:
                        continue
                    for di, dst_task in enumerate(dst_suffix):
                        skill_dst = TASK_SKILL.get(dst_task["bk"])
                        if not skill_dst or skill_dst not in eng_src["skills"]:
                            continue
                        if skill_src not in eng_dst["skills"]:
                            continue
                        test_src = src_without_task + [dst_task]
                        test_dst = (dst_route[:dst_prefix_len + di]
                                    + [src_task] + dst_suffix[di + 1:])

                        full_src = (list(prefixes.get(src_id, []))
                                    + test_src)
                        full_dst = (list(prefixes.get(dst_id, []))
                                    + test_dst)

                        if _light_transport_over_limit(eng_src, full_src):
                            continue
                        if _light_transport_over_limit(eng_dst, full_dst):
                            continue
                        if check_eq and not check_equipment(eng_src, full_src):
                            continue
                        if check_eq and not check_equipment(eng_dst, full_dst):
                            continue

                        c_src = cost_of(src_id, test_src)
                        c_dst = cost_of(dst_id, test_dst)
                        c_old_src = cost_of(src_id, src_route)
                        c_old_dst = cost_of(dst_id, dst_route)
                        if not all(math.isfinite(x)
                                   for x in (c_src, c_dst,
                                             c_old_src, c_old_dst)):
                            continue
                        delta = (c_src + c_dst) - (c_old_src + c_old_dst)
                        if best_swap is None or delta < best_swap[0]:
                            best_swap = (delta, dst_id, di, dst_task)

                if best_swap is None:
                    continue
                _, dst_id, di, dst_task = best_swap
                test_src = src_without_task + [dst_task]
                dst_route = routes[dst_id]
                dst_prefix_len = len(prefixes.get(dst_id, []))
                dst_suffix = dst_route[dst_prefix_len:]
                test_dst = (dst_route[:dst_prefix_len + di]
                            + [src_task] + dst_suffix[di + 1:])

                redistrib = {eid: list(routes[eid]) for eid in routes}
                redistrib[src_id] = list(test_src)
                redistrib[dst_id] = list(test_dst)

                can_free, _ = _try_free_engineer(src_id, test_src, redistrib)
                if can_free and not redistrib.get(src_id):
                    old_total = total_cost(routes)
                    new_total = total_cost(redistrib)
                    if (math.isfinite(new_total)
                            and new_total < old_total - 1e-6):
                        for eid in redistrib:
                            routes[eid] = redistrib[eid]
                        swap_freed = True
                        break
            if swap_freed:
                break
        if swap_freed:
            continue

        eids = [e for e in routes if routes[e] and not prefixes.get(e)]
        sub_routes = {eid: routes[eid] for eid in eids}
        general_swap = _swap_between_routes(sub_routes, eng_by_id, prefixes,
                                            cost_of, check_eq=check_eq)
        if general_swap:
            routes.update(sub_routes)
        else:
            break

    return {eid: r for eid, r in routes.items() if r}


# =============================================================================
# ALNS
# =============================================================================

def _alns_destroy(routes, prefixes, n_remove, strategy, rng,
                  engineers, office_loc, master_state):
    removable = []
    for eid, route in routes.items():
        prefix_len = len(prefixes.get(eid, []))
        for idx in range(prefix_len, len(route)):
            removable.append((eid, idx, route[idx]))

    if not removable or n_remove <= 0:
        return {eid: list(r) for eid, r in routes.items()}, []

    n_remove = min(n_remove, len(removable))

    if strategy == "random":
        removed = rng.sample(removable, n_remove)

    elif strategy == "worst":
        eng_by_id = {e["id"]: e for e in engineers if e.get("is_active", True)}
        scored = []
        for eid, idx, t in removable:
            route = routes[eid]
            route_without = route[:idx] + route[idx + 1:]
            old_c = route_score(eid, route, eng_by_id, prefixes,
                                master_state, office_loc)
            new_c = route_score(eid, route_without, eng_by_id, prefixes,
                                master_state, office_loc)
            if math.isfinite(old_c) and math.isfinite(new_c):
                scored.append((old_c - new_c + rng.uniform(0, 0.5),
                               eid, idx, t))
            else:
                scored.append((0.0, eid, idx, t))
        scored.sort(reverse=True)
        removed = [(eid, idx, t) for _, eid, idx, t in scored[:n_remove]]

    elif strategy == "related":
        seed = rng.choice(removable)
        seed_t = seed[2]
        scored = []
        for eid, idx, t in removable:
            d = haversine_km(seed_t["lat"], seed_t["lon"], t["lat"], t["lon"])
            scored.append((d + rng.uniform(0, 0.5), eid, idx, t))
        scored.sort()
        removed = [(eid, idx, t) for _, eid, idx, t in scored[:n_remove]]

    elif strategy == "route":
        non_empty = [eid for eid, r in routes.items()
                     if len(r) > len(prefixes.get(eid, []))]
        if not non_empty:
            return {eid: list(r) for eid, r in routes.items()}, []
        target = rng.choice(non_empty)
        prefix_len = len(prefixes.get(target, []))
        pool = [(target, idx, t)
                for idx, t in enumerate(routes[target][prefix_len:], prefix_len)]
        removed = pool if len(pool) <= n_remove else rng.sample(pool, n_remove)

    elif strategy == "segment":
        non_empty = [eid for eid, r in routes.items()
                     if len(r) > len(prefixes.get(eid, []))]
        if not non_empty:
            return {eid: list(r) for eid, r in routes.items()}, []
        target = rng.choice(non_empty)
        prefix_len = len(prefixes.get(target, []))
        suffix_len = len(routes[target]) - prefix_len
        if suffix_len <= 0:
            return {eid: list(r) for eid, r in routes.items()}, []
        seg_len = min(suffix_len, max(1, n_remove))
        start = rng.randint(0, suffix_len - seg_len)
        removed = []
        for k in range(seg_len):
            idx = prefix_len + start + k
            removed.append((target, idx, routes[target][idx]))
    else:
        removed = rng.sample(removable, n_remove)

    new_routes = {eid: list(r) for eid, r in routes.items()}
    removed_tasks = []
    by_route = {}
    for eid, idx, t in removed:
        by_route.setdefault(eid, []).append((idx, t))
    for eid, items in by_route.items():
        items.sort(key=lambda x: x[0], reverse=True)
        for idx, t in items:
            new_routes[eid].pop(idx)
            removed_tasks.append(t)

    return new_routes, removed_tasks


def _alns_repair(routes, removed_tasks, prefixes, master_state,
                 engineers, office_loc, strategy, now=None):
    eng_by_id = {e["id"]: e for e in engineers if e.get("is_active", True)}

    result = {eid: list(r) for eid, r in routes.items()}
    for e in engineers:
        if e.get("is_active", True):
            result.setdefault(e["id"], [])

    pending = list(removed_tasks)
    pending.sort(key=lambda t: (0 if t.get("is_urgent") else 1,
                                t.get("priority", 9), t["end"]))

    while pending:
        best_task = None
        best_rank = -float("inf")
        best_choice = None

        for task in pending:
            skill = TASK_SKILL.get(task["bk"])
            if not skill:
                continue
            candidates = []
            for eng in eng_by_id.values():
                if skill not in eng["skills"]:
                    continue
                route = result.get(eng["id"], [])
                prefix_len = len(prefixes.get(eng["id"], []))
                init_time, init_loc = master_state[eng["id"]]
                is_new = (len(route) == 0)
                for pos in range(prefix_len, len(route) + 1):
                    cand = route[:pos] + [task] + route[pos:]

                    if _light_transport_over_limit(eng, cand):
                        continue
                    if not check_equipment(eng, cand):
                        continue

                    suffix = cand[prefix_len:]
                    ev = evaluate_route(eng, suffix, office_loc,
                                        init_time, init_loc,
                                        equipment_full_route=cand)
                    base = route_cost(ev, is_new_route=is_new)
                    if not math.isfinite(base):
                        continue
                    c = base + transport_equipment_bonus(task, eng)
                    c += urgent_penalty(ev, task)
                    candidates.append((c, eng["id"], pos))
            if not candidates:
                continue
            candidates.sort(key=lambda x: x[0])
            is_urgent = task.get("is_urgent", False)

            if strategy == "greedy":
                rank = -candidates[0][0]
            elif strategy == "regret2":
                rank = (1e9 if len(candidates) < 2
                        else candidates[1][0] - candidates[0][0])
            elif strategy == "regret3":
                if len(candidates) >= 3:
                    rank = ((candidates[1][0] - candidates[0][0])
                            + (candidates[2][0] - candidates[0][0]))
                elif len(candidates) == 2:
                    rank = candidates[1][0] - candidates[0][0]
                else:
                    rank = 1e9
            else:
                rank = -candidates[0][0]

            if is_urgent:
                rank += 1e9

            if rank > best_rank:
                best_rank = rank
                best_task = task
                best_choice = candidates[0]

        if best_task is None:
            break
        _, eid, pos = best_choice
        result[eid] = result[eid][:pos] + [best_task] + result[eid][pos:]

        if best_task.get("is_urgent"):
            _reorder_for_urgent(eid, result, engineers, office_loc,
                                prefixes, master_state, best_task)

        pending.remove(best_task)

    return result


def alns(routes, engineers, office_loc, prefixes, master_state,
         iterations=ALNS_ITERATIONS):
    eng_by_id = {e["id"]: e for e in engineers if e.get("is_active", True)}

    routes = {eid: list(r) for eid, r in routes.items()}
    for e in engineers:
        if e.get("is_active", True):
            routes.setdefault(e["id"], [])

    best = {eid: list(r) for eid, r in routes.items()}
    best_cost = solution_cost(best, engineers, office_loc,
                              prefixes, master_state)
    current = {eid: list(r) for eid, r in best.items()}
    current_cost = best_cost

    destroy_ops = ["random", "worst", "related", "route", "segment"]
    repair_ops  = ["regret2", "regret3", "greedy"]
    d_weights = {op: 1.0 for op in destroy_ops}
    r_weights = {op: 1.0 for op in repair_ops}
    d_scores  = {op: 0.0 for op in destroy_ops}
    r_scores  = {op: 0.0 for op in repair_ops}
    d_uses    = {op: 0 for op in destroy_ops}
    r_uses    = {op: 0 for op in repair_ops}

    rng = random.Random(ALNS_SEED)
    if math.isfinite(best_cost):
        temperature = max(best_cost * ALNS_TEMPERATURE_RATIO,
                          ALNS_TEMPERATURE_FLOOR)
    else:
        temperature = ALNS_TEMPERATURE_FLOOR
    no_improve = 0

    def roulette(weights):
        total = sum(weights.values())
        if total <= 0:
            return list(weights)[0]
        r = rng.random() * total
        acc = 0.0
        for k, w in weights.items():
            acc += w
            if r <= acc:
                return k
        return list(weights)[-1]

    for it in range(iterations):
        temp = max(temperature * (ALNS_COOLING ** it), 1.0)
        d_op = roulette(d_weights)
        r_op = roulette(r_weights)

        removable_count = sum(
            max(0, len(current[eid]) - len(prefixes.get(eid, [])))
            for eid in current
        )
        if removable_count == 0:
            break

        ratio = rng.uniform(ALNS_DESTROY_MIN_RATIO, ALNS_DESTROY_MAX_RATIO)
        n_remove = max(1, int(removable_count * ratio))

        destroyed, removed = _alns_destroy(
            current, prefixes, n_remove, d_op, rng,
            engineers, office_loc, master_state)
        if not removed:
            d_uses[d_op] += 1
            continue

        repaired = _alns_repair(
            destroyed, removed, prefixes, master_state,
            engineers, office_loc, r_op)

        cand_cost = solution_cost(repaired, engineers, office_loc,
                                  prefixes, master_state)
        if not math.isfinite(cand_cost):
            d_uses[d_op] += 1
            r_uses[r_op] += 1
            no_improve += 1
            continue

        score = ALNS_SIGMA4
        if cand_cost < best_cost - 1e-6:
            best = {eid: list(r) for eid, r in repaired.items()}
            best_cost = cand_cost
            current = {eid: list(r) for eid, r in repaired.items()}
            current_cost = cand_cost
            score = ALNS_SIGMA1
            no_improve = 0
        elif cand_cost < current_cost - 1e-6:
            current = {eid: list(r) for eid, r in repaired.items()}
            current_cost = cand_cost
            score = ALNS_SIGMA2
            no_improve += 1
        else:
            delta = cand_cost - current_cost
            prob = math.exp(-delta / temp) if temp > 0 else 0.0
            if rng.random() < prob:
                current = {eid: list(r) for eid, r in repaired.items()}
                current_cost = cand_cost
                score = ALNS_SIGMA3
            no_improve += 1

        d_scores[d_op] += score
        r_scores[r_op] += score
        d_uses[d_op] += 1
        r_uses[r_op] += 1

        if (it + 1) % ALNS_WEIGHT_UPDATE_PERIOD == 0:
            for op in destroy_ops:
                if d_uses[op] > 0:
                    d_weights[op] = ((1 - ALNS_RHO) * d_weights[op]
                                     + ALNS_RHO * (d_scores[op] / d_uses[op]))
                    d_scores[op] = 0.0
                    d_uses[op] = 0
            for op in repair_ops:
                if r_uses[op] > 0:
                    r_weights[op] = ((1 - ALNS_RHO) * r_weights[op]
                                     + ALNS_RHO * (r_scores[op] / r_uses[op]))
                    r_scores[op] = 0.0
                    r_uses[op] = 0

        if no_improve >= ALNS_NO_IMPROVE_LIMIT:
            break

    return best, best_cost


# =============================================================================
# ПЕРЕПЛАНИРОВАНИЕ
# =============================================================================

def reoptimize(routes, engineers, office_loc, all_tasks, now, new_tasks,
               alns_iterations=ALNS_ITERATIONS):
    update_task_statuses(routes, engineers, office_loc, now)
    prefixes, pending, master_state = split_locked_and_pending(
        routes, engineers, office_loc, now)

    for t in new_tasks:
        if TASK_SKILL.get(t["bk"]):
            if t not in pending:
                pending.append(t)

    pending.sort(key=lambda x: (0 if x.get("is_urgent") else 1,
                                x.get("priority", 9), x["end"]))

    initial = regret_insert(list(pending), engineers, office_loc,
                            prefixes, master_state, check_eq=True)
    initial = local_search(initial, engineers, office_loc,
                           prefixes, master_state, check_eq=True)

    assigned_ids = set()
    for eid, r in initial.items():
        for t in r:
            assigned_ids.add(id(t))
    remaining = [t for t in pending if id(t) not in assigned_ids]
    if remaining:
        force_assign_remaining(remaining, initial, engineers, office_loc,
                               prefixes, master_state, check_eq=True)

    initial = minimize_engineers(initial, engineers, office_loc,
                                 prefixes, master_state, check_eq=True)

    best, best_cost = alns(initial, engineers, office_loc, prefixes,
                           master_state, iterations=alns_iterations)
    best = minimize_engineers(best, engineers, office_loc, prefixes,
                              master_state, check_eq=True)
    best_cost = solution_cost(best, engineers, office_loc,
                              prefixes, master_state)

    assigned_ids = set()
    for eid, r in best.items():
        for t in r:
            assigned_ids.add(id(t))
    unassigned = [t for t in pending if id(t) not in assigned_ids]

    best = {eid: r for eid, r in best.items() if r}
    update_task_statuses(best, engineers, office_loc, now)
    return best, unassigned


def force_insert_best_position(task, eid, routes, engineers, office_loc,
                               prefixes=None, master_state=None):
    eng = next((e for e in engineers if e["id"] == eid), None)
    if eng is None:
        return False, "мастер не найден"

    skill = TASK_SKILL.get(task["bk"])
    if not skill:
        return False, f"неизвестный тип заявки '{task['bk']}'"
    if skill not in eng["skills"]:
        return False, f"нет навыка '{skill}'"

    route = routes.get(eid, [])
    needed = route_equipment_needed(route + [task])
    alloc = eng.get("equipment_allocated", {"router": 0, "stb": 0})

    if alloc["router"] < needed["router"] or alloc["stb"] < needed["stb"]:
        return False, "не хватает оборудования"

    prefix_len = len((prefixes or {}).get(eid, []))
    init_time, init_loc = (master_state or {}).get(
        eid, (eng["shift_start"], office_loc))

    best_route = None
    best_cost = None
    for pos in range(len(route) + 1):
        cand = route[:pos] + [task] + route[pos:]

        if _light_transport_over_limit(eng, cand):
            continue
        if not check_equipment(eng, cand):
            continue

        suffix = cand[prefix_len:]
        ev = evaluate_route(eng, suffix, office_loc, init_time, init_loc,
                            equipment_full_route=cand)
        if not ev.get("feasible", True):
            continue

        c = route_cost(ev, is_new_route=(len(route) == 0))
        if not math.isfinite(c):
            continue
        c += transport_equipment_bonus(task, eng)
        c += urgent_penalty(ev, task)
        if best_cost is None or c < best_cost:
            best_cost = c
            best_route = cand

    if best_route is None:
        return False, "не удалось найти допустимую позицию"

    routes[eid] = best_route
    return True, ""


# =============================================================================
# ГЕОМЕТРИЯ (Mapbox)
# =============================================================================

def _mapbox_request(stops_chunk, profile):
    coords = ";".join(f"{lon},{lat}" for lat, lon in stops_chunk)
    url = f"{MAPBOX_DIRECTIONS_URL}/{profile}/{coords}"
    params = {
        "geometries":   "geojson",
        "overview":     "full",
        "steps":        "false",
        "language":     "ru",
        "access_token": MAPBOX_TOKEN,
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data.get("routes"):
        return None
    geom = data["routes"][0]["geometry"]["coordinates"]
    return [[lat, lon] for lon, lat in geom]


def mapbox_route_geometry(stops, profile="driving"):
    if not MAPBOX_TOKEN or len(stops) < 2:
        return [[lat, lon] for lat, lon in stops]
    full, i = [], 0
    try:
        while i < len(stops) - 1:
            chunk = stops[i:i + MAPBOX_MAX_COORDS]
            if len(chunk) < 2:
                break
            piece = _mapbox_request(chunk, profile)
            if piece is None:
                raise RuntimeError("Mapbox вернул пустой routes")
            if full:
                piece = piece[1:]
            full.extend(piece)
            i += MAPBOX_MAX_COORDS - 1
        return full or [[lat, lon] for lat, lon in stops]
    except Exception as e:
        print(f"    ⚠ Mapbox ({profile}): {e}")
        return [[lat, lon] for lat, lon in stops]


def split_geometry_by_waypoints(geometry, waypoints):
    if len(waypoints) < 2 or len(geometry) < 2:
        return [geometry]
    n = len(geometry)
    idx = []
    for wp in waypoints:
        best_i, best_d = 0, float("inf")
        for i in range(n):
            d = (geometry[i][0] - wp[0]) ** 2 + (geometry[i][1] - wp[1]) ** 2
            if d < best_d:
                best_d = d
                best_i = i
        idx.append(best_i)
    for i in range(1, len(idx)):
        if idx[i] < idx[i - 1]:
            idx[i] = idx[i - 1]
    idx[0] = 0
    idx[-1] = n - 1
    segs = []
    for i in range(1, len(waypoints)):
        a, b = idx[i - 1], idx[i]
        if b <= a:
            segs.append([waypoints[i - 1], waypoints[i]])
        else:
            segs.append(geometry[a:b + 1])
    return segs


# =============================================================================
# HTML-КАРТА
# =============================================================================

COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080",
    "#e6beff", "#9a6324", "#800000", "#aaffc3", "#808000",
    "#000075", "#808080", "#ffe119", "#ffd8b1",
]


def _render_map(masters_map_data, title, filename):
    masters_json = json.dumps(masters_map_data, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8" />
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html,body {{ height:100%; margin:0; padding:0; font-family: sans-serif; }}
  #map {{ width:100%; height:100%; }}
  .legend {{ background:#fff; padding:10px; line-height:1.5; font-size:13px;
             border-radius:6px; box-shadow:0 0 10px rgba(0,0,0,.3);
             max-height:70vh; overflow-y:auto; }}
  .dark .legend {{ background:#222; color:#eee; }}
  .legend-item {{ display:flex; align-items:center; margin-bottom:4px; }}
  .legend-color {{ width:18px; height:4px; margin-right:8px; }}
  .legend-dot {{ width:14px; height:14px; border-radius:50%;
                 margin-right:8px; border:2px solid #fff;
                 box-shadow:0 1px 3px rgba(0,0,0,.4); }}
  .legend-profile {{ color:#666; font-size:11px; margin-left:4px; }}
  .pin-wrap {{ background:transparent !important; border:none !important; }}
  .pin-marker {{
    display:flex; align-items:center; justify-content:center;
    width:26px; height:26px; border-radius:50%;
    background: var(--c, #4363d8);
    border:2px solid #fff;
    box-shadow:0 2px 6px rgba(0,0,0,.45);
    font: 700 12px/1 sans-serif; color:#fff;
    user-select:none;
  }}
  .pin-office {{ background:#111; color:#fff; border-color:#fff; }}
  .pin-urgent {{ box-shadow: 0 0 0 3px rgba(230,25,75,.7), 0 2px 6px rgba(0,0,0,.45); }}
  .leaflet-tooltip.pin-tooltip {{
    font-size:12px; white-space:normal; max-width:260px;
    padding:6px 8px; border-radius:6px;
  }}
</style></head>
<body><div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const masters = {masters_json};
const map = L.map('map', {{ preferCanvas: true }});
const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19, subdomains: 'abc',
    attribution: '&copy; OpenStreetMap contributors | Routing: &copy; Mapbox'
}});
const dark = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    maxZoom: 19, subdomains:'abcd', attribution:'&copy; OSM, &copy; CARTO'
}});
osm.addTo(map);
map.on('baselayerchange', e => {{
    if (e.name === 'Тёмная') document.body.classList.add('dark');
    else document.body.classList.remove('dark');
}});
const PROFILE_STYLE = {{
    walking: {{ weight: 4, dashArray: '1 8', opacity: 0.9 }},
    cycling: {{ weight: 5, dashArray: null,  opacity: 0.9 }},
    driving: {{ weight: 6, dashArray: null,  opacity: 0.85 }},
}};
function makeIcon(num, color, kind, urgent) {{
    const isOffice = (kind === 'office_start' || kind === 'office_end');
    let cls = isOffice ? 'pin-marker pin-office' : 'pin-marker';
    if (urgent) cls += ' pin-urgent';
    const sz = isOffice ? 28 : 26;
    return L.divIcon({{
        className: 'pin-wrap',
        html: `<div class="${{cls}}" style="--c:${{color}}">${{num}}</div>`,
        iconSize: [sz, sz], iconAnchor: [sz/2, sz/2],
        tooltipAnchor: [0, -sz/2], popupAnchor: [0, -sz/2],
    }});
}}
const allBounds = [];
for (const m of masters) {{
    const st = PROFILE_STYLE[m.profile] || PROFILE_STYLE.driving;
    if (m.segments && m.segments.length) {{
        for (const seg of m.segments) {{
            if (!seg.points || seg.points.length < 2) continue;
            L.polyline(seg.points, {{
                color: seg.color, weight: st.weight,
                opacity: st.opacity, dashArray: st.dashArray
            }}).addTo(map).bindPopup(seg.popup || ('Мастер ' + m.id));
        }}
    }}
    for (const s of m.stops) {{
        const marker = L.marker([s.lat, s.lon], {{
            icon: makeIcon(s.num, s.color || m.color, s.kind, s.urgent),
            riseOnHover: true,
            zIndexOffset: (s.kind === 'task' ? 0 : 500),
        }}).addTo(map);
        if (s.label) {{
            marker.bindTooltip(s.label, {{
                direction: 'top', offset: [0, -4],
                className: 'pin-tooltip', sticky: false,
            }});
        }}
        if (s.popup) marker.bindPopup(s.popup);
        allBounds.push([s.lat, s.lon]);
    }}
    if (m.segments) for (const seg of m.segments) for (const p of seg.points) allBounds.push(p);
}}
if (allBounds.length > 0) map.fitBounds(allBounds, {{ padding: [30,30] }});
else map.setView([55.7558, 37.6173], 11);
L.control.layers({{ 'OpenStreetMap': osm, 'Тёмная': dark }}).addTo(map);
const legend = L.control({{ position:'bottomright' }});
legend.onAdd = function() {{
    const div = L.DomUtil.create('div', 'legend');
    div.innerHTML = '<b>Мастера</b><br>';
    for (const m of masters) {{
        const tasks = m.stops.filter(s => s.kind === 'task').length;
        div.innerHTML += `<div class="legend-item">
            <div class="legend-color" style="background:${{m.color}}"></div>
            Мастер ${{m.id}} — ${{tasks}} заявок
        </div>`;
    }}
    div.innerHTML += '<hr><span style="color:#e6194b">✦ красная обводка — СРОЧНАЯ / ГЛОБАЛЬНАЯ</span>';
    return div;
}};
legend.addTo(map);
</script></body></html>"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)


def _compute_colors(schedule, eng, now):
    """
    Приоритет — статус заявки (из update_task_statuses).
    Если статуса нет — fallback на время.
    """
    seg_colors = []
    pin_colors = []
    prev_end = eng["shift_start"]

    for item in schedule:
        task_start = item["start"]
        task_end = item["end"]
        status = (item["task"].get("status") or "").lower()

        if status in ("completed", "cancelled"):
            seg_color = COLOR_DONE
            pin_color = COLOR_DONE
        elif status == "in_progress":
            seg_color = COLOR_IN_TRANSIT
            pin_color = COLOR_IN_TRANSIT
        elif status in ("en_route", "arrived"):
            seg_color = COLOR_IN_TRANSIT
            pin_color = COLOR_IN_TRANSIT
        else:
            if now < prev_end:
                seg_color = COLOR_PLANNED
            elif now < task_start:
                seg_color = COLOR_IN_TRANSIT
            else:
                seg_color = COLOR_DONE
            if now < task_start:
                pin_color = COLOR_PLANNED
            elif now < task_end:
                pin_color = COLOR_IN_TRANSIT
            else:
                pin_color = COLOR_DONE

        seg_colors.append(seg_color)
        pin_colors.append(pin_color)
        prev_end = task_end

    last_end = schedule[-1]["end"] if schedule else eng["shift_start"]
    if now < last_end:
        return_color = COLOR_PLANNED
    elif now < eng["shift_end"]:
        return_color = COLOR_RETURN
    else:
        return_color = COLOR_DONE
    return seg_colors, pin_colors, return_color


def build_map_data(routes, engineers, office_loc, now):
    eng_by_id = {e["id"]: e for e in engineers}
    data = []
    for eid, route in routes.items():
        if not route:
            continue
        eng = eng_by_id[eid]
        ev = evaluate_route(eng, route, office_loc,
                            equipment_full_route=route)
        color = COLORS[(eng["id"] - 1) % len(COLORS)]
        profile = TRANSPORT_TO_MAPBOX_PROFILE.get(eng["transport"], "driving")

        waypoints = ([office_loc] + [(t["lat"], t["lon"]) for t in route]
                     + [office_loc])
        full_geom = mapbox_route_geometry(waypoints, profile=profile)
        split = split_geometry_by_waypoints(full_geom, waypoints)

        seg_colors, pin_colors, return_color = _compute_colors(
            ev["schedule"], eng, now)

        shift_start_str = eng["shift_start"].strftime("%H:%M")
        shift_end_str   = eng["shift_end"].strftime("%H:%M")
        total_tasks     = len(route)

        # ---------- Сегменты (линии маршрута) ----------
        segments = []
        for i, seg_points in enumerate(split):
            if i < len(route):
                t = route[i]
                seg_color = seg_colors[i]
                status_ru = STATUS_RU.get(t.get("status", "planned"),
                                          t.get("status"))
                mark = " 🚨" if t.get("is_urgent") else ""
                bk = t.get("bk", "")
                item = ev["schedule"][i] if i < len(ev["schedule"]) else None
                leg_info = ""
                if item:
                    leg_info = (f"<br>Дорога: ~{item['travel_min']:.0f} мин "
                                f"({item['leg_km']:.1f} км)")
                seg_popup = (f"<b>Мастер {eng['name']}</b> → "
                             f"<b>Заявка #{t['id']}</b><br>"
                             f"<b>{bk}</b>{mark} · {status_ru}<br>"
                             f"{t['address']}{leg_info}")
            else:
                seg_color = return_color
                end_day_str = ev["end_day"].strftime("%H:%M")
                seg_popup = (f"<b>Мастер {eng['name']}</b> → <b>Офис</b><br>"
                             f"Возврат: {return_color and 'по плану' or ''} "
                             f"~ {ev['return_min']:.0f} мин<br>"
                             f"Финиш смены: {end_day_str}")
            segments.append({
                "points": seg_points,
                "color":  seg_color,
                "popup":  seg_popup,
            })

        # ---------- Оборудование мастера ----------
        alloc = eng.get("equipment_allocated", {"router": 0, "stb": 0})
        eq_total = {"router": 0, "stb": 0}
        for item in ev["schedule"]:
            t = item["task"]
            eq = TASK_EQUIPMENT.get(t["bk"], {"router": 0, "stb": 0})
            eq_total["router"] += eq["router"]
            eq_total["stb"]    += eq["stb"]
        eq_rem = {"router": alloc["router"] - eq_total["router"],
                  "stb":    alloc["stb"]    - eq_total["stb"]}

        # ---------- Стопы (маркеры) ----------
        # 1) Офис — старт
        office_start_popup = (
            f"<b>Офис</b> — старт мастера {eng['name']}<br>"
            f"Транспорт: {eng['transport']}<br>"
            f"Смена: {shift_start_str}–{shift_end_str}"
        )
        stops = [{
            "lat": office_loc[0], "lon": office_loc[1],
            "popup": office_start_popup,
            "label": (f"Офис · старт мастера {eng['name']} · "
                      f"смена {shift_start_str}–{shift_end_str}"),
            "color": COLOR_OFFICE, "num": "С", "kind": "office_start",
            "urgent": False,
        }]

        # 2) Задачи
        for idx, item in enumerate(ev["schedule"], 1):
            t = item["task"]
            status = t.get("status", "planned")
            status_ru = STATUS_RU.get(status, status)
            is_urgent_or_global = (
                bool(t.get("is_urgent")) or t.get("bk") == "Глобальная проблема"
            )
            urgent_tag = " 🚨 СРОЧНАЯ" if is_urgent_or_global else ""

            eq = TASK_EQUIPMENT.get(t["bk"], {"router": 0, "stb": 0})
            eq_parts = []
            if eq.get("router"): eq_parts.append(f"router × {eq['router']}")
            if eq.get("stb"):    eq_parts.append(f"STB × {eq['stb']}")

            departure = item["arrival"] - timedelta(
                minutes=effective_travel_min(item["travel_min"])
            )

            # ── Собираем строки попапа по секциям ──
            lines = []
            # --- Заголовок: кто и куда ---
            lines.append(
                f"<b>Мастер {eng['name']}</b> ({eng['transport']})"
                f"{urgent_tag}"
            )
            lines.append(
                f"<b>Заявка #{t['id']}</b> "
                f"<span style='color:#666'>№{idx} из {total_tasks} "
                f"в маршруте</span>"
            )
            # --- Тип заявки ---
            type_str = f"<b>{t['bk']}</b>"
            if t.get("hd"):
                type_str += f" / {t['hd']}"
            lines.append(type_str)
            # --- Адрес ---
            lines.append(t["address"])
            # --- Доп. инфо о заявке ---
            if t.get("district"):
                lines.append(f"Район: {t['district']}")
            if t.get("gigabit"):
                lines.append(f"Гигабит: {t['gigabit']}")
            lines.append(
                f"Окно клиента: {t['start'].strftime('%H:%M')}–"
                f"{t['end'].strftime('%H:%M')}"
            )
            lines.append(f"Длительность работ: {t['service']} мин")
            lines.append(f"Статус: {status_ru}")
            if eq_parts:
                lines.append(f"Оборудование: {', '.join(eq_parts)}")

            # --- Разделитель ---
            lines.append(
                "<hr style='margin:6px 0;border:none;"
                "border-top:1px solid #ccc'>"
            )

            # --- Тайминг маршрута ---
            lines.append(
                f"<b>План:</b> выезд {departure.strftime('%H:%M')} → "
                f"прибытие {item['arrival'].strftime('%H:%M')}"
            )
            lines.append(
                f"Начало работ: <b>{item['start'].strftime('%H:%M')}</b> · "
                f"окончание: <b>{item['end'].strftime('%H:%M')}</b>"
            )
            lines.append(
                f"Дорога до точки: ~{item['travel_min']:.0f} мин "
                f"({item['leg_km']:.1f} км)"
            )
            if item.get("wait_min", 0) > 1:
                lines.append(f"Ожидание на месте: {item['wait_min']:.0f} мин")

            popup = "<br>".join(lines)

            # --- Тултип (при наведении, короткий) ---
            label = (
                f"№{idx} [{status_ru}]{urgent_tag} · "
                f"{t.get('bk','')} · "
                f"{t['start'].strftime('%H:%M')}–"
                f"{t['end'].strftime('%H:%M')} · "
                f"{t['address']}"
            )

            stops.append({
                "lat": t["lat"], "lon": t["lon"],
                "popup": popup, "label": label,
                "color": pin_colors[idx - 1], "num": str(idx),
                "kind": "task",
                "urgent": is_urgent_or_global,
            })

        # 3) Офис — финиш
        office_end_popup = (
            f"<b>Офис</b> — финиш мастера {eng['name']}<br>"
            f"Плановое возвращение: {ev['end_day'].strftime('%H:%M')}<br>"
            f"Пройдено: ~{ev['total_km']:.1f} км"
        )
        stops.append({
            "lat": office_loc[0], "lon": office_loc[1],
            "popup": office_end_popup,
            "label": (f"Офис · финиш мастера {eng['name']} · "
                      f"~{ev['end_day'].strftime('%H:%M')}"),
            "color": COLOR_OFFICE, "num": "Ф", "kind": "office_end",
            "urgent": False,
        })

        data.append({
            "id":      eng["id"],
            "color":   color,
            "profile": profile,
            "segments": segments,
            "stops":   stops,
        })
    return data