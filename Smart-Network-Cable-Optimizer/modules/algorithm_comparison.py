"""Page 7 - Prim vs Kruskal performance comparison."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from algorithms.common import KRUSKAL_SPACE, KRUSKAL_TIME, PRIM_SPACE, PRIM_TIME
from . import benchmarking as bm
from . import network_service as ns
from . import ui

COLORS = {"Prim": "#0e7490", "Kruskal": "#d97706"}


def _theory_table() -> pd.DataFrame:
    return pd.DataFrame([
        ["Strategy", "Grows one tree vertex by vertex", "Merges components edge by edge"],
        ["Data structures", "Adjacency list + binary min-heap", "Sorted edge list + Disjoint Set Union"],
        ["Time complexity", PRIM_TIME, KRUSKAL_TIME],
        ["Space complexity", PRIM_SPACE, KRUSKAL_SPACE],
        ["Best for", "Dense graphs (E close to V^2)", "Sparse graphs (E close to V)"],
        ["Cycle handling", "Skips edges to visited vertices", "DSU find() detects same component"],
        ["Disconnected graph", "Restart from each unvisited vertex", "Naturally yields a spanning forest"],
    ], columns=["Property", "Prim's Algorithm", "Kruskal's Algorithm"])


def _line(df, x, title, xlabel, key, log=True):
    fig = px.line(df, x=x, y="Avg Time (ms)", color="Algorithm", markers=True, color_discrete_map=COLORS,
                  title=title, labels={x: xlabel})
    fig.update_layout(plot_bgcolor="white", height=380, yaxis=dict(gridcolor="#eef2f5", type="log" if log else "linear"),
                      xaxis=dict(gridcolor="#eef2f5"))
    ui.plot(fig, key)


def render() -> None:
    ui.page_header("Algorithm Comparison", "Execution time, edges processed and cost for Prim's and Kruskal's algorithms.")
    graph = ns.load_graph()

    st.subheader("1. Current campus network")
    if graph["buildings"]:
        nodes, edges = ns.algo_inputs(graph)
        runs = st.slider("Repeated runs (averaged)", 10, 1000, 200, 10, key="cmp_runs")
        df = bm.benchmark_graph(nodes, edges, runs=runs)
        pr = ns.run_algorithm(graph, ns.PRIM, record_steps=False)
        kr = ns.run_algorithm(graph, ns.KRUSKAL, record_steps=False)
        show = df[["Algorithm", "Avg Time (ms)", "Min Time (ms)", "Selected Edges", "Processed Edges",
                   "Rejected Edges", "MST Cost"]].copy()
        show["Avg Time (µs)"] = (show.pop("Avg Time (ms)") * 1000).round(2)
        show["Min Time (µs)"] = (show.pop("Min Time (ms)") * 1000).round(2)
        show["Time Complexity"] = [PRIM_TIME, KRUSKAL_TIME]
        show["Space Complexity"] = [PRIM_SPACE, KRUSKAL_SPACE]
        ui.show_df(show)
        same_cost = abs(pr.total_cost - kr.total_cost) < 1e-6
        same_edges = {e.eid for e in pr.mst_edges} == {e.eid for e in kr.mst_edges}
        k1, k2 = st.columns(2)
        k1.metric("Minimum cost identical?", "Yes" if same_cost else "NO")
        k2.metric("Selected edge sets identical?", "Yes" if same_edges else "No (multiple MSTs)")
        fig = go.Figure(go.Bar(x=["Prim", "Kruskal"], y=show["Avg Time (µs)"], marker_color=[COLORS["Prim"], COLORS["Kruskal"]],
                               text=[f"{v:.2f} µs" for v in show["Avg Time (µs)"]], textposition="outside"))
        fig.update_layout(title=f"Execution time comparison (average of {runs} runs)", yaxis_title="Time (µs)",
                          plot_bgcolor="white", height=340)
        ui.plot(fig, "cmp_bar_current")
    else:
        st.info("Add buildings and connections to compare the algorithms on your own network.")

    st.subheader("2. Generated graphs: scalability benchmark")
    st.caption("Random connected graphs. Execution time is measured inside each algorithm with time.perf_counter() "
               "and averaged over repeated runs.")
    c1, c2, c3 = st.columns(3)
    sizes = c1.multiselect("Number of buildings (V)", [10, 50, 100, 500, 1000], default=[10, 50, 100, 500, 1000], key="bm_sizes")
    runs_b = c2.slider("Runs per graph", 1, 20, 5, key="bm_runs")
    factor = c3.select_slider("Edges per vertex (E ≈ k·V)", options=[2, 3, 5, 10], value=3, key="bm_factor")
    if ui.button("Run benchmark", key="bm_run"):
        if not sizes:
            st.error("Select at least one graph size.")
        else:
            bar = st.progress(0.0, text="Benchmarking...")
            by_size = bm.benchmark_sizes(sorted(sizes), runs=runs_b, edge_factor=factor,
                                         progress=lambda f, t: bar.progress(f * 0.6, text=t))
            by_edges = bm.benchmark_edge_counts(200, runs=runs_b,
                                                progress=lambda f, t: bar.progress(0.6 + f * 0.4, text=t))
            bar.empty()
            st.session_state["bm_results"] = (by_size, by_edges)
    res = st.session_state.get("bm_results")
    if res:
        by_size, by_edges = res
        if not by_size["Costs Match"].all() or not by_edges["Costs Match"].all():
            st.error("Prim and Kruskal returned different costs - this indicates a bug.")
        else:
            st.success("Prim and Kruskal returned the same minimum cost on every generated graph.")
        ui.show_df(by_size.round(4))
        fig = px.bar(by_size, x="Buildings", y="Avg Time (ms)", color="Algorithm", barmode="group",
                     color_discrete_map=COLORS, title="Execution time comparison by graph size")
        fig.update_layout(plot_bgcolor="white", height=380, xaxis=dict(type="category"), yaxis=dict(gridcolor="#eef2f5"))
        ui.plot(fig, "cmp_bar_sizes")
        _line(by_size, "Buildings", "Graph size vs execution time (log scale)", "Number of buildings (V)", "cmp_line_size")
        st.markdown("**Edge count vs execution time** (fixed V = 200, increasing E)")
        _line(by_edges, "Edges", "Edge count vs execution time (log scale)", "Number of edges (E)", "cmp_line_edges")
        with st.expander("Edge-count experiment data"):
            ui.show_df(by_edges.round(4))
    else:
        st.info("Press **Run benchmark** to test 10, 50, 100, 500 and 1000 buildings.")

    st.subheader("3. Theory and interpretation")
    ui.show_df(_theory_table())
    st.markdown("""
- Both algorithms are **correct**: they always return a spanning tree of **identical minimum total cost**.
- When several edges share the same weight there can be **more than one** minimum spanning tree, so the *selected edges* may differ while the *cost* is equal.
- Kruskal is dominated by sorting `O(E log E)`; Prim by heap operations `O(E log V)`. On sparse graphs both are close, while on very dense graphs Kruskal's sort of all edges becomes the main cost in this pure-Python measurement.
- Timings depend on the machine and on Python's constant factors; the theoretical complexity - not the raw milliseconds - is what the analysis relies on.
""")
