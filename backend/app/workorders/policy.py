"""What a job of each kind needs. A policy table, not a model: assumption A15 in docs/ASSUMPTIONS.md.

Skills, durations and safety notes are inputs to the ranking and to the collision engine. They are
data a Facilities Administrator would tune, and nothing here decides who gets a job.
"""

# category: (skill code, minimum level)
SKILL_FOR = {
    "ELECTRICAL": ("ELECTRICAL", 2),
    "NETWORK": ("NETWORK", 2),
    "PLUMBING": ("PLUMBING", 2),
    "HVAC": ("HVAC", 2),
    "CARPENTRY": ("CARPENTRY", 1),
    "EQUIPMENT": ("GENERAL", 1),
    "HOUSEKEEPING": ("GENERAL", 1),
    "SAFETY": ("GENERAL", 1),
    "OTHER": ("GENERAL", 1),
}

ESTIMATE_MINUTES = {
    "ELECTRICAL": 90,
    "NETWORK": 60,
    "PLUMBING": 60,
    "HVAC": 90,
    "CARPENTRY": 60,
    "EQUIPMENT": 45,
    "HOUSEKEEPING": 30,
    "SAFETY": 60,
    "OTHER": 45,
}

SAFETY_NOTE = {
    "ELECTRICAL": "Switch off and lock out the supply before opening any panel. Test that it is dead.",
    "HVAC": "Isolate the unit at the breaker. Do not open the refrigerant circuit without gloves and goggles.",
    "PLUMBING": "Close the nearest isolation valve first, and check for wet floors near electrics.",
    "NETWORK": "Work on a powered-down switch where you can, and label cables before you move them.",
    "SAFETY": "Make the area safe first and keep people out of it until it has been checked.",
}

# Priority -> minutes a job can wait before the "can start soon" part of its ranking is worth nothing.
WAIT_SCALE = {"P1": 60, "P2": 120, "P3": 480, "P4": 960}
URGENT = ("P1", "P2")
PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}

# How far ahead a job is planned, and the slack before a late job is flagged.
PLANNING_HORIZON_HOURS = 72
LATE_GRACE_MINUTES = 15
NOT_ACCEPTED_MINUTES = {"P1": 10, "P2": 30, "P3": 120, "P4": 240}

# Points for each part of the ranking. They add up to 100.
POINTS = {"skill": 30, "workload": 25, "timing": 20, "shift": 15, "proximity": 10}
