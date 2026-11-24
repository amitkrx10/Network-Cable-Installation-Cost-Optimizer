"""Page 13 - About the project and Algorithm Theory (DAA)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import ui

PRIM_PSEUDO = """PRIM(G, start):
    for each vertex v: visited[v] <- false
    visited[start] <- true;  T <- empty set;  cost <- 0
    H <- min-heap of edges (w, start, v) for every neighbour v of start
    while H is not empty:
        (w, u, v) <- EXTRACT-MIN(H)
        if visited[v]:  continue                 # would form a cycle
        visited[v] <- true
        T <- T + {(u, v)};  cost <- cost + w
        for each neighbour x of v with not visited[x]:
            INSERT(H, (weight(v, x), v, x))
    if |T| < V - 1:  graph is disconnected
    return T, cost"""

KRUSKAL_PSEUDO = """KRUSKAL(G):
    T <- empty set;  cost <- 0
    for each vertex v: MAKE-SET(v)
    sort edges of G by non-decreasing weight
    for each edge (u, v, w) in sorted order:
        if FIND(u) != FIND(v):                   # different components -> no cycle
            UNION(u, v)                          # union by rank + path compression
            T <- T + {(u, v)};  cost <- cost + w
            if |T| = V - 1:  break
    if |T| < V - 1:  graph is disconnected
    return T, cost"""

COMPLEXITY = pd.DataFrame([
    ["Prim (binary heap)", "O((V + E) log V)", "O(V + E)", "Dense graphs", "Needs adjacency list + heap"],
    ["Kruskal (DSU)", "O(E log E) = O(E log V)", "O(V + E)", "Sparse graphs", "Needs all edges sorted up-front"],
    ["DSU find / union", "O(alpha(V)) amortised", "O(V)", "Cycle detection", "Needs path compression + union by rank"],
], columns=["Algorithm", "Time", "Space", "Best for", "Limitation"])


def render() -> None:
    ui.page_header("About the Project", "Smart Network Cable Installation Cost Optimizer - Design and Analysis of Algorithms PBL")
    t1, t2, t3, t4, t5 = st.tabs(["Project Overview", "Algorithm Theory", "Pseudocode", "Complexity & Applications", "Viva Q&A"])

    with t1:
        st.markdown("""
**Problem statement.** Connect different buildings with the *minimum total cable installation cost*.

**Model.** Buildings are vertices; every possible cable route is an undirected edge whose weight is
`Total Cost = (Distance x Cost per meter) + Installation charges`. The cheapest set of routes that links all
buildings is a **Minimum Spanning Tree (MST)**.

**Objectives**
1. Implement Prim's and Kruskal's algorithms from scratch, with a Disjoint Set Union.
2. Compare them theoretically and experimentally (time, edges processed, cost).
3. Visualise the network, animate each algorithm, and quantify the savings.
4. Study resilience: what happens when an installed link fails.
5. Support dynamic changes and what-if scenarios backed by a SQLite database.

**Methodology.** Input validation -> graph construction -> MST computation (both algorithms) -> verification
(V-1 edges, no cycle, connectivity, equal cost) -> cost analysis -> visualisation and reporting.

**System architecture.** `Streamlit UI (modules/)` -> `business logic (network_service)` -> `algorithms/` (Prim, Kruskal, DSU)
and `database/` (SQLite). NetworkX is used only for layout and validation, never for the optimisation.
""")
    with t2:
        st.markdown("""
**Graph data structure.** A graph G = (V, E). We store it as an *adjacency list* (vertex -> list of (weight, neighbour)),
which needs O(V + E) space and lets Prim enumerate neighbours quickly.

**Weighted undirected graph.** Each edge {u, v} has a non-negative weight and can be used in both directions.

**Minimum Spanning Tree.** A spanning tree is an acyclic connected subgraph containing all V vertices (exactly V - 1 edges).
An MST is the spanning tree with the smallest total weight. It is unique when all edge weights are distinct.

**Greedy approach.** Both algorithms repeatedly take the locally cheapest safe edge. This is optimal because of the
**cut property**: for any cut of the graph, the cheapest edge crossing the cut belongs to some MST. The **cycle property**
says the heaviest edge on any cycle is never needed.

**Prim's algorithm** grows one tree from a start vertex, always adding the cheapest edge that leaves the tree.

**Kruskal's algorithm** sorts all edges and adds each one that joins two different components.

**Disjoint Set Union (Union-Find).** Maintains a partition of vertices. `find` returns a set representative
(with *path compression*); `union` merges sets (by *rank*). Together they run in amortised O(alpha(V)).

**Cycle detection.** An edge (u, v) closes a cycle exactly when `find(u) == find(v)`. Prim detects the same situation
when an endpoint is already visited.

**Why MST suits cable installation.** Cost is the sum of installed edge costs and every building must be reachable.
Any extra edge beyond V - 1 only adds cost, so the cheapest connected network is a spanning tree - an MST.

**Advantages.** Optimal, simple, fast, deterministic cost. **Limitations.** No redundancy: one link failure splits the
network; it ignores traffic load, latency and capacity; weights must be known and static.

**Real-world applications.** Campus/ISP/LAN cabling, power-grid and pipeline layout, road and railway planning,
telecom backbones, clustering (single-linkage), circuit/VLSI wiring, approximation algorithms (TSP).
""")
    with t3:
        c1, c2 = st.columns(2)
        c1.markdown("**Prim's Algorithm**")
        c1.code(PRIM_PSEUDO, language="text")
        c2.markdown("**Kruskal's Algorithm**")
        c2.code(KRUSKAL_PSEUDO, language="text")
    with t4:
        st.markdown("**Theoretical comparison**")
        ui.show_df(COMPLEXITY)
        st.markdown("""
- Prim: each of the E edges is pushed/popped at most once or twice -> heap operations cost O(log E) = O(log V) -> **O((V + E) log V)**.
- Kruskal: sorting dominates -> **O(E log E)**; the DSU operations add O(E alpha(V)).
- Both need **O(V + E)** extra space (graph, heap/sorted list, DSU arrays).
- **Sample result:** 6 buildings, 9 routes -> MST cost ₹13,000 vs ₹41,000 for all routes (savings ₹28,000, 68.29%).
""")
    with t5:
        qa = {
            "Why is the greedy strategy correct for MST?": "The cut property guarantees the cheapest edge across any cut belongs to an MST, so choosing it never rules out an optimal solution.",
            "Prim vs Kruskal - when to prefer which?": "Prim with an adjacency structure suits dense graphs; Kruskal suits sparse graphs or when edges are already a list.",
            "Can both algorithms give different trees?": "Yes, if equal-weight edges allow several MSTs. The total cost is always identical.",
            "How does DSU speed up Kruskal?": "find/union run in near-constant amortised time using path compression and union by rank, so cycle checks are cheap.",
            "What if the graph is disconnected?": "No spanning tree exists. Both algorithms return a minimum spanning forest with fewer than V - 1 edges, and the app reports the network as disconnected.",
            "Does an MST give a fault-tolerant network?": "No. A tree has no redundancy; any edge failure disconnects it. Extra links (e.g. a ring) are needed for resilience at extra cost.",
            "Why can't negative costs be used?": "A cost cannot be negative physically; the app rejects them. (MST algorithms themselves also work with negative weights, but the model does not need them.)",
        }
        for q, a in qa.items():
            with st.expander(q):
                st.write(a)
