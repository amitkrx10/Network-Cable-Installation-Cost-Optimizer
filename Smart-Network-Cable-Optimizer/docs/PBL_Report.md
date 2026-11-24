# PBL Report - Smart Network Cable Installation Cost Optimizer

## Abstract
Connecting campus buildings with cable at minimum cost is modelled as a Minimum Spanning Tree problem on a weighted undirected graph.
Prim's and Kruskal's algorithms (with a Disjoint Set Union) are implemented from scratch and embedded in a Streamlit application with
SQLite storage, interactive visualisation, step animation, benchmarking, failure simulation, scenario analysis and PDF/CSV reporting.
On the sample six-building campus the MST costs Rs. 13,000 against Rs. 41,000 for all routes (68.29% saving).

## Problem definition
Given buildings V and candidate cable routes E with cost w(e) = distance x rate + installation charge, choose a subset of E that connects all
buildings with minimum total cost.

## Objectives
Correct manual implementations; complexity and performance comparison; savings analysis; resilience study; usable planning tool with persistence.

## Methodology
Validate input -> build adjacency list / edge list -> run Prim (heap) and Kruskal (sort + DSU) -> verify (V-1 edges, acyclic, connected, equal cost,
NetworkX cross-check, brute force and NetworkX reference in tests) -> analyse cost -> visualise and report.

## Algorithm explanation
*Prim:* start anywhere; repeatedly extract the cheapest edge leaving the tree from a min-heap; skip stale edges. O((V+E) log V).
*Kruskal:* sort edges; accept an edge iff `find(u) != find(v)`, then `union`. O(E log E). *DSU:* path compression + union by rank, O(alpha(V)).
Correctness: cut property (cheapest edge crossing any cut is in some MST) and cycle property.

## System architecture
UI pages -> network_service (business logic) -> algorithms + SQLite (buildings, cable_connections, optimization_results,
algorithm_execution_history, scenarios, app_meta).

## Results and analysis
Sample: selected B-C 1000, A-C 2000, D-E 2000, E-F 3000, B-D 5000 = 13,000; rejected A-B (cycle). Failure of B-D splits {A,B,C} from {D,E,F};
cheapest replacement C-D (8,000) raises MST cost to 16,000. Benchmarks (3 edges/vertex) show both algorithms scale near-linearithmically with equal costs on every graph;
Kruskal is faster on sparse graphs in this implementation, Prim's heap approach is competitive as density rises.

## Conclusion
MST is the right model for minimum-cost connectivity; both algorithms agree on cost; the tool makes the trade-offs visible.

## Future enhancements
Redundant topologies, capacity constraints, GIS distances, Steiner points, authentication and shared deployment.

## Viva preparation
See the *About Project -> Viva Q&A* page. Key points: cut property, why equal-weight ties give different trees with equal cost, DSU optimisations,
disconnected graphs (spanning forest), no fault tolerance in a tree, why negative costs are rejected by the app.
