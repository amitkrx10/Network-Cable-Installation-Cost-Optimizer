"""Page 1 - Dashboard: KPIs, charts and network status."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import db
from . import graph_visualizer as gv
from . import network_service as ns
from . import ui


def render() -> None:
    ui.show_flash()
    ui.page_header("Network Planning Dashboard", "Minimum-cost cabling for your campus, computed with Prim's and Kruskal's algorithms.")
    graph = ns.load_graph()
    if not graph["buildings"]:
        st.info("No buildings yet. Add buildings in **Building Management**, or load the sample campus below.")
        if ui.button("Load sample campus network", key="dash_load_sample"):
            db.seed_sample_data(reset=True)
            ui.flash("success", "Sample campus network loaded.")
            st.rerun()
        return

    algorithm = ui.current_algorithm()
    result = ns.run_algorithm(graph, algorithm, record_steps=False)
    m = ns.cost_metrics(graph, result)
    status = "Connected" if result.connected else f"{result.num_components} parts"

    ui.kpi_row([
        ("Total buildings", f"{m['num_buildings']}", "nodes in the graph", ui.TEAL),
        ("Possible connections", f"{m['num_connections']}", "candidate cable routes", ui.TEAL),
        ("Total possible cost", ui.inr(m["original_cost"]), "if every route were laid", ui.AMBER),
    ])
    ui.kpi_row([
        ("Minimum installation cost", ui.inr(m["mst_cost"]), "MST total", ui.GREEN),
        ("Selected MST connections", f"{m['selected_edges']}", f"V - 1 = {max(m['num_buildings'] - 1, 0)} for a connected network", ui.GREEN),
        ("Cost savings", ui.inr(m["savings"]), f"{m['savings_pct']:.2f}% saved", ui.GREEN),
    ])
    ui.kpi_row([
        ("Savings percentage", f"{m['savings_pct']:.2f}%", "(Original - MST) / Original", ui.GREEN),
        ("Selected algorithm", algorithm.replace(" Algorithm", ""), result.time_complexity, ui.BLUE),
        ("Connectivity status", status, "all buildings reachable" if result.connected else "some buildings isolated",
         ui.GREEN if result.connected else ui.RED),
    ])
    if not result.connected:
        st.warning("The network is **disconnected**. Add cable connections between the separate parts to link every building.")

    left, right = st.columns([3, 2])
    with left:
        ui.plot(gv.complete_network_figure(graph, result, height=470, positions=gv.compute_layout(graph)), "dash_graph")
    with right:
        fig = go.Figure(go.Bar(x=["All possible routes", "Optimized MST", "Savings"],
                               y=[m["original_cost"], m["mst_cost"], m["savings"]],
                               marker_color=[ui.AMBER, ui.GREEN, ui.TEAL],
                               text=[ui.inr(v) for v in (m["original_cost"], m["mst_cost"], m["savings"])],
                               textposition="outside"))
        fig.update_layout(title="Cost comparison (₹)", height=235, margin=dict(l=10, r=10, t=40, b=10),
                          plot_bgcolor="white", yaxis=dict(showgrid=True, gridcolor="#eef2f5"))
        ui.plot(fig, "dash_cost_bar")
        sel = ns.cost_by_cable_type(ns.mst_connections(graph, result))
        allc = ns.cost_by_cable_type(graph["connections"])
        fig2 = go.Figure()
        fig2.add_bar(x=allc["Cable Type"], y=allc["Total Cost"], name="All possible", marker_color=ui.GREY)
        fig2.add_bar(x=sel["Cable Type"], y=sel["Total Cost"], name="Selected MST", marker_color=ui.GREEN)
        fig2.update_layout(title="Cost by cable type (₹)", barmode="group", height=235,
                           margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white",
                           legend=dict(orientation="h", y=1.25))
        ui.plot(fig2, "dash_type_bar")

    t1, t2 = st.columns(2)
    with t1:
        st.subheader("Selected MST connections")
        ui.show_df(ns.connections_df(ns.mst_connections(graph, result))[["From", "To", "Cable Type", "Total Cost"]])
    with t2:
        st.subheader("Recent optimization runs")
        hist = db.get_execution_history(limit=8)
        if hist:
            df = pd.DataFrame(hist)[["created_at", "algorithm", "mst_cost", "execution_time_ms", "connected"]]
            df.columns = ["Time", "Algorithm", "MST Cost", "Time (ms)", "Connected"]
            ui.show_df(df)
        else:
            st.caption("No runs saved yet - open **MST Optimization** and run an algorithm.")
