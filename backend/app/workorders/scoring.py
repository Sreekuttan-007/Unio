"""Ranking technicians for a job. Pure functions over plain data, so every number is explainable and testable.

The collision engine decides whether an assignment is allowed. This only decides which allowed
choice to suggest first, and shows its working.
"""

import math
from datetime import datetime, timedelta
from typing import Any

from app.bookings.slots import SLOT_SECONDS
from app.campus.layout import BUILDING_REGIONS
from app.core.clock import ensure_utc, local_time
from app.workorders.policy import POINTS, PRIORITY_RANK, URGENT, WAIT_SCALE

CENTRES = {building: (x + w / 2, y + h / 2) for _, building, _, x, y, w, h in BUILDING_REGIONS}
NEARBY_DISTANCE = 360  # map units: roughly one block away


def ceil_slot(value: datetime) -> datetime:
    value = ensure_utc(value)
    seconds = int(value.timestamp())
    rounded = math.ceil(seconds / SLOT_SECONDS) * SLOT_SECONDS
    return datetime.fromtimestamp(rounded, tz=value.tzinfo)


def round_minutes(minutes: int) -> int:
    return max(15, math.ceil(minutes / 15) * 15)


def distance(building_a: str | None, building_b: str | None) -> float | None:
    a, b = CENTRES.get(building_a or ""), CENTRES.get(building_b or "")
    if a is None or b is None:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def plan_window(
    now: datetime, minutes: int, tasks: list[dict[str, Any]], shifts: list[dict[str, Any]], *, urgent: bool, horizon_hours: int = 72
) -> tuple[datetime, datetime, bool]:
    """The earliest slot a technician could do the job: free of their other jobs, and in a shift unless the job is urgent.

    Returns (start, end, inside a shift).
    """
    length = timedelta(minutes=round_minutes(minutes))
    start = ceil_slot(now)
    limit = start + timedelta(hours=horizon_hours)
    busy = sorted((ensure_utc(t["startAt"]), ensure_utc(t["endAt"])) for t in tasks if t.get("startAt") and t.get("endAt"))
    spans = sorted((ensure_utc(s["startAt"]), ensure_utc(s["endAt"])) for s in shifts)
    while start < limit:
        end = start + length
        clash = next((span for span in busy if span[0] < end and span[1] > start), None)
        if clash:
            start = ceil_slot(clash[1])
            continue
        inside = any(s_start <= start and s_end >= end for s_start, s_end in spans)
        if inside or urgent:
            return start, end, inside
        later = next((max(s_start, start) for s_start, s_end in spans if s_end > start and max(s_start, start) > start and max(s_start, start) + length <= s_end), None)
        if later is None:
            break
        start = ceil_slot(later)
    fallback = ceil_slot(now)
    return fallback, fallback + length, False


def _duration(minutes: float) -> str:
    total = round(minutes)
    if total < 60:
        return f"{total} min"
    hours, rest = divmod(total, 60)
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def score_candidate(
    order: dict[str, Any], tech: dict[str, Any], tasks: list[dict[str, Any]], shifts: list[dict[str, Any]], window: tuple[datetime, datetime, bool], now: datetime
) -> dict[str, Any]:
    """A 0 to 100 score with each part of it spelled out as a sentence."""
    start, end, inside = window
    held = {skill["code"]: skill["level"] for skill in tech.get("skills", [])}
    needs = order.get("requiredSkills", [])
    factors: list[dict[str, Any]] = []
    parts: dict[str, float] = {}

    # Skill: meeting the minimum is worth most of it, and each level above adds a little.
    gaps = [(need, held.get(need["code"])) for need in needs]
    missing = [need for need, level in gaps if level is None or level < need["minLevel"]]
    if missing:
        parts["skill"] = 0
        factors.append({"label": "Skill", "value": f"Needs {missing[0]['code'].title()} level {missing[0]['minLevel']}", "good": False})
    else:
        surplus = sum(level - need["minLevel"] for need, level in gaps if level is not None) / max(len(gaps), 1)
        parts["skill"] = min(POINTS["skill"], POINTS["skill"] * 2 / 3 + surplus * 5)
        described = ", ".join(f"{need['code'].title()} level {level}" for need, level in gaps) or "No special skill needed"
        factors.append({"label": "Skill", "value": described, "good": True})

    # Workload: minutes already booked.
    booked = sum(int(task.get("estimatedMinutes") or 60) for task in tasks)
    parts["workload"] = POINTS["workload"] * max(0.0, 1 - booked / 480)
    count = len(tasks)
    factors.append({"label": "Workload", "value": f"{count} {'task' if count == 1 else 'tasks'}, {_duration(booked)} booked" if count else "Nothing booked", "good": booked <= 240})

    # Timing: how soon the job could start, which matters most for urgent work.
    wait = max(0.0, (start - ensure_utc(now)).total_seconds() / 60)
    scale = WAIT_SCALE.get(order["priority"], 480)
    parts["timing"] = POINTS["timing"] * max(0.0, 1 - wait / scale)
    ahead = [task for task in tasks if task.get("endAt") and ensure_utc(task["endAt"]) <= start and task.get("priority") and PRIORITY_RANK.get(task["priority"], 4) > PRIORITY_RANK.get(order["priority"], 4)]
    behind_lower = f", behind lower-priority {ahead[-1]['id']}" if ahead and order["priority"] in URGENT else ""
    factors.append({"label": "Start", "value": ("Can start now" if wait <= 15 else f"Free from {local_time(start)}") + behind_lower, "good": wait <= scale / 4 and not behind_lower})

    # Shift: how much of the shift is left after the job.
    covering = next((span for span in shifts if ensure_utc(span["startAt"]) <= start and ensure_utc(span["endAt"]) >= end), None)
    if inside and covering:
        margin = (ensure_utc(covering["endAt"]) - end).total_seconds() / 60
        parts["shift"] = POINTS["shift"] * min(1.0, margin / 120)
        factors.append({"label": "Shift", "value": f"{_duration(margin)} to spare in the shift", "good": True})
    else:
        parts["shift"] = 0
        factors.append({"label": "Shift", "value": "Outside the shift", "good": False})

    # Proximity: already working in this building, or one nearby.
    here = order.get("buildingId")
    near = None
    for task in tasks:
        gap = 0.0 if task.get("buildingId") == here else distance(task.get("buildingId"), here)
        if gap is not None and (near is None or gap < near):
            near = gap
    if near is None:
        parts["proximity"] = POINTS["proximity"] / 2
        factors.append({"label": "Location", "value": "Not on a job right now", "good": True})
    elif near == 0:
        parts["proximity"] = POINTS["proximity"]
        factors.append({"label": "Location", "value": "Already working in this building", "good": True})
    elif near <= NEARBY_DISTANCE:
        parts["proximity"] = POINTS["proximity"] * 0.6
        factors.append({"label": "Location", "value": "Working in a nearby block", "good": True})
    else:
        parts["proximity"] = POINTS["proximity"] * 0.2
        factors.append({"label": "Location", "value": "Working across campus", "good": False})

    return {"total": round(sum(parts.values())), "factors": factors, "parts": {key: round(value, 1) for key, value in parts.items()}}
