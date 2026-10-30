"""When an action is refused, offer something that would work.

Every suggestion is judged by the same engine as the original, so nothing is offered that the
engine would then refuse. Suggestions are advice. They change nothing.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta
from typing import Any

from app.collision.engine import CollisionEngine, RuleConfig
from app.collision.models import ROOM_ACTIONS, ActionType, CollisionResult, Decision, ProposedAction
from app.collision.reader import StateReader
from app.core.clock import local_time

ROOM_PROBLEMS = {"ROOM_OVERLAP", "ROOM_CLOSED", "ROOM_CAPACITY", "ROOM_UNKNOWN", "ROOM_NOT_BOOKABLE", "ASSET_DOWN", "ROOM_TYPE"}
MAX_SUGGESTIONS = 3
ROOM_CANDIDATES_TRIED = 40
TIME_STEP = timedelta(minutes=30)
TIME_STEPS_TRIED = 16


class AlternativeSuggestionService:
    def __init__(self, engine: CollisionEngine) -> None:
        self._engine = engine

    async def suggest(self, action: ProposedAction, result: CollisionResult, reader: StateReader, config: Mapping[str, RuleConfig] | None = None) -> list[dict[str, Any]]:
        if result.decision is Decision.ALLOW:
            return []
        codes = {finding.code for finding in result.findings}
        if action.type in ROOM_ACTIONS and codes & ROOM_PROBLEMS:
            return await self.rooms(action, reader, config) + await self._times(action, codes, reader, config)
        if action.type is ActionType.ASSIGN_TECHNICIAN:
            return await self._technicians(action, reader, config)
        if action.type is ActionType.RESERVE_PARTS and "STOCK_SHORT" in codes:
            return self._parts(result)
        return []

    async def _passes(self, action: ProposedAction, reader: StateReader, config: Mapping[str, RuleConfig] | None) -> bool:
        return (await self._engine.evaluate(replace(action, expected_state_token=None), reader, config)).decision is Decision.ALLOW

    async def rooms(self, action: ProposedAction, reader: StateReader, config: Mapping[str, RuleConfig] | None = None) -> list[dict[str, Any]]:
        """Other rooms that would take this session or booking, nearest and best fitting first."""
        p = action.payload
        original = await reader.room(p["room_id"])
        found: list[tuple[tuple[bool, int], dict[str, Any]]] = []
        tried = 0
        for room in await reader.candidate_rooms(original["buildingId"] if original else None):
            if room["_id"] == p["room_id"] or room["capacity"] < p["headcount"]:
                continue
            if (p["kind"] == "PRACTICAL") != (room["type"] == "LAB"):
                continue
            tried += 1
            if tried > ROOM_CANDIDATES_TRIED:
                break
            if await self._passes(replace(action, payload={**p, "room_id": room["_id"]}), reader, config):
                same_building = bool(original) and room["buildingId"] == original["buildingId"]
                place = "in the same building" if same_building else f"in {room['buildingId'].removeprefix('B-')} block"
                found.append(
                    (
                        (not same_building, room["capacity"] - p["headcount"]),
                        {
                            "kind": "ROOM", "label": f"Use {room['code']} instead", "roomId": room["_id"],
                            "reason": f"Free from {local_time(p['start_at'])} to {local_time(p['end_at'])}, seats {room['capacity']}, {place}.",
                            "apply": {"roomId": room["_id"]},
                        },
                    )
                )
        found.sort(key=lambda pair: pair[0])
        return [item for _, item in found[:MAX_SUGGESTIONS]]

    async def _times(self, action: ProposedAction, codes: set[str], reader: StateReader, config: Mapping[str, RuleConfig] | None) -> list[dict[str, Any]]:
        if "ROOM_OVERLAP" not in codes:
            return []
        p = action.payload
        length = p["end_at"] - p["start_at"]
        suggestions = []
        for step in range(1, TIME_STEPS_TRIED + 1):
            start = p["start_at"] + TIME_STEP * step
            end = start + length
            if await self._passes(replace(action, payload={**p, "start_at": start, "end_at": end}), reader, config):
                suggestions.append(
                    {
                        "kind": "TIME", "label": f"Move to {local_time(start)} to {local_time(end)}", "roomId": p["room_id"],
                        "reason": f"{p['room_id']} is free then.",
                        "apply": {"startAt": start.isoformat(), "endAt": end.isoformat()},
                    }
                )
                if len(suggestions) == 2:
                    break
        return suggestions

    async def _technicians(self, action: ProposedAction, reader: StateReader, config: Mapping[str, RuleConfig] | None) -> list[dict[str, Any]]:
        p = action.payload
        found: list[tuple[int, dict[str, Any]]] = []
        for tech in await reader.all_technicians():
            if tech["_id"] == p["technician_id"]:
                continue
            if await self._passes(replace(action, payload={**p, "technician_id": tech["_id"]}), reader, config):
                open_tasks = len(await reader.technician_tasks(tech["_id"], exclude_work_order_id=p.get("work_order_id")))
                skills = ", ".join(f"{skill['code']} {skill['level']}" for skill in tech["skills"])
                found.append((open_tasks, {"kind": "TECHNICIAN", "label": f"Assign {tech['name']} instead", "technicianId": tech["_id"], "reason": f"Holds {skills}, is on shift and has {open_tasks} open {'task' if open_tasks == 1 else 'tasks'}.", "apply": {"technicianId": tech["_id"]}}))
        found.sort(key=lambda pair: (pair[0], pair[1]["technicianId"]))
        return [item for _, item in found[:MAX_SUGGESTIONS]]

    @staticmethod
    def _parts(result: CollisionResult) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        for finding in result.findings:
            if finding.code != "STOCK_SHORT":
                continue
            item_id = finding.affected[0][1]
            name, short, free = finding.data["itemName"], finding.data["shortBy"], finding.data["free"]
            suggestions.append({"kind": "PURCHASE_REQUEST", "label": f"Raise a purchase request for {short} x {name}", "itemId": item_id, "reason": "The work order stays blocked until the stock arrives.", "apply": {"itemId": item_id, "qty": short}})
            if free > 0:
                suggestions.append({"kind": "PARTIAL", "label": f"Reserve the {free} that {'is' if free == 1 else 'are'} free now", "itemId": item_id, "reason": "The rest follows once more arrives.", "apply": {"itemId": item_id, "qty": free}})
        return suggestions[:MAX_SUGGESTIONS]
