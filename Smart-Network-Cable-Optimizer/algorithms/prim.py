"""Prim's Algorithm - implemented from scratch (adjacency list + binary min-heap).

Greedy idea: grow a single tree from a start vertex. At every step pick the
cheapest edge that leaves the tree (cut property) and add its new endpoint.
Lazy variant: edges are pushed when a vertex joins the tree; stale entries
(whose far endpoint has meanwhile joined) are discarded when popped.

Time : O((V + E) log V)  with a binary heap (heap holds at most E entries)
Space: O(V + E)          adjacency list + heap + visited set

For a disconnected graph the algorithm is restarted from every unvisited vertex
and returns a minimum spanning *forest*; `connected` is then False.
"""
from __future__ import annotations

import heapq
import time
from typing import Any, Iterable, Optional, Sequence

from .common import (PRIM_SPACE, PRIM_TIME, GraphError, Edge, MSTResult,
                     normalize_edges)


def prim_mst(nodes: Sequence, edges: Iterable, start: Optional[Any] = None,
             record_steps: bool = True) -> MSTResult:
    node_list = list(nodes)
    edge_list = normalize_edges(node_list, edges)
    if start is not None and start not in set(node_list):
        raise GraphError(f"Start vertex {start!r} is not in the graph")

    t0 = time.perf_counter()

    # --- adjacency list ---------------------------------------------------
    adj = {n: [] for n in node_list}
    for e in edge_list:
        adj[e.u].append((e.weight, e.v, e.eid))
        adj[e.v].append((e.weight, e.u, e.eid))

    visited = set()
    mst: list = []
    steps: list = []
    roots: list = []
    total = 0.0
    processed = 0
    rejected = 0
    seq = 0  # tie-breaker so heap never compares vertices; keeps output deterministic

    order = node_list if start is None else [start] + [n for n in node_list if n != start]
    for root in order:
        if root in visited:
            continue
        roots.append(root)
        visited.add(root)
        heap: list = []
        for w, nb, eid in adj[root]:
            heapq.heappush(heap, (w, seq, root, nb, eid))
            seq += 1
        while heap:
            w, _, u, v, eid = heapq.heappop(heap)
            processed += 1
            if v in visited:
                rejected += 1
                if record_steps:
                    steps.append({
                        "step": len(steps) + 1, "edge_id": eid, "u": u, "v": v, "weight": w,
                        "status": "rejected",
                        "reason": "Both endpoints are already in the tree - adding it would create a cycle",
                        "mst_cost": total, "selected_count": len(mst),
                        "info": f"heap size: {len(heap)}"})
                continue
            visited.add(v)
            mst.append(Edge(u, v, w, eid))
            total += w
            if record_steps:
                steps.append({
                    "step": len(steps) + 1, "edge_id": eid, "u": u, "v": v, "weight": w,
                    "status": "selected",
                    "reason": "Cheapest edge leaving the current tree - connects a new vertex",
                    "mst_cost": total, "selected_count": len(mst),
                    "info": f"tree size: {len(visited)}"})
            for w2, nb, eid2 in adj[v]:
                if nb not in visited:
                    heapq.heappush(heap, (w2, seq, v, nb, eid2))
                    seq += 1

    elapsed = time.perf_counter() - t0
    return MSTResult(
        algorithm="Prim's Algorithm", mst_edges=mst, total_cost=total,
        connected=len(roots) <= 1, num_components=len(roots),
        num_nodes=len(node_list), num_edges=len(edge_list), steps=steps,
        execution_time=elapsed, edges_processed=processed, edges_rejected=rejected,
        time_complexity=PRIM_TIME, space_complexity=PRIM_SPACE,
        extra={"roots": roots})
