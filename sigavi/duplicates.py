from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime


def normalize_text(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value).strip().casefold()


def normalize_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/").casefold()


def date_text(value: date | datetime | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()[:10]


def identity_key(code: str, alert_date: date | datetime | str | None, product: str, alert_url: str, pdf_url: str) -> str:
    parts = "|".join((
        normalize_text(code),
        date_text(alert_date),
        normalize_text(product),
        normalize_url(alert_url),
        normalize_url(pdf_url),
    ))
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def windows_safe_name(value: str, max_length: int = 110) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    value = value[:max_length].rstrip(" .") or "alerta"
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        value = f"_{value}"
    return value
