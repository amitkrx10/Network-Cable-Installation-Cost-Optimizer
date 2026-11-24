# Smart Network Cable Installation Cost Optimizer

**Design and Analysis of Algorithms (DAA) – Project-Based Learning**

A smart network planning application that connects multiple campus buildings using the Minimum Spanning Tree (MST) approach to minimize total cable installation costs.

## Overview

The project models campus buildings as vertices and possible cable connections as weighted edges in an undirected graph.

It implements two classical greedy algorithms:
- Prim's Algorithm
- Kruskal's Algorithm

Both algorithms calculate the minimum-cost network required to connect all buildings.

## Key Features

- **Building Management:** Add, edit, delete, and search campus buildings.
- **Cable Management:** Manage cable connections and installation costs.
- **MST Optimization:** Find the minimum-cost network using Prim's and Kruskal's algorithms.
- **Graph Visualization:** Interactive visualization of the complete network and MST.
- **Algorithm Animation:** Step-by-step execution with playback controls.
- **Algorithm Comparison:** Compare execution time and performance.
- **Cost Analysis:** Calculate total cost, savings, and cable-type expenses.
- **Failure Simulation:** Analyze the impact of network connection failures.
- **Scenario Analysis:** Evaluate different network configurations.
- **Report Generation:** Export PDF and CSV reports.
- **Database Management:** Store project data using SQLite.

## Algorithms Implemented

| Algorithm | Approach | Time Complexity |
|---|---|---|
| Prim's Algorithm | Adjacency List + Min Heap | O((V+E) log V) |
| Kruskal's Algorithm | Sorting + DSU | O(E log E) |
| Disjoint Set Union | Path Compression + Union by Rank | O(α(V)) per operation (amortized) |

## Technology Stack

- Python 3.11+
- Streamlit
- Plotly
- NetworkX
- SQLite
- Pandas
- NumPy
- ReportLab
- Pytest

## Project Structure

```text
Smart-Network-Cable-Optimizer/
│
├── algorithms/
│   ├── prim.py
│   ├── kruskal.py
│   ├── dsu.py
│   ├── common.py
│   └── verify.py
│
├── modules/
│   ├── dashboard.py
│   ├── building_manager.py
│   ├── cable_manager.py
│   ├── mst_optimization.py
│   ├── graph_visualizer.py
│   ├── animation.py
│   ├── algorithm_comparison.py
│   ├── cost_analysis.py
│   ├── failure_simulation.py
│   ├── scenario_analysis.py
│   ├── report_generator.py
│   └── network_service.py
│
├── database/
│   └── db.py
│
├── data/
│   └── sample_network.csv
│
├── tests/
│
├── docs/
│   └── PBL_Report.md
│
├── reports/
├── app.py
├── requirements.txt
└── README.md
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/amitkrx10/Network-Cable-Installation-Cost-Optimizer.git
```

### 2. Navigate to the Project Directory

```bash
cd Smart-Network-Cable-Optimizer
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

### 4. Activate the Environment

Windows:

```bash
venv\Scripts\activate
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run Tests

```bash
python -m pytest -q
```

### 7. Launch the Application

```bash
python -m streamlit run app.py
```

The application will open at:

`http://localhost:8501`

## Sample Results

For the sample six-building campus network:

| Metric | Result |
|---|---:|
| Total cost of all routes | ₹41,000 |
| Minimum spanning tree cost | ₹13,000 |
| Total savings | ₹28,000 |
| Cost reduction | 68.29% |
| Selected MST edges | 5 |

Both Prim's and Kruskal's algorithms produce the same minimum total cost.

## Future Scope

- Redundant network connectivity.
- Capacity and latency constraints.
- GIS-based distance calculations.
- Multi-user deployment.
- Advanced network optimization.

## Author

**Amit Kumar**

B.Tech – Computer Science and Engineering

## Acknowledgement

Developed as a Design and Analysis of Algorithms (DAA) Project-Based Learning project.
