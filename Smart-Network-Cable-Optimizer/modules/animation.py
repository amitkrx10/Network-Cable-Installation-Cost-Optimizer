"""Page 6 - Step-by-step algorithm animation (Prim and Kruskal)."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from . import graph_visualizer as gv
from . import network_service as ns
from . import ui
from .mst_optimization import graph_signature

SS = st.session_state


def _set(idx=None, playing=None) -> None:
    if idx is not None:
        SS["anim_idx"] = idx
    if playing is not None:
        SS["anim_playing"] = playing


def _on_start():
    _set(1 if SS.get("anim_n", 0) else 0, False)


def _on_pause():
    _set(playing=False)


def _on_next():
    _set(min(SS.get("anim_idx", 0) + 1, SS.get("anim_n", 0)), False)


def _on_prev():
    _set(max(SS.get("anim_idx", 0) - 1, 0), False)


def _on_reset():
    _set(0, False)


def _on_auto():
    if SS.get("anim_idx", 0) >= SS.get("anim_n", 0):
        SS["anim_idx"] = 0
    SS["anim_playing"] = True


def _draw(graph, result, pos, idx: int) -> None:
    names = ns.building_names(graph)
    steps = result.steps
    n = len(steps)
    states, tree_nodes = {}, set()
    if result.algorithm == ns.PRIM and result.extra.get("roots"):
        tree_nodes.add(result.extra["roots"][0])
    for s in steps[:idx]:
        states[s["edge_id"]] = s["status"]
        if s["status"] == "selected":
            tree_nodes.update((s["u"], s["v"]))
    colors = {b["id"]: (ui.GREEN if b["id"] in tree_nodes else "#14232f") for b in graph["buildings"]}
    cur = steps[idx - 1] if idx > 0 else None
    fig = gv.build_graph_figure(graph, states, positions=pos, node_colors=colors, height=500,
                                highlight_ids=[cur["edge_id"]] if cur else (),
                                title=f"{result.algorithm} - step {idx} of {n}")
    left, right = st.columns([3, 2])
    with left:
        ui.plot(fig, f"anim_fig_{idx}")
        st.progress(idx / n if n else 1.0, text=f"Step {idx} of {n}")
    with right:
        needed = max(len(graph["buildings"]) - 1, 0)
        if cur is None:
            st.markdown('<div class="stepbox idle"><h4>Ready</h4><div class="row">Press <b>Start</b>, <b>Next Step</b> or '
                        '<b>Auto Play</b>. Grey edges are unprocessed; green are selected; red are rejected.</div></div>',
                        unsafe_allow_html=True)
        else:
            cls = "sel" if cur["status"] == "selected" else "rej"
            badge = ui.badge("SELECTED", "ok") if cur["status"] == "selected" else ui.badge("REJECTED", "bad")
            st.markdown(
                f'<div class="stepbox {cls}"><h4>Step {cur["step"]}: {names[cur["u"]]} - {names[cur["v"]]} {badge}</h4>'
                f'<div class="row"><b>Edge cost:</b> {ui.inr(cur["weight"])}</div>'
                f'<div class="row"><b>Reason:</b> {cur["reason"]}</div>'
                f'<div class="row"><b>Current MST cost:</b> {ui.inr(cur["mst_cost"])}</div>'
                f'<div class="row"><b>Selected edges:</b> {cur["selected_count"]} of {needed}</div>'
                f'<div class="row"><b>State:</b> {cur["info"]}</div></div>', unsafe_allow_html=True)
        if idx == n and n > 0:
            st.success(f"Finished: minimum cost {ui.inr(result.total_cost)} using {result.selected_count} connections."
                       + ("" if result.connected else " (network is disconnected - minimum spanning forest)"))
        if result.algorithm == ns.KRUSKAL:
            st.markdown("**Sorted edge list**")
            status = {s["edge_id"]: s["status"].capitalize() for s in steps[:idx]}
            rows = [{"Order": i + 1, "Edge": f"{names[e.u]} - {names[e.v]}", "Cost": e.weight,
                     "Status": status.get(e.eid, "Pending")} for i, e in enumerate(result.extra["sorted_edges"])]
            ui.show_df(pd.DataFrame(rows, columns=["Order", "Edge", "Cost", "Status"]), height=230)
    if idx:
        with st.expander("Steps so far", expanded=False):
            ui.show_df(ns.steps_df(graph, result, upto=idx))


def render() -> None:
    ui.page_header("Algorithm Animation", "Watch each algorithm choose or reject edges one step at a time.")
    graph = ns.load_graph()
    if not ui.need_buildings(graph, 2):
        return
    if not graph["connections"]:
        st.info("Add cable connections to animate the algorithms.")
        return
    default = 0 if ui.current_algorithm() == ns.PRIM else 1
    c1, c2, c3 = st.columns([2, 2, 2])
    algo = c1.radio("Algorithm", ns.ALGORITHMS, index=default, horizontal=True, key="anim_algo")
    start = None
    if algo == ns.PRIM:
        names = ns.building_names(graph)
        start = c2.selectbox("Start building", list(names), format_func=lambda i: names[i], key="anim_start")
    speed = c3.slider("Auto-play delay (seconds)", 0.1, 2.0, 0.8, 0.1, key="anim_speed")

    result = ns.run_algorithm(graph, algo, start=start)
    n = len(result.steps)
    sig = (algo, start, graph_signature(graph))
    if SS.get("anim_sig") != sig:
        SS.update(anim_sig=sig, anim_idx=0, anim_playing=False)
    SS["anim_n"] = n
    SS["anim_idx"] = min(SS.get("anim_idx", 0), n)

    b = st.columns(6)
    b[0].button("▶ Start", key="anim_b_start", on_click=_on_start, **ui._WIDE)
    b[1].button("⏸ Pause", key="anim_b_pause", on_click=_on_pause, **ui._WIDE)
    b[2].button("⏭ Next Step", key="anim_b_next", on_click=_on_next, **ui._WIDE)
    b[3].button("⏮ Previous Step", key="anim_b_prev", on_click=_on_prev, **ui._WIDE)
    b[4].button("↺ Reset", key="anim_b_reset", on_click=_on_reset, **ui._WIDE)
    b[5].button("⏩ Auto Play", key="anim_b_auto", on_click=_on_auto, **ui._WIDE)

    pos = gv.compute_layout(graph)
    holder = st.empty()
    with holder.container():
        _draw(graph, result, pos, SS["anim_idx"])
    if SS.get("anim_playing"):
        while SS["anim_idx"] < n:
            time.sleep(speed)
            SS["anim_idx"] += 1
            with holder.container():
                _draw(graph, result, pos, SS["anim_idx"])
        SS["anim_playing"] = False
