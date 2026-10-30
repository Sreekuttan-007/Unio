"""Pulls place, asset and missing details out of a report, using the campus itself as the reference.

Location is matched against the real room and building records, so a room that does not exist is
caught, not guessed. Typos in building names are forgiven with a fuzzy match.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz, process

from app.ml.triage import TriageModel, classify, urgency

ROOM_CODE = re.compile(r"\b([a-z]{3})\s?-?\s?(\d{3})\b", re.IGNORECASE)

EXTRA_ALIASES = {
    "library": "B-LIB", "lib": "B-LIB", "cafeteria": "B-CAF", "canteen": "B-CAF", "pavilion": "B-CAF", "mess": "B-CAF",
    "hostel": "B-KLH", "kalam": "B-KLH", "admin": "B-ADM", "administration": "B-ADM", "auditorium": "B-ADM", "seminar": "B-ADM",
    "raman": "B-RLB", "research": "B-RLB",
}

ASSETS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("projector",), "Projector"),
    (("wifi", "wi-fi", "access point"), "Wi-Fi access point"),
    (("air conditioner", "split ac", " ac "), "Air conditioner"),
    (("tube light", "tubelight", "bulb"), "Light fitting"),
    (("ceiling fan", " fan "), "Ceiling fan"),
    (("tap",), "Tap"),
    (("socket", "plug point"), "Socket"),
    (("microphone", " mic "), "Microphone"),
    (("switch board", "switchboard", "panel", "mcb"), "Power panel"),
    (("door",), "Door"),
    (("printer",), "Printer"),
    (("water cooler",), "Water cooler"),
)


@dataclass
class Gazetteer:
    rooms: dict[str, dict[str, Any]] = field(default_factory=dict)
    buildings: dict[str, dict[str, Any]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)


async def load_gazetteer(db: Any) -> Gazetteer:
    rooms = {room["_id"]: room async for room in db["rooms"].find({})}
    buildings = {building["_id"]: building async for building in db["buildings"].find({})}
    aliases: dict[str, str] = {}
    for building_id, building in buildings.items():
        aliases[building["code"].lower()] = building_id
        for word in re.findall(r"[a-z]+", building["name"].lower()):
            if len(word) >= 5 and word not in ("block", "research", "labs", "seminar", "administration", "pavilion", "sports", "hall"):
                aliases.setdefault(word, building_id)
    for alias, building_id in EXTRA_ALIASES.items():
        if building_id in buildings:
            aliases[alias] = building_id
    return Gazetteer(rooms, buildings, aliases)


@dataclass
class Location:
    room_code: str | None = None
    building_id: str | None = None
    building_name: str | None = None
    unknown_room: str | None = None

    @property
    def text(self) -> str:
        if self.room_code and self.building_name:
            return f"{self.room_code}, {self.building_name}"
        return self.building_name or ""


def locate(text: str, gaz: Gazetteer) -> Location:
    unknown: str | None = None
    for prefix, digits in ROOM_CODE.findall(text):
        code = f"{prefix.upper()}-{digits}"
        if code in gaz.rooms:
            building = gaz.buildings.get(gaz.rooms[code]["buildingId"], {})
            return Location(code, gaz.rooms[code]["buildingId"], building.get("name"))
        if prefix.lower() in gaz.aliases:
            unknown = code
            building_id = gaz.aliases[prefix.lower()]
            return Location(None, building_id, gaz.buildings[building_id]["name"], unknown_room=code)
    words = re.findall(r"[a-z]+", text.lower())
    for word in words:
        if word in gaz.aliases:
            building_id = gaz.aliases[word]
            return Location(None, building_id, gaz.buildings[building_id]["name"])
    long_aliases = [alias for alias in gaz.aliases if len(alias) >= 6]
    for word in words:
        if len(word) >= 6:
            match = process.extractOne(word, long_aliases, scorer=fuzz.ratio, score_cutoff=86)
            if match:
                building_id = gaz.aliases[match[0]]
                return Location(None, building_id, gaz.buildings[building_id]["name"])
    return Location(unknown_room=unknown)


def find_asset(text: str) -> str | None:
    lower = f" {text.lower()} "
    for needles, name in ASSETS:
        if any(needle in lower for needle in needles):
            return name
    return None


def build_extraction(text: str, gaz: Gazetteer, model: TriageModel | None) -> dict[str, Any]:
    """Everything the screen needs except the duplicate check, which needs the database."""
    category, confidence, source, version = classify(text, model)
    place = locate(text, gaz)
    clarification: str | None = None
    if place.unknown_room and not place.room_code:
        clarification = f"I could not find room {place.unknown_room}. Which room or building is it in?"
    elif not place.building_id:
        clarification = "Which room or building is this in? Add a room code such as ARB-204."
    elif len(text.split()) < 3:
        clarification = "Can you say a little more about what is wrong?"
    return {
        "category": category,
        "categoryConfidence": round(confidence, 2),
        "urgency": urgency(text, category),
        "location": {"text": place.text, "roomCode": place.room_code, "buildingName": place.building_name},
        "asset": find_asset(text),
        "clarification": clarification,
        "duplicate": None,
        "source": "AI" if source == "ML" else "RULE",
        "modelVersion": version,
        "buildingId": place.building_id,
    }
