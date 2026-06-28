from __future__ import annotations

import json
from datetime import date
from io import BytesIO
from typing import Any

import pandas as pd

from flight_delay_explorer.config import MONTH_NAMES, WEEKDAY_NAMES


def format_int(value: Any) -> str:
    if value is None or pd.isna(value):
        return "0"
    return f"{int(round(float(value))):,}"


def format_float(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "0.0"
    return f"{float(value):,.{digits}f}"


def format_percent(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "0.0%"
    return f"{float(value) * 100:,.{digits}f}%"


def format_minutes(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "0.0 min"
    return f"{float(value):,.{digits}f} min"


def month_name(month_number: int | None) -> str | None:
    if month_number is None:
        return None
    return MONTH_NAMES.get(int(month_number))


def weekday_name(weekday_number: int | None) -> str | None:
    if weekday_number is None:
        return None
    return WEEKDAY_NAMES.get(int(weekday_number))


def hhmm_to_label(value: Any) -> str | None:
    if value is None or value == "" or pd.isna(value):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if number == 2400:
        return "24:00"
    number %= 2400
    hours = number // 100
    minutes = number % 100
    return f"{hours:02d}:{minutes:02d}"


def hhmm_to_hour(value: Any) -> int | None:
    if value is None or value == "" or pd.isna(value):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if number == 2400:
        return 0
    return (number % 2400) // 100


def time_of_day_from_hour(hour: int | None) -> str | None:
    if hour is None:
        return None
    if 0 <= hour <= 5:
        return "Night"
    if 6 <= hour <= 11:
        return "Morning"
    if 12 <= hour <= 17:
        return "Afternoon"
    return "Evening"


def cancellation_reason_label(code: Any) -> str:
    mapping = {
        "A": "Carrier",
        "B": "Weather",
        "C": "National Air System",
        "D": "Security",
    }
    if code is None or code == "" or pd.isna(code):
        return "Unknown"
    return mapping.get(str(code).strip().upper(), "Unknown")


def df_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, default=_json_default).encode("utf-8")


def _json_default(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def figure_download_config(filename: str) -> dict[str, Any]:
    return {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {
            "format": "png",
            "filename": filename,
            "height": 900,
            "width": 1600,
            "scale": 2,
        },
    }


def excel_bytes(frame: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)
    return output.getvalue()
