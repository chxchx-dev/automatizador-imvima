from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

COLOMBIA = timezone(timedelta(hours=-5), "America/Bogota")


def now_colombia() -> datetime:
    return datetime.now(COLOMBIA)


def today_colombia() -> date:
    return now_colombia().date()
