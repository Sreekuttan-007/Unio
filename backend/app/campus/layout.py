"""The drawn campus: where each building sits on the map, and the roads and greens around it.

Positions live in data (the campus_map collection), not in a component, so the map can be
re-calibrated without touching the frontend. The campus is fictional (PS constraint C2).
"""

from typing import Any

MAP_ID = "MAP-1"
MAP_VERSION = 1
VIEW_W = 1200
VIEW_H = 760

# regionId, building id, label, x, y, width, height
BUILDING_REGIONS: tuple[tuple[str, str, str, int, int, int, int], ...] = (
    ("bld-arb", "B-ARB", "Aryabhata Block", 110, 120, 270, 150),
    ("bld-bhb", "B-BHB", "Bhaskara Block", 110, 330, 270, 130),
    ("bld-rmb", "B-RMB", "Ramanujan Block", 440, 120, 250, 150),
    ("bld-rlb", "B-RLB", "Raman Research Labs", 440, 330, 250, 130),
    ("bld-lib", "B-LIB", "Central Library", 750, 120, 190, 150),
    ("bld-caf", "B-CAF", "Cafeteria and Sports Pavilion", 750, 330, 190, 130),
    ("bld-klh", "B-KLH", "Kalam Hostel", 1000, 120, 150, 340),
    ("bld-adm", "B-ADM", "Administration and Seminar Hall", 440, 540, 250, 120),
)

# kind is one of: road, path, green, water, gate. The frontend styles each kind with tokens.
DECOR: tuple[dict[str, Any], ...] = (
    {"kind": "green", "x": 40, "y": 40, "w": 1120, "h": 680, "r": 28},
    {"kind": "road", "x": 40, "y": 292, "w": 1120, "h": 24},
    {"kind": "road", "x": 40, "y": 492, "w": 1120, "h": 24},
    {"kind": "road", "x": 396, "y": 40, "w": 24, "h": 680},
    {"kind": "road", "x": 706, "y": 40, "w": 24, "h": 680},
    {"kind": "road", "x": 960, "y": 40, "w": 24, "h": 480},
    {"kind": "water", "x": 110, "y": 540, "w": 250, "h": 120, "r": 60},
    {"kind": "green", "x": 750, "y": 540, "w": 200, "h": 120, "r": 20},
    {"kind": "gate", "x": 540, "y": 690, "w": 50, "h": 22, "r": 6},
)


def build_map_document() -> dict[str, Any]:
    regions = [
        {
            "regionId": region_id,
            "entityType": "BUILDING",
            "entityId": building_id,
            "label": label,
            "shape": {"type": "rect", "x": x, "y": y, "w": w, "h": h, "r": 14},
        }
        for region_id, building_id, label, x, y, w, h in BUILDING_REGIONS
    ]
    return {
        "_id": MAP_ID,
        "version": MAP_VERSION,
        "viewBox": {"w": VIEW_W, "h": VIEW_H},
        "decor": [dict(item) for item in DECOR],
        "regions": regions,
    }
