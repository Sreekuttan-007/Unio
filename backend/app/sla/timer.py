"""The pure arithmetic of an SLA clock: state and remaining time from stored timestamps.

Kept apart from sla/service.py (which writes sla_instances) so anything read-only, including the
simulator's planner, can use it without importing a module the import-boundary test treats as a
write path. Nothing here reads or writes a database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.core.clock import ensure_utc, utcnow

AT_RISK_PERCENT = 75


def duration(minutes: float) -> str:
    total = abs(round(minutes))
    if total < 60:
        return f"{total} min"
    hours, rest = divmod(total, 60)
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def evaluate(instance: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """State, percentage used, and wording, from the stored times. Pure, so it is easy to test."""
    now = ensure_utc(now or utcnow())
    started = ensure_utc(instance["startedAt"])
    window = instance["resolutionMinutes"]
    paused = float(instance.get("pausedMinutes", 0))
    open_pause = next((pause for pause in instance.get("pauses", []) if pause.get("to") is None), None)
    resolved_at = ensure_utc(instance["resolvedAt"]) if instance.get("resolvedAt") else None
    end = resolved_at or now
    if open_pause and not resolved_at:
        paused += (now - ensure_utc(open_pause["from"])).total_seconds() / 60
    elapsed = max(0.0, (end - started).total_seconds() / 60 - paused)
    percent = elapsed / window * 100 if window else 0
    due = started + timedelta(minutes=window + paused)
    remaining = window - elapsed
    if resolved_at:
        state = "MET" if percent <= 100 else "BREACHED"
        text = "Closed within target" if state == "MET" else f"Closed {duration(elapsed - window)} late"
    elif open_pause:
        state, text = "PAUSED", f"Paused: {open_pause.get('reason', 'waiting')}"
    elif percent >= 100:
        state, text = "BREACHED", f"overdue by {duration(-remaining)}"
    elif percent >= instance.get("atRiskPercent", AT_RISK_PERCENT):
        state, text = "AT_RISK", f"{duration(remaining)} left"
    else:
        state, text = "ON_TRACK", f"{duration(remaining)} left"
    return {"state": state, "percentElapsed": round(min(percent, 999)), "remaining": text, "dueAt": due.isoformat()}
