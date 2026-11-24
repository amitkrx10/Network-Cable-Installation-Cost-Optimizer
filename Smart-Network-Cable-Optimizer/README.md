# Smart Network Cable Installation Cost Optimizer
**Design and Analysis of Algorithms (DAA) - PBL project** | Prim's Algorithm - Kruskal's Algorithm - MST - Disjoint Set Union

## 1. Introduction & problem statement
Connect different buildings of a campus with the **minimum total cable installation cost**. Buildings are graph vertices,
possible cable routes are weighted edges (`Total Cost = Distance x Cost per meter + Installation charge`), and the
cheapest way to link everything is a **Minimum Spanning Tree**.

## 2. Objectives
1. Implement Prim's (adjacency list + min-heap) and Kruskal's (sorting + DSU with path compression and union by rank) **from scratch**.
2. Compare them theoretically and by measurement (`time.perf_counter()`, repeated runs, 10-1000 buildings).
3. Visualise, animate, and quantify savings; simulate link failures; analyse what-if scenarios.
4. Persist everything in SQLite and export PDF/CSV reports.

## 3. Features (all implemented and tested)
Dashboard KPIs | Building CRUD + search | Cable CRUD with live cost formula and validation (self-loops, duplicates, negatives) |
Prim and Kruskal with recorded steps, selected/rejected edges, timing, complexity | Interactive Plotly graph (complete / MST modes) |
Step-by-step animation (Start, Pause, Next, Previous, Reset, Auto Play) | Prim vs Kruskal benchmark with 3 charts |
Cost analysis (savings, by cable type) | Network failure simulation + criticality table | Dynamic optimization (add/remove/change, old vs new) |
Scenario analysis (5 presets + custom, saved in DB) | PDF + CSV reports | Algorithm theory, pseudocode and viva Q&A page.

## 4. Technology stack
Python 3.11+, Streamlit, Plotly, NetworkX (layout and validation **only**), SQLite, Pandas, NumPy, ReportLab, Pytest.

## 5. Architecture
```
Streamlit pages (modules/*.py) -> business logic (modules/network_service.py) -> algorithms/ (Prim, Kruskal, DSU)
                                                                             -> database/db.py (SQLite)
```
## 6. Project structure
```
app.py                    entry point + sidebar navigation
algorithms/               prim.py  kruskal.py  dsu.py  common.py  verify.py
modules/                  dashboard, building_manager, cable_manager, mst_optimization, graph_visualizer,
                          animation, algorithm_comparison, cost_analysis, failure_simulation,
                          scenario_analysis, report_generator, about, network_service, benchmarking, ui
database/db.py            schema, validation, CRUD
data/sample_network.csv   sample campus connections (network.db is created on first run)
reports/                  generated PDF reports
tests/                    pytest suite (102 tests)
docs/PBL_Report.md        abstract, methodology, results, viva preparation
```
## 7. Installation and execution (Windows PowerShell)
```powershell
cd Smart-Network-Cable-Optimizer
python -m venv venv
.\venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q                   # run all tests
python -m streamlit run app.py        # launch the app (opens http://localhost:8501)
```
The SQLite database `data/network.db` is created and filled with the sample campus on first launch and keeps your data afterwards.
Use *Building Management -> Data Tools* to reset to the sample data.

## 8. Sample output
| Source | Dest | Cost | In MST |
|---|---|---:|:-:|
| B-C | | 1,000 | yes |
| A-C | | 2,000 | yes |
| D-E | | 2,000 | yes |
| E-F | | 3,000 | yes |
| A-B | | 4,000 | no (cycle) |
| B-D | | 5,000 | yes |

Minimum cost **₹13,000** (5 edges = V-1) | all routes ₹41,000 | savings **₹28,000 (68.29%)** - identical for Prim and Kruskal.

## 9. Screenshots
Add your own screenshots here after running the app (Dashboard, Graph Visualization, Animation, Comparison, Failure Simulation).

## 10. Complexity analysis
| | Time | Space |
|---|---|---|
| Prim (binary heap) | O((V+E) log V) | O(V+E) |
| Kruskal (DSU) | O(E log E) = O(E log V) | O(V+E) |
| DSU find/union | O(alpha(V)) amortised | O(V) |

## 11. Notes
* The PDF uses "Rs." because built-in PDF fonts lack the rupee glyph; the app UI shows ₹.
* An MST has no redundancy: any installed link failing disconnects the network (shown in Failure Simulation).
* Connections are undirected; a connection between two buildings can exist only once.

## 12. Future scope
Redundant (k-edge-connected) designs, capacity/latency constraints, map-based coordinates with automatic distance,
Steiner-tree extensions, multi-user deployment with a server database.

## 13. Conclusion
The project shows that a greedy MST gives the provably cheapest connected cabling plan; Prim and Kruskal return the same
minimum cost, with performance differences that follow their complexity profiles.
