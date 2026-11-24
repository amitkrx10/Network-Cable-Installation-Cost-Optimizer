"""Shared data structures and input validation for the MST algorithms."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, NamedTuple, Sequence

PRIM_TIME = "O((V + E) log V)"
PRIM_SPACE = "O(V + E)"
KRUSKAL_TIME = "O(E log E)  (= O(E log V))"
KRUSKAL_SPACE = "O(V + E)"


class GraphError(ValueError):
    """Raised for invalid graph input (unknown vertex, self-loop, negative weight...)."""


class Edge(NamedTuple):
    u: Any
    v: Any
    weight: float
    eid: Any = None


def normalize_edges(nodes: Sequence, edges: Iterable) -> List[Edge]:
    """Validate and convert raw edges to Edge tuples.

    Accepts (u, v, w) or (u, v, w, eid) tuples or Edge objects.
    Raises GraphError for unknown vertices, self-loops, NaN/inf or negative weights.
    """
    node_set = set(nodes)
    if len(node_set) != len(nodes):
        raise GraphError("Duplicate vertex identifiers in node list")
    out: List[Edge] = []
    for i, e in enumerate(edges):
        if len(e) == 3:
            u, v, w = e
            eid = i
        elif len(e) == 4:
            u, v, w, eid = e
            if eid is None:
                eid = i
        else:
            raise GraphError(f"Edge #{i} must be (u, v, weight[, id])")
        if u not in node_set or v not in node_set:
            raise GraphError(f"Edge {u!r}-{v!r} references an unknown vertex")
        if u == v:
            raise GraphError(f"Self-loop on vertex {u!r} is not allowed")
        try:
            w = float(w)
        except (TypeError, ValueError):
            raise GraphError(f"Edge {u!r}-{v!r} has a non-numeric weight") from None
        if not math.isfinite(w):
            raise GraphError(f"Edge {u!r}-{v!r} has a non-finite weight")
        if w < 0:
            raise GraphError(f"Edge {u!r}-{v!r} has a negative weight ({w})")
        out.append(Edge(u, v, w, eid))
    return out


@dataclass
class MSTResult:
    algorithm: str
    mst_edges: List[Edge]
    total_cost: float
    connected: bool
    num_components: int
    num_nodes: int
    num_edges: int
    steps: List[Dict[str, Any]]
    execution_time: float  # seconds (time.perf_counter)
    edges_processed: int
    edges_rejected: int
    time_complexity: str
    space_complexity: str
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def selected_count(self) -> int:
        return len(self.mst_edges)

    @property
    def execution_time_ms(self) -> float:
        return self.execution_time * 1000.0
