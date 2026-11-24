"""Independent verification helpers (cycle detection, connectivity, MST validity)."""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence

from .dsu import DSU


def connected_components(nodes: Sequence, edges: Iterable) -> List[list]:
    """Connected components as lists of vertices, largest first."""
    nodes = list(nodes)
    index = {n: i for i, n in enumerate(nodes)}
    dsu = DSU(nodes)
    for e in edges:
        dsu.union(e[0], e[1])
    groups = [sorted(g, key=index.get) for g in dsu.groups().values()]
    groups.sort(key=lambda g: (-len(g), index[g[0]]))
    return groups


def is_connected(nodes: Sequence, edges: Iterable) -> bool:
    return len(connected_components(nodes, edges)) <= 1


def has_cycle(nodes: Sequence, edges: Iterable) -> bool:
    """True if the undirected edge set contains a cycle (DSU based)."""
    dsu = DSU(nodes)
    for e in edges:
        if not dsu.union(e[0], e[1]):
            return True
    return False


def verify_mst(nodes: Sequence, graph_edges: Iterable, result) -> Dict[str, bool]:
    """Check that `result` is a valid minimum-spanning tree/forest *structure*."""
    nodes = list(nodes)
    graph_edges = list(graph_edges)
    mst = result.mst_edges
    graph_components = len(connected_components(nodes, graph_edges))
    mst_components = len(connected_components(nodes, mst))
    checks = {
        "Edge count = V - components": len(mst) == len(nodes) - graph_components if nodes else len(mst) == 0,
        "No cycles": not has_cycle(nodes, mst),
        "Spans every building": mst_components == graph_components,
        "Cost equals sum of edges": math.isclose(sum(e[2] for e in mst), result.total_cost, abs_tol=1e-6),
    }
    checks["Valid MST"] = all(checks.values())
    return checks
