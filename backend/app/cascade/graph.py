"""Breadth-first walk over dependency edges. Pure: it takes the edges in memory and reads nothing else.

A visited set makes cycles terminate, and the depth limit bounds the walk on a graph nobody has
checked for mistakes. Each reached node remembers the edge it was reached by, so every line of an
impact chain can say why it is there.
"""

from collections import deque
from dataclasses import dataclass
from typing import Any

MAX_DEPTH = 6


@dataclass(frozen=True)
class Reached:
    kind: str  # ASSET or ROOM
    id: str
    depth: int
    via_id: str | None = None
    relation: str | None = None


def adjacency(edges: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        if edge.get("active", True):
            out.setdefault((edge["fromType"], edge["fromId"]), []).append(edge)
    for targets in out.values():
        targets.sort(key=lambda edge: (edge["toType"], edge["toId"]))  # stable order, so results are repeatable
    return out


def walk(edges: list[dict[str, Any]], roots: list[tuple[str, str]], max_depth: int = MAX_DEPTH) -> list[Reached]:
    """Every node reachable from the roots, nearest first. A root is (kind, id)."""
    graph = adjacency(edges)
    seen: set[tuple[str, str]] = set()
    order: list[Reached] = []
    queue: deque[Reached] = deque()
    for kind, node_id in roots:
        if (kind, node_id) not in seen:
            seen.add((kind, node_id))
            queue.append(Reached(kind, node_id, 0))
    while queue:
        node = queue.popleft()
        order.append(node)
        if node.depth >= max_depth:
            continue
        for edge in graph.get((node.kind, node.id), []):
            key = (edge["toType"], edge["toId"])
            if key not in seen:
                seen.add(key)
                queue.append(Reached(edge["toType"], edge["toId"], node.depth + 1, node.id, edge["relation"]))
    return order
