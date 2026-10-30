"""The drawn campus: where each building sits on the map, and the roads and greens around it.

Positions live in data (the campus_map collection), not in a component, so the map can be
re-calibrated without touching the frontend.

The shapes below trace the real SRM Easwari Engineering College (EEC) campus map. Eight of the
named buildings are bound 1:1 to the eight operational buildings this app already models
(`BUILDINGS` in `app/campus/seed.py`) - their `_id`/`code`/room numbering are unchanged from the
original fictional campus, so every existing room code, asset id and test that depends on them
(for example `ARB-204`, `AST-TR-ARB`) keeps working. Only each building's display name and its
position on the map changed, to the real EEC block it now stands in for. Every other real block,
hostel, road and green space on campus is drawn too, as background scenery, so the map looks like
the real place even though only eight of its buildings carry live operational data today.
"""

from typing import Any

MAP_ID = "MAP-1"
MAP_VERSION = 2
VIEW_W = 1600
VIEW_H = 1195


def _polygon(points: str) -> tuple[str, int, int, int, int]:
    """Turns an SVG `points` attribute into a path `d` string and its bounding box."""
    pairs = [tuple(float(n) for n in pair.split(",")) for pair in points.split()]
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    d = "M" + " L".join(f"{x:g},{y:g}" for x, y in pairs) + " Z"
    return d, round(min(xs)), round(min(ys)), round(max(xs) - min(xs)), round(max(ys) - min(ys))


def _bbox(points: str) -> tuple[int, int, int, int]:
    _d, x, y, w, h = _polygon(points)
    return x, y, w, h


# The real, non-rectangular footprint of a bound building, keyed by regionId. Everything else
# below is a plain rectangle.
_BUILDING_OUTLINE: dict[str, str] = {
    "EEC-MAIN": "340,490 380,450 450,450 495,500 495,590 450,600 400,610 340,605 330,540",
    "ACAD-1": "1368,532 1414,532 1414,836 1348,836 1350,770 1368,748",
    "IST-8": "1362,270 1395,268 1395,300 1400,395 1470,425 1470,450 1425,478 1400,455 1385,448 1350,445 1350,405 1362,380",
    "WORKSHOP": "1360,112 1455,108 1487,150 1485,178 1358,160",
    "BOYS-8": "1158,143 1230,145 1228,190 1190,192 1192,215 1225,205 1225,260 1262,262 1292,300 1290,347 1170,318 1170,285 1150,280",
}

# regionId, building id, label, bounding box (x, y, w, h) — all eight buildings this app has
# operational data for, each bound to the real EEC block closest in role (academic / lab /
# library / admin / common / hostel) to what it already represents. Three are plain rectangles;
# the other five (see _BUILDING_OUTLINE above) draw their real, non-rectangular footprint but
# still carry a bounding box here, because this table is also how the rest of the backend (for
# example the technician-proximity scoring in app/workorders/scoring.py) finds a building's
# position on the map - every consumer of BUILDING_REGIONS needs all eight, not just the
# rectangular ones.
BUILDING_REGIONS: tuple[tuple[str, str, str, int, int, int, int], ...] = (
    ("EEC-MAIN", "B-ARB", "EEC Main Block", *_bbox(_BUILDING_OUTLINE["EEC-MAIN"])),
    ("ELEC-2", "B-BHB", "Electronics Block 2", 755, 537, 127, 70),
    ("ACAD-1", "B-RMB", "Academic Block 1", *_bbox(_BUILDING_OUTLINE["ACAD-1"])),
    ("ELEC-1", "B-RLB", "Electronics Block 1", 645, 548, 100, 55),
    ("IST-8", "B-LIB", "Institute of Science & Technology", *_bbox(_BUILDING_OUTLINE["IST-8"])),
    ("BMS-12", "B-ADM", "New BMS Block", 938, 376, 174, 127),
    ("WORKSHOP", "B-CAF", "Workshop", *_bbox(_BUILDING_OUTLINE["WORKSHOP"])),
    ("BOYS-8", "B-KLH", "Boys Hostel", *_bbox(_BUILDING_OUTLINE["BOYS-8"])),
)

# building id -> regionId, so the seed script can bind each building document to its real place
# on the map without duplicating this table.
REGION_ID_FOR_BUILDING: dict[str, str] = {building_id: region_id for region_id, building_id, *_rest in BUILDING_REGIONS}

# The rest of the real campus: named blocks with no live operational data behind them yet,
# drawn as scenery so the map is recognisably the real place. kind, label, rect-or-points.
_SCENERY_RECTS: tuple[tuple[str, int, int, int, int], ...] = (
    ("Block 13 (north)", 920, 312, 120, 50),
    ("SRMIST Admin Block", 1050, 335, 60, 42),
    ("Block 13 (south)", 900, 522, 75, 106),
    ("PG Block 1", 978, 535, 114, 25),
    ("General Hospital", 1138, 442, 77, 226),
    ("General Hospital / SRM Prime Hospital", 1218, 465, 107, 207),
    ("SRM Dental College", 924, 650, 166, 52),
    ("Block 10", 925, 703, 55, 38),
    ("Chellammal Ladies Hostel", 133, 795, 117, 53),
    ("Sivasakthi Ladies Hostel", 273, 790, 132, 60),
    ("Block 3", 1246, 706, 66, 132),
    ("Block 23 (strip)", 118, 622, 110, 25),
)
_SCENERY_POLY: tuple[tuple[str, str], ...] = (
    ("PG Block 2", "975,595 1075,595 1075,598 1090,598 1090,632 975,632"),
    ("PG, Civil & Mechanical Block", "468,805 520,800 560,820 690,845 815,885 810,910 700,890 560,860 468,832"),
    ("Academic Block 2", "1442,502 1476,502 1476,812 1450,826 1442,820"),
    ("Academic Block 4", "1168,707 1235,707 1235,850 1170,850"),
    ("Dental Hospital", "927,797 1000,797 1000,725 1092,725 1092,797 1065,797 1065,878 927,878"),
    ("Block 9", "1168,322 1290,348 1286,398 1186,398 1166,380"),
    ("Hostel Block 20", "108,645 145,645 165,628 195,645 237,655 255,685 240,710 248,740 245,780 215,790 175,800 140,790 95,780 85,750 95,720 82,695 90,665"),
    ("Block 23 (north)", "230,553 284,553 284,613 262,613 258,640 252,613 230,613"),
)
_GREEN_RECTS: tuple[tuple[str, int, int, int, int], ...] = (
    ("Park", 770, 445, 135, 75),  # approximate rect for the small park near the Electronics blocks
    ("Park", 895, 885, 215, 90),
)
_GREEN_POLY: tuple[tuple[str, str], ...] = (
    ("Lawn", "908,145 1150,145 1148,318 1125,320 1040,300 908,300"),
    ("EEC Courtyard", "378,498 440,498 440,520 425,520 425,545 440,545 440,570 378,570"),
    ("Open Air Theatre (OAT)", "465,718 500,685 560,665 620,663 680,676 680,820 692,836 600,810 540,795 500,785 470,750"),
    ("EEC Playground / Sports Complex", "1487,430 1600,430 1600,940 1487,940"),
)
_ROAD_POLY: tuple[str, ...] = (
    "0,822 120,835 400,935 700,980 860,1000 1100,1000 1400,985 1600,945 1600,1005 1400,1042 1100,1052 870,1054 700,1036 400,962 0,882",
    "908,105 1325,92 1345,120 1325,125 908,150",
    "1330,165 1362,165 1375,470 1328,470",
    "1315,445 1342,448 1344,880 1318,880",
    "1442,0 1478,0 1600,230 1600,278 1440,60",
    "1112,365 1140,365 1140,972 1112,972",
    "258,648 500,596 500,520 545,535 640,545 645,598 760,606 900,628 900,650 1138,650 1138,682 905,682 905,975 862,975 862,832 832,832 832,690 420,690 258,665",
    "415,950 445,950 432,1080 400,1080",
    "1225,1030 1250,1030 1247,1085 1222,1085",
)
_ROAD_RECTS: tuple[tuple[int, int, int, int], ...] = ((920, 1050, 45, 43),)


def build_map_document() -> dict[str, Any]:
    regions = []
    for region_id, building_id, label, x, y, w, h in BUILDING_REGIONS:
        outline = _BUILDING_OUTLINE.get(region_id)
        shape = {"type": "path", "d": _polygon(outline)[0], "x": x, "y": y, "w": w, "h": h} if outline else {"type": "rect", "x": x, "y": y, "w": w, "h": h, "r": 10}
        regions.append({"regionId": region_id, "entityType": "BUILDING", "entityId": building_id, "label": label, "shape": shape})

    decor: list[dict[str, Any]] = []
    for _label, x, y, w, h in _SCENERY_RECTS:
        decor.append({"kind": "path", "x": x, "y": y, "w": w, "h": h})
    for _label, points in _SCENERY_POLY:
        d, x, y, w, h = _polygon(points)
        decor.append({"kind": "path", "d": d, "x": x, "y": y, "w": w, "h": h})
    for _label, x, y, w, h in _GREEN_RECTS:
        decor.append({"kind": "green", "x": x, "y": y, "w": w, "h": h, "r": 12})
    for _label, points in _GREEN_POLY:
        d, x, y, w, h = _polygon(points)
        decor.append({"kind": "green", "d": d, "x": x, "y": y, "w": w, "h": h})
    for points in _ROAD_POLY:
        d, x, y, w, h = _polygon(points)
        decor.append({"kind": "road", "d": d, "x": x, "y": y, "w": w, "h": h})
    for x, y, w, h in _ROAD_RECTS:
        decor.append({"kind": "road", "x": x, "y": y, "w": w, "h": h})

    return {
        "_id": MAP_ID,
        "version": MAP_VERSION,
        "viewBox": {"w": VIEW_W, "h": VIEW_H},
        "decor": decor,
        "regions": regions,
    }
