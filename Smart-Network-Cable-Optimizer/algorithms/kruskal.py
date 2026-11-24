"""Kruskal's Algorithm - implemented from scratch with a Disjoint Set Union.

Greedy idea: sort all edges by weight; scan them in ascending order and keep an
edge only if it joins two different components (checked with DSU find()).
The scan stops early as soon as V-1 edges have been chosen.

Time : O(E log E) for sorting  (+ O(E * alpha(V)) for the DSU operations)
Space: O(V + E)

For a disconnected graph the result is a minimum spanning forest and
`connected` is False.
"""
from __future__ import annotations

import time
from typing import Iterable, Sequence

from .common import (KRUSKAL_SPACE, KRUSKAL_TIME, Edge, MSTResult,
                     normalize_edges)
from .dsu import DSU


def kruskal_mst(nodes: Sequence, edges: Iterable, record_steps: bool = True) -> MSTResult:
    node_list = list(nodes)
    edge_list = normalize_edges(node_list, edges)

    t0 = time.perf_counter()
    sorted_edges = sorted(edge_list, key=lambda e: e.weight)  # stable: ties keep input order
    dsu = DSU(node_list)
    target = len(node_list) - 1

    mst: list = []
    steps: list = []
    total = 0.0
    processed = 0
    rejected = 0

    for e in sorted_edges:
        if len(mst) == target:  # tree complete - remaining edges are never examined
            break
        processed += 1
        if dsu.union(e.u, e.v):
            mst.append(e)
            total += e.weight
            if record_steps:
                steps.append({
                    "step": len(steps) + 1, "edge_id": e.eid, "u": e.u, "v": e.v,
                    "weight": e.weight, "status": "selected",
                    "reason": "Connects two different components - no cycle is formed",
                    "mst_cost": total, "selected_count": len(mst),
                    "info": f"components left: {dsu.components}"})
        else:
            rejected += 1
            if record_steps:
                steps.append({
                    "step": len(steps) + 1, "edge_id": e.eid, "u": e.u, "v": e.v,
                    "weight": e.weight, "status": "rejected",
                    "reason": "Both endpoints are already in the same component - it would create a cycle",
                    "mst_cost": total, "selected_count": len(mst),
                    "info": f"components left: {dsu.components}"})

    elapsed = time.perf_counter() - t0
    return MSTResult(
        algorithm="Kruskal's Algorithm", mst_edges=mst, total_cost=total,
        connected=dsu.components <= 1, num_components=dsu.components,
        num_nodes=len(node_list), num_edges=len(edge_list), steps=steps,
        execution_time=elapsed, edges_processed=processed, edges_rejected=rejected,
        time_complexity=KRUSKAL_TIME, space_complexity=KRUSKAL_SPACE,
        extra={"sorted_edges": sorted_edges})
