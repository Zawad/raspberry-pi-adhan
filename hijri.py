"""Hijri calendar helpers (offline, via the pure-Python hijridate package)."""
from datetime import date, timedelta

import db

try:
    from hijridate import Gregorian
except ImportError:  # keep the daemon runnable without the package
    Gregorian = None

RAMADAN_MONTH = 9


def hijri_offset() -> int:
    """Days to shift the Hijri date by, for local moonsighting. Clamped to -2..+2."""
    try:
        offset = int(db.get_setting("hijri_offset", 0))
    except (TypeError, ValueError):
        offset = 0
    return max(-2, min(2, offset))


def today_hijri() -> dict | None:
    if Gregorian is None:
        return None
    h = Gregorian.fromdate(date.today() + timedelta(days=hijri_offset())).to_hijri()
    return {
        "day": h.day,
        "month": h.month,
        "year": h.year,
        "text": f"{h.day} {h.month_name()} {h.year} AH",
    }


def ramadan_active() -> bool:
    mode = db.get_setting("ramadan_mode", "auto")
    if mode == "on":
        return True
    if mode == "off":
        return False
    h = today_hijri()
    return bool(h and h["month"] == RAMADAN_MONTH)
