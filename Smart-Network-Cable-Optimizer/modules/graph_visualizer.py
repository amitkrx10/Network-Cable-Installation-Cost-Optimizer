"""Interactive Plotly graph visualisation + the 'Graph Visualization' page."""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Optional, Tuple

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

from . import network_service as ns
from . import ui

STATE_STYLE = {
    "unprocessed": dict(color=ui.GREY, width=2, dash="solid", name="Unprocessed"),
    "rejected": dict(color=ui.RED, width=3, dash="solid", name="Rejected (forms a cycle)"),
    "failed": dict(color=ui.RED, width=5, dash="dash", name="Failed connection"),
    "replacement": dict(color=ui.BLUE, width=5, dash="solid", name="Replacement connection"),
    "selected": dict(color=ui.GREEN, width=5, dash="solid", name="Selected (MST edge)"),
}
DRAW_ORDER = ["unprocessed", "rejected", "failed", "replacement", "selected"]
PALETTE = ["#0e7490", "#d97706", "#7c3aed", "#be123c", "#15803d", "#1d4ed8", "#a16207", "#0f766e"]


def compute_layout(graph: ns.Graph, seed: int = 42) -> Dict[int, Tuple[float, float]]:
    """Deterministic layout (fixed seed) so every view of the same network looks the same."""
    ids = [b["id"] for b in graph["buildings"]]
    if not ids:
        return {}
    if len(ids) == 1:
        return {ids[0]: (0.0, 0.0)}
    G = nx.Graph()
    G.add_nodes_from(ids)
    G.add_edges_from((c["source_id"], c["dest_id"]) for c in graph["connections"])
    if len(ids) > 400:
        pos = nx.circular_layout(G)
    else:
        pos = nx.spring_layout(G, seed=seed, k=1.6 / math.sqrt(len(ids)), iterations=200)
    return {k: (float(v[0]), float(v[1])) for k, v in pos.items()}


def mst_states(result) -> Dict[int, str]:
    return {e.eid: "selected" for e in result.mst_edges}


def build_graph_figure(graph: ns.Graph, edge_states: Dict[int, str],
                       positions: Optional[Dict[int, Tuple[float, float]]] = None,
                       node_colors: Optional[Dict[int, str]] = None,
                       highlight_ids: Iterable[int] = (), title: str = "",
                       labels: Optional[Dict[str, str]] = None, hide_states: Iterable[str] = (),
                       height: int = 580, show_weights: Optional[bool] = None) -> go.Figure:
    pos = positions or compute_layout(graph)
    conns = graph["connections"]
    show_w = (len(conns) <= 60) if show_weights is None else show_weights
    show_names = len(graph["buildings"]) <= 40
    labels = labels or {}
    hide = set(hide_states)
    fig = go.Figure()

    def mid(c):
        (x0, y0), (x1, y1) = pos[c["source_id"]], pos[c["dest_id"]]
        return (x0 + x1) / 2, (y0 + y1) / 2

    def hover(c):
        return (f"<b>{c['source_name']} ↔ {c['dest_name']}</b><br>Total cost: {ui.inr(c['total_cost'])}<br>"
                f"Distance: {c['distance_m']:g} m<br>Cable: {c['cable_type']}<br>"
                f"Rate: {ui.inr(c['cost_per_meter'])}/m + {ui.inr(c['install_charge'])} installation")

    hl = [c for c in conns if c["id"] in set(highlight_ids)]
    if hl:
        xs, ys = [], []
        for c in hl:
            (x0, y0), (x1, y1) = pos[c["source_id"]], pos[c["dest_id"]]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="rgba(245,158,11,0.45)", width=14),
                                 hoverinfo="skip", name="Current edge"))

    groups: Dict[str, list] = {}
    for c in conns:
        s = edge_states.get(c["id"], "unprocessed")
        if s not in hide:
            groups.setdefault(s, []).append(c)
    for state in DRAW_ORDER:
        items = groups.get(state)
        if not items:
            continue
        style = STATE_STYLE[state]
        name = labels.get(state, style["name"])
        xs, ys = [], []
        for c in items:
            (x0, y0), (x1, y1) = pos[c["source_id"]], pos[c["dest_id"]]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", hoverinfo="skip", legendgroup=state, name=name,
                                 line=dict(color=style["color"], width=style["width"], dash=style["dash"])))
        mids = [mid(c) for c in items]
        fig.add_trace(go.Scatter(
            x=[m[0] for m in mids], y=[m[1] for m in mids], legendgroup=state, showlegend=False,
            mode="markers+text" if show_w else "markers",
            text=[ui.inr(c["total_cost"]) for c in items], textposition="top center",
            textfont=dict(size=11, color=style["color"] if state != "unprocessed" else "#6b7280"),
            marker=dict(size=9, color="white", line=dict(color=style["color"], width=2)),
            hovertext=[hover(c) for c in items], hoverinfo="text"))

    ids = [b["id"] for b in graph["buildings"]]
    deg = {i: 0 for i in ids}
    for c in conns:
        deg[c["source_id"]] += 1
        deg[c["dest_id"]] += 1
    node_colors = node_colors or {}
    fig.add_trace(go.Scatter(
        x=[pos[b["id"]][0] for b in graph["buildings"]], y=[pos[b["id"]][1] for b in graph["buildings"]],
        mode="markers+text" if show_names else "markers", name="Buildings",
        text=[f"<b>{b['name']}</b>" for b in graph["buildings"]], textposition="bottom center",
        textfont=dict(size=12, color=ui.INK),
        marker=dict(size=26, color=[node_colors.get(b["id"], "#14232f") for b in graph["buildings"]],
                    line=dict(color="white", width=2)),
        hovertext=[f"<b>{b['name']}</b> ({b['code']})<br>{b['description'] or ''}<br>Possible links: {deg[b['id']]}"
                   for b in graph["buildings"]], hoverinfo="text"))

    if pos:
        xs_all = [p[0] for p in pos.values()]
        ys_all = [p[1] for p in pos.values()]
        padx = max(0.3, (max(xs_all) - min(xs_all)) * 0.15)
        pady = max(0.3, (max(ys_all) - min(ys_all)) * 0.15)
        xr, yr = [min(xs_all) - padx, max(xs_all) + padx], [min(ys_all) - pady, max(ys_all) + pady]
    else:
        xr = yr = [-1, 1]
    fig.update_layout(
        title=dict(text=title, x=0.01, font=dict(size=16)), height=height, dragmode="pan",
        plot_bgcolor="white", paper_bgcolor="white", hovermode="closest",
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis=dict(visible=False, range=xr), yaxis=dict(visible=False, range=yr),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0))
    return fig


def complete_network_figure(graph: ns.Graph, result, **kw) -> go.Figure:
    return build_graph_figure(graph, mst_states(result), title="Complete network - MST connections highlighted",
                              labels={"unprocessed": "Not selected"}, **kw)


def mst_only_figure(graph: ns.Graph, result, **kw) -> go.Figure:
    return build_graph_figure(graph, mst_states(result), title="Optimized minimum spanning tree",
                              hide_states=("unprocessed",), **kw)


def render() -> None:
    graph = ns.load_graph()
    ui.page_header("Graph Visualization", "Buildings are nodes, possible cable routes are edges. Scroll to zoom, drag to pan, hover for costs.")
    if not ui.need_buildings(graph):
        return
    algorithm = ui.current_algorithm()
    result = ns.run_algorithm(graph, algorithm, record_steps=False)
    metrics = ns.cost_metrics(graph, result)
    pos = compute_layout(graph)

    mode = st.radio("Visualization mode", ["Complete Network Graph", "Optimized Minimum Spanning Tree"],
                    horizontal=True, key="viz_mode")
    c1, c2, c3 = st.columns(3)
    c1.metric("Algorithm", algorithm.replace(" Algorithm", ""))
    c2.metric("MST cost", ui.inr(metrics["mst_cost"]))
    c3.metric("Network status", "Connected" if result.connected else f"{result.num_components} separate parts")
    fig = (complete_network_figure(graph, result, positions=pos) if mode.startswith("Complete")
           else mst_only_figure(graph, result, positions=pos))
    ui.plot(fig, "viz_main")
    if not result.connected:
        st.warning("The network is not fully connected - the figure shows a minimum spanning forest. "
                   "Add cable connections between the separate parts to link every building.")
    st.caption("Green edges = installed MST connections; grey edges = possible connections that are not selected. "
               "Edge labels show the total installation cost in ₹.")
    with st.expander("Selected connections"):
        rows = ns.mst_connections(graph, result)
        ui.show_df(ns.connections_df(rows))
