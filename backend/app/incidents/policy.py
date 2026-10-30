"""How urgent a thing is, decided by a table, never by a model.

AI supplies the category and the urgency it read from the text. This table turns those into a
priority, and nothing a reporter writes can change the table.
"""

RANK = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
BY_URGENCY = {"CRITICAL": "P1", "HIGH": "P2", "MEDIUM": "P3", "LOW": "P4"}
MANY_REPORTS = 5


def _raise(priority: str) -> str:
    return {"P4": "P3", "P3": "P2", "P2": "P1", "P1": "P1"}[priority]


def priority_for(category: str, urgency: str, report_count: int, *, exams_affected: int = 0, current: str | None = None) -> str:
    """Never lowers an existing priority: new information can only make something more urgent."""
    priority = BY_URGENCY.get(urgency, "P3")
    if category == "SAFETY" and RANK[priority] > RANK["P2"]:
        priority = "P2"
    if report_count >= MANY_REPORTS:
        priority = _raise(priority)
    if exams_affected and RANK[priority] > RANK["P1"]:
        priority = "P1" if RANK[priority] <= RANK["P2"] else _raise(priority)
    if current and RANK[current] < RANK[priority]:
        return current
    return priority
