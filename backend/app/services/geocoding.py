# backend/app/services/geocoding.py
"""
Алгоритм геокодирования адресов через LocationIQ.
С подробным логированием каждого шага (в stdout).
"""
from __future__ import annotations

import os
import re
import time
from typing import Optional

import requests


LOCATIONIQ_API_KEY = os.environ.get(
    "LOCATIONIQ_API_KEY",
    "pk.c0746f8cfc1ae74893ba4df23c8812a8",
)
LOCATIONIQ_URL = "https://us1.locationiq.com/v1/search.php"

HEADERS = {"Accept": "application/json", "Accept-Language": "ru,en;q=0.8"}
LOCATIONIQ_MIN_INTERVAL = 1
_last_locationiq = [0.0]

# Минимальный score, при котором мы доверяем попаданию.
# См. _score_hit: только дом ≈ 9, улица+дом ≈ 12–14.
# Ниже порога — попадание «просто Москва», его лучше не принимать.
MIN_ACCEPT_SCORE = 6.0


# ============================================================
#  Нормализация
# ============================================================

STREET_TYPE_MAP = {
    "ул": "улица", "улица": "улица", "улицы": "улица",
    "пр-кт": "проспект", "пр-т": "проспект", "просп": "проспект",
    "проспект": "проспект",
    "пр": "проезд", "пр-д": "проезд", "проезд": "проезд",
    "пер": "переулок", "переулок": "переулок",
    "б-р": "бульвар", "бул": "бульвар", "бульвар": "бульвар",
    "наб": "набережная", "набережная": "набережная",
    "пл": "площадь", "площадь": "площадь",
    "ш": "шоссе", "шоссе": "шоссе",
    "ал": "аллея", "аллея": "аллея",
    "туп": "тупик", "тупик": "тупик",
    "дор": "дорога", "дорога": "дорога",
    "просек": "просек", "просека": "просека",
}
_KEYS = sorted(STREET_TYPE_MAP.keys(), key=len, reverse=True)
_TYPES_RE = "|".join(re.escape(k) for k in _KEYS)
_PREFIX_RE = re.compile(r"^\s*(" + _TYPES_RE + r")\.?[\s\.]+(.+?)\s*$", re.IGNORECASE)
_SUFFIX_RE = re.compile(r"^\s*(.+?)\s+(" + _TYPES_RE + r")\.?\s*$", re.IGNORECASE)
_STREET_PREFIX_RE = re.compile(r"^\s*(" + _TYPES_RE + r")\.?\s+", re.IGNORECASE)

_CITY_RE = re.compile(r"^\s*(?:Город|город|г\.?)\s+(.+?)\s*$", re.IGNORECASE)
_CITY_WRAPPER_RE = re.compile(r"^\s*(?:Город|город|г\.?)\s*", re.IGNORECASE)

# "г.Город" → "г. Город" (точка + любая не-пробельная буква)
_DOT_SPACE_RE = re.compile(r"\.(?=\S)")


def _pre_normalize(address: str) -> str:
    """Общая пред-обработка строки адреса."""
    a = (address or "").strip()
    if not a:
        return ""
    # "г.Город" → "г. Город"
    a = _DOT_SPACE_RE.sub(". ", a)
    # множественные пробелы
    a = re.sub(r"\s+", " ", a)
    # " ," → ","
    a = re.sub(r"\s+,", ",", a)
    return a


def _clean_city_name(city: str) -> str:
    """Убирает обёртки 'Город', 'г.', 'город' из названия города."""
    s = (city or "").strip(" .,")
    for _ in range(3):
        new = _CITY_WRAPPER_RE.sub("", s).strip(" .,")
        if new == s or not new:
            break
        s = new
    return s


def clean_text(s) -> str:
    if s is None:
        return ""
    s = str(s).replace("\t", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_street(street: str):
    s = street.strip(" .,")
    m = _PREFIX_RE.match(s)
    if m:
        type_key = m.group(1).lower()
        name = m.group(2).strip(" .,")
    else:
        m = _SUFFIX_RE.match(s)
        if m:
            name = m.group(1).strip(" .,")
            type_key = m.group(2).lower()
        else:
            return s, ""
    type_full = STREET_TYPE_MAP.get(type_key, type_key)
    extra = ""
    m2 = re.search(r"\s+(Квартал\s+\S+)", name, re.IGNORECASE)
    if m2:
        extra = m2.group(1)
        name = name[:m2.start()].strip(" .,")
    return f"{name} {type_full}".strip(), extra


def normalize_house(h: str) -> str:
    s = h.strip()
    s = re.sub(r"^(д\.?|дом)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bстроение\s*", "с", s, flags=re.IGNORECASE)
    s = re.sub(r"\bстр\.?\s*",  "с", s, flags=re.IGNORECASE)
    s = re.sub(r"\bкорпус\s*",  "к", s, flags=re.IGNORECASE)
    s = re.sub(r"\bкорп\.?\s*", "к", s, flags=re.IGNORECASE)
    s = re.sub(r"\bк\.\s*",     "к", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*/\s*", "/", s)
    s = re.sub(r"\s+", "", s)
    return s


def _looks_like_street(part: str) -> bool:
    """Похоже ли «на улицу»: начинается или заканчивается на тип улицы."""
    s = (part or "").strip(" .,")
    if not s:
        return False
    return bool(_PREFIX_RE.match(s) or _SUFFIX_RE.match(s))


def extract_city(address: str):
    """
    Возвращает (город, остаток_адреса).

    Поддерживает форматы:
      «Москва, ул. Ленина, 1»
      «Город Москва, ул. Ленина, 1»
      «г.Город Москва, ул. Ленина, 1»   ← теперь тоже
      «Кузьминки, Город Москва, пр-кт.Волгоградский, 128к5»
    """
    a = _pre_normalize(address)
    if not a:
        return None, ""

    parts = [p.strip(" .,") for p in a.split(",")]
    parts = [p for p in parts if p]
    if not parts:
        return None, ""

    # 1. Явное «Город X» / «г. X» — в любой позиции
    for idx, part in enumerate(parts):
        m = _CITY_RE.match(part)
        if m:
            city = _clean_city_name(m.group(1))
            if city:
                rest = parts[:idx] + parts[idx + 1:]
                return city, ", ".join(rest).strip(" ,.")

    # 2. Если есть улица по типу — город = элемент прямо перед ней
    street_idx = next(
        (i for i, p in enumerate(parts) if _looks_like_street(p)), None
    )
    if street_idx is not None and street_idx > 0:
        city = _clean_city_name(parts[street_idx - 1])
        if city:
            rest = parts[:street_idx - 1] + parts[street_idx:]
            return city, ", ".join(rest).strip(" ,.")

    # 3. Fallback: первый элемент — город, если он не улица
    first = _clean_city_name(parts[0])
    if first and not _looks_like_street(first):
        return first, ", ".join(parts[1:]).strip(" ,.")

    return None, a


# ============================================================
#  Варианты номера дома
# ============================================================

def _house_variants(house: str) -> list[str]:
    """
    Возвращает список вариантов написания дома для запроса к LocationIQ.

      9Бс1    → 9Бс1, 9Бк1, 9Б к 1, 9Б стр 1, 9Б
      128к5   → 128к5, 128 к 5, 128
      24/30с1 → 24/30с1, 24/30к1, 24/30 к 1, 24/30, 24
    """
    if not house:
        return [""]

    h = house.strip()
    out: list[str] = []
    seen: set[str] = set()

    def add(v: str) -> None:
        v = (v or "").strip(" .,")
        if v and v not in seen:
            seen.add(v)
            out.append(v)

    add(h)

    # «сN» (строение) → «кN» (корпус)
    add(re.sub(r"(\d)\s*[сc]\s*(\d)", r"\1к\2", h, flags=re.IGNORECASE))
    # «сN» → « к N»
    add(re.sub(r"(\d)\s*[сc]\s*(\d)", r"\1 к \2", h, flags=re.IGNORECASE))
    # «сN» → « стр N»
    add(re.sub(r"(\d)\s*[сc]\s*(\d)", r"\1 стр \2", h, flags=re.IGNORECASE))
    # «кN» → « к N»
    add(re.sub(r"(\d)\s*[кk]\s*(\d)", r"\1 к \2", h, flags=re.IGNORECASE))

    # без корпуса/строения в конце
    add(re.sub(r"[сcкk]\d+$", "", h, flags=re.IGNORECASE))
    # до дроби
    if "/" in h:
        head = h.split("/")[0]
        add(head)

    return out


# ============================================================
#  LocationIQ
# ============================================================

def _wait_locationiq():
    now = time.time()
    delta = now - _last_locationiq[0]
    if delta < LOCATIONIQ_MIN_INTERVAL:
        time.sleep(LOCATIONIQ_MIN_INTERVAL - delta)
    _last_locationiq[0] = time.time()


def _locationiq_request(params: dict, timeout: int = 10) -> list:
    if not LOCATIONIQ_API_KEY:
        return []
    base = {
        "key": LOCATIONIQ_API_KEY,
        "format": "json",
        "limit": 5,
        "accept-language": "ru",
        "addressdetails": 1,
        "normalizecity": 1,
    }
    base.update({k: v for k, v in params.items() if v})

    for attempt in range(3):
        _wait_locationiq()
        try:
            r = requests.get(LOCATIONIQ_URL, params=base,
                             headers=HEADERS, timeout=timeout)
        except requests.exceptions.Timeout:
            print(f"      [HTTP] timeout, повтор {attempt+1}/3", flush=True)
            time.sleep(2)
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"      [HTTP] connection error: {e}, повтор {attempt+1}/3", flush=True)
            time.sleep(3)
            continue

        if r.status_code in (401, 403):
            print(f"      [HTTP] {r.status_code} — неверный API-ключ", flush=True)
            return []
        if r.status_code == 429:
            print(f"      [HTTP] 429 rate-limit, повтор {attempt+1}/3", flush=True)
            time.sleep(2 * (2 ** attempt))
            continue
        if r.status_code != 200:
            print(f"      [HTTP] {r.status_code}", flush=True)
            return []
        try:
            data = r.json()
        except Exception as e:
            print(f"      [HTTP] ошибка JSON: {e}", flush=True)
            return []
        return data if isinstance(data, list) else []
    return []


def _build_query_params(address: str, district: str | None = None) -> list:
    if not address:
        return []
    city, rest = extract_city(address)
    parts = [p.strip(" .") for p in rest.split(",") if p.strip(" .")]
    if not parts:
        return []

    # Ищем настоящую улицу по типу, а не первую попавшуюся часть.
    street_idx = next(
        (i for i, p in enumerate(parts) if _looks_like_street(p)), None
    )
    if street_idx is not None:
        street_raw  = parts[street_idx]
        house_parts = parts[street_idx + 1:]
    else:
        street_raw  = parts[0]
        house_parts = parts[1:]

    street, street_extra = normalize_street(street_raw)
    house_raw = ", ".join(house_parts).strip()
    house = normalize_house(house_raw) if house_raw else ""

    house_variants = _house_variants(house) if house else [""]
    h0 = house_variants[0] if house_variants else ""

    out, seen = [], set()

    def add(p):
        p = {k: v for k, v in p.items() if v}
        if not p:
            return
        key = tuple(sorted(p.items()))
        if key in seen:
            return
        seen.add(key)
        out.append(p)

    # ── 1. Основные street-запросы (оригинальный дом) ──
    if city and street and h0:
        add({"street": f"{h0} {street} {city}", "country": "ru"})
        add({"street": f"{h0}, {street}, {city}", "country": "ru"})
        add({"street": f"{h0}, {street}, {city}, Россия", "country": "ru"})
        add({"street": f"{street}, {h0}, {city}", "country": "ru"})
        add({"street": f"{street} {h0} {city}", "country": "ru"})
        add({"street": f"{street}, {h0}, {city}, Россия", "country": "ru"})
    if city and street:
        add({"q": f"{city}, {street}"})
    if street and h0:
        add({"street": f"{h0} {street}", "city": city or "", "country": "ru"})
        add({"street": f"{street}, {h0}", "city": city or "", "country": "ru"})
    if street:
        add({"street": street, "city": city or "", "country": "ru"})

    # ── 2. q-запросы с оригинальным домом ──
    if house:
        if city:
            add({"q": f"{city}, {street}, {h0}"})
            add({"q": f"{city}, {street}, {h0}, Россия"})
        if city and district:
            add({"q": f"{city}, {district}, {street}, {h0}"})
        if street_extra and city:
            add({"q": f"{city}, {street}, {street_extra}, {h0}"})

    # ── 3. Альтернативные варианты дома ──
    if city and street and house and len(house_variants) > 1:
        for hv in house_variants[1:]:
            add({"q": f"{city}, {street}, {hv}"})

    # ── 4. Запросы без дома — на крайний случай ──
    if city and street:
        add({"q": f"{city}, {street}, Россия"})

    add({"q": address})
    add({"q": f"{address}, Россия"})
    return out


_STREET_STOPWORDS = {
    "улица", "ул", "ул.", "проспект", "пр-т", "пр.", "пр-кт",
    "переулок", "пер", "пер.", "проезд", "пр-д", "шоссе", "ш",
    "бульвар", "б-р", "набережная", "наб", "площадь", "пл",
    "аллея", "дорога", "тупик", "съезд", "линия",
}


def _meaningful_tokens(street: str) -> list:
    if not street:
        return []
    tokens = re.split(r"[\s,.\-]+", street.lower().strip())
    return [t for t in tokens if t and t not in _STREET_STOPWORDS]


def _house_base(h: str) -> str:
    """9Бс1 → 9б, 24/30к2 → 24/30."""
    h = (h or "").strip().lower().replace(" ", "")
    return re.sub(r"[сcкk]\d+$", "", h, flags=re.IGNORECASE)


def _score_hit(item: dict, want_street: str | None = None,
               want_house: str | None = None) -> float:
    s = 0.0
    addr = item.get("address") or {}
    t = (item.get("type") or "").lower()
    cls = (item.get("class") or "").lower()
    hn = (addr.get("house_number") or "").strip()
    road = (addr.get("road") or addr.get("pedestrian")
            or addr.get("footway") or addr.get("path") or "").lower()

    if want_house:
        if hn:
            s += 5.0
            a = hn.replace(" ", "").lower()
            b = want_house.replace(" ", "").lower()
            if a == b:
                s += 4.0
            elif b in a or a in b:
                s += 2.0
            # совпадение «по базе»: 9Б = 9Бс1 = 9Бк1
            elif _house_base(a) and _house_base(a) == _house_base(b):
                s += 3.0
        else:
            s -= 3.0

    if want_street:
        want_tokens = _meaningful_tokens(want_street)
        road_tokens = _meaningful_tokens(road)
        if not want_tokens:
            pass
        elif not road_tokens:
            s -= 1.0
        else:
            road_set = set(road_tokens)
            matched = sum(1 for w in want_tokens if w in road_set)
            ratio = matched / len(want_tokens)
            if ratio == 1.0:
                s += 3.0
            elif ratio >= 0.5:
                s += 2.0
            elif ratio > 0:
                s += 1.0
            else:
                s -= 1.0

    if t in ("house", "building", "residential", "apartments"):
        s += 2.0
    if cls == "building":
        s += 1.0

    imp = item.get("importance")
    try:
        s += float(imp) * 0.5
    except (TypeError, ValueError):
        pass

    return s


def check_geocoder() -> bool:
    if not LOCATIONIQ_API_KEY:
        print("[GEO] LOCATIONIQ_API_KEY не задан", flush=True)
        return False
    hits = _locationiq_request({"q": "Москва, Красная площадь, 1"}, timeout=10)
    if hits:
        print("[GEO] LocationIQ отвечает", flush=True)
        return True
    print("[GEO] LocationIQ не отвечает", flush=True)
    return False


def geocode(address: str, district: str | None = None,
            max_seconds: int = 90, tag: str = "") -> Optional[tuple[float, float]]:
    """
    Геокодирует адрес. Возвращает (lat, lon) или None.
    Печатает подробный лог каждого варианта.
    """
    if not address:
        return None

    prefix = f"[GEO{(':' + tag) if tag else ''}]"

    city, rest = extract_city(address)
    parts = [p.strip(" .") for p in rest.split(",") if p.strip(" .")]
    want_street = want_house = None
    if parts:
        street_idx = next(
            (i for i, p in enumerate(parts) if _looks_like_street(p)), None
        )
        if street_idx is not None:
            want_street, _ = normalize_street(parts[street_idx])
            house_parts = parts[street_idx + 1:]
        else:
            want_street, _ = normalize_street(parts[0])
            house_parts = parts[1:]
        if house_parts:
            want_house = normalize_house(", ".join(house_parts))

    queries = _build_query_params(address, district)
    if not queries:
        print(f"{prefix} не удалось построить варианты запроса: «{address}»", flush=True)
        return None

    print(f"{prefix} геокодируем «{address}» — {len(queries)} вариантов", flush=True)

    started = time.time()
    best = None
    for idx, params in enumerate(queries, 1):
        if time.time() - started > max_seconds:
            print(f"{prefix} время вышло ({max_seconds}с)", flush=True)
            break

        label = params.get("q") or params.get("street") or "?"
        print(f"{prefix}   [{idx}/{len(queries)}] {label}", flush=True)

        hits = _locationiq_request(params, timeout=10)
        if not hits:
            print(f"{prefix}     ← пусто", flush=True)
            continue

        for h in hits:
            try:
                lat = float(h["lat"])
                lon = float(h["lon"])
            except Exception:
                continue
            sc = _score_hit(h, want_street, want_house)
            if best is None or sc > best[0]:
                best = (sc, lat, lon)

        print(f"{prefix}     → попаданий: {len(hits)}, лучший score = {best[0]:.1f}", flush=True)

        if best and best[0] >= 14.5:
            print(f"{prefix}     ✓ уверенное совпадение, дальше не ищем", flush=True)
            break

    if best and best[0] >= MIN_ACCEPT_SCORE:
        print(f"{prefix} ✓ {best[1]:.5f}, {best[2]:.5f} (score={best[0]:.1f})", flush=True)
        return best[1], best[2]

    if best:
        print(f"{prefix} ✗ все попадания ниже порога "
              f"(лучший score={best[0]:.1f} < {MIN_ACCEPT_SCORE})", flush=True)
    else:
        print(f"{prefix} ✗ адрес не геокодирован", flush=True)
    return None