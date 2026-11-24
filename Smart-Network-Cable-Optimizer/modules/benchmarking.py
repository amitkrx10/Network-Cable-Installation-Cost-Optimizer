"""Random graph generation and repeated-run benchmarking of Prim vs Kruskal (no Streamlit)."""
from __future__ import annotations

import random
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from algorithms import kruskal_mst, prim_mst


def generate_random_graph(n: int, m: int | None = None, seed: int = 0,
                          max_weight: int = 10000) -> Tuple[List[int], List[tuple]]:
    """Connected random weighted graph with n vertices and ~m edges (m >= n-1)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    nodes = list(range(n))
    if n == 1:
        return nodes, []
    max_edges = n * (n - 1) // 2
    m = min(max(n - 1, m if m is not None else 3 * n), max_edges)
    rng = random.Random(seed)
    perm = nodes[:]
    rng.shuffle(perm)
    edges = set()
    for i in range(1, n):  # random spanning tree guarantees connectivity
        a, b = perm[i], perm[rng.randrange(i)]
        edges.add((min(a, b), max(a, b)))
    if m > len(edges):
        if m > max_edges * 0.5:
            pool = [(a, b) for a in range(n) for b in range(a + 1, n) if (a, b) not in edges]
            edges.update(rng.sample(pool, m - len(edges)))
        else:
            while len(edges) < m:
                a, b = rng.randrange(n), rng.randrange(n)
                if a != b:
                    edges.add((min(a, b), max(a, b)))
    ordered = sorted(edges)
    weights = np.random.default_rng(seed).integers(1, max_weight + 1, size=len(ordered))
    return nodes, [(u, v, int(w), i) for i, ((u, v), w) in enumerate(zip(ordered, weights))]


def time_algorithm(func: Callable, nodes: Sequence, edges: Sequence, runs: int) -> Dict[str, float]:
    """Run `func` repeatedly; execution time is measured inside with time.perf_counter()."""
    func(nodes, edges, record_steps=False)  # warm-up (not measured)
    times, res = [], None
    for _ in range(max(1, runs)):
        res = func(nodes, edges, record_steps=False)
        times.append(res.execution_time * 1000.0)
    arr = np.array(times)
    return {"avg_ms": float(arr.mean()), "min_ms": float(arr.min()), "std_ms": float(arr.std()),
            "cost": res.total_cost, "selected": res.selected_count, "processed": res.edges_processed,
            "rejected": res.edges_rejected, "connected": res.connected}


def _rows(n: int, edges: Sequence, runs: int, nodes: Sequence) -> List[dict]:
    out = []
    stats = {}
    for name, func in (("Prim", prim_mst), ("Kruskal", kruskal_mst)):
        stats[name] = time_algorithm(func, nodes, edges, runs)
    match = abs(stats["Prim"]["cost"] - stats["Kruskal"]["cost"]) < 1e-6
    for name, s in stats.items():
        out.append({"Buildings": n, "Edges": len(edges), "Algorithm": name,
                    "Avg Time (ms)": s["avg_ms"], "Min Time (ms)": s["min_ms"], "Std Dev (ms)": s["std_ms"],
                    "MST Cost": s["cost"], "Selected Edges": s["selected"],
                    "Processed Edges": s["processed"], "Rejected Edges": s["rejected"],
                    "Costs Match": match})
    return out


def benchmark_sizes(sizes: Sequence[int] = (10, 50, 100, 500, 1000), runs: int = 5,
                    edge_factor: int = 3, seed: int = 1, progress: Callable | None = None) -> pd.DataFrame:
    rows: List[dict] = []
    for i, n in enumerate(sizes):
        nodes, edges = generate_random_graph(n, edge_factor * n, seed=seed + n)
        rows += _rows(n, edges, runs, nodes)
        if progress:
            progress((i + 1) / len(sizes), f"V = {n} done")
    return pd.DataFrame(rows)


def benchmark_edge_counts(n: int = 200, edge_counts: Sequence[int] = (400, 1000, 2000, 5000, 10000, 19900),
                          runs: int = 5, seed: int = 7, progress: Callable | None = None) -> pd.DataFrame:
    rows: List[dict] = []
    for i, m in enumerate(edge_counts):
        nodes, edges = generate_random_graph(n, m, seed=seed + m)
        rows += _rows(n, edges, runs, nodes)
        if progress:
            progress((i + 1) / len(edge_counts), f"E = {len(edges)} done")
    return pd.DataFrame(rows)


def benchmark_graph(nodes: Sequence, edges: Sequence, runs: int = 200) -> pd.DataFrame:
    """Repeated-run comparison on an arbitrary (e.g. the current campus) graph."""
    return pd.DataFrame(_rows(len(nodes), list(edges), runs, nodes))
