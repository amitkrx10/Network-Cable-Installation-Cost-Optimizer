"""Page 4 - MST Optimization: run Prim/Kruskal, inspect results, dynamic updates, history."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from algorithms import verify_mst
from database import db
from . import graph_visualizer as gv
from . import network_service as ns
from . import ui


def graph_signature(graph) -> tuple:
    return (tuple((b["id"], b["name"]) for b in graph["buildings"]),
            tuple((c["id"], c["source_id"], c["dest_id"], c["total_cost"]) for c in graph["connections"]))


def show_result(graph, result, key: str) -> None:
    m = ns.cost_metrics(graph, result)
    names = ns.building_names(graph)
    ui.kpi_row([
        ("Minimum installation cost", ui.inr(m["mst_cost"]), f"{m['selected_edges']} connections selected", ui.GREEN),
        ("Execution time", f"{result.execution_time_ms:.4f} ms", "time.perf_counter()", ui.BLUE),
        ("Edges processed", f"{result.edges_processed}", f"{result.edges_rejected} rejected (cycle)", ui.TEAL),
        ("Savings", ui.inr(m["savings"]), f"{m['savings_pct']:.2f}% below {ui.inr(m['original_cost'])}", ui.GREEN),
    ])
    if result.connected:
        st.success(f"Connected network: every building is linked using exactly V - 1 = {max(m['num_buildings'] - 1, 0)} connections.")
    else:
        st.error(f"Disconnected network: the buildings form {result.num_components} separate parts, so no single spanning tree exists. "
                 "The result is a minimum spanning forest. Add connections between the parts to link them.")
    c1, c2 = st.columns(2)
    c1.markdown(f"**Time complexity:** `{result.time_complexity}`")
    c2.markdown(f"**Space complexity:** `{result.space_complexity}`")
    if result.algorithm == ns.PRIM and result.extra.get("roots"):
        st.caption(f"Started from: {names[result.extra['roots'][0]]}")
    if result.algorithm == ns.KRUSKAL:
        unexamined = result.num_edges - result.edges_processed
        st.caption(f"Kruskal stopped after the tree was complete; {unexamined} heavier edge(s) never needed examining.")

    left, right = st.columns([3, 2])
    with left:
        ui.plot(gv.mst_only_figure(graph, result, height=430, positions=gv.compute_layout(graph)), f"{key}_fig")
    with right:
        nodes, edges = ns.algo_inputs(graph)
        checks = verify_mst(nodes, edges, result)
        nxc = ns.networkx_validate(graph, result)
        st.markdown("**Verification**")
        for label, ok in {**checks, **nxc}.items():
            st.markdown(f"{'✅' if ok else '❌'} {label}")
    t1, t2, t3 = st.tabs(["Selected edges", "Rejected edges", "Execution steps"])
    with t1:
        sel = ns.mst_connections(graph, result)
        ui.show_df(ns.connections_df(sel))
    with t2:
        df = ns.steps_df(graph, result)
        rej = df[df["Status"] == "Rejected"]
        if rej.empty:
            st.caption("No edge was rejected.")
        else:
            ui.show_df(rej[["Step", "Edge", "Cost", "Reason"]])
    with t3:
        ui.show_df(ns.steps_df(graph, result))


def _run_tab(graph) -> None:
    algorithm = ui.current_algorithm()
    sig = graph_signature(graph)
    if st.session_state.get("mst_sig") != sig:
        st.session_state["mst_runs"], st.session_state["mst_sig"] = {}, sig
    start = None
    if algorithm == ns.PRIM:
        ids = [b["id"] for b in graph["buildings"]]
        names = ns.building_names(graph)
        start = st.selectbox("Prim start building", ids, format_func=lambda i: names[i], key="prim_start")
    c1, c2 = st.columns(2)
    run_sel = ui.button(f"Run {algorithm} and save", key="run_selected")
    run_both = ui.button("Run both algorithms and save", key="run_both")
    if run_sel or run_both:
        algos = ns.ALGORITHMS if run_both else [algorithm]
        runs = {}
        for a in algos:
            res = ns.run_algorithm(graph, a, start=start if a == ns.PRIM else None)
            db.save_optimization_result(ns.result_to_record(graph, res))
            runs[a] = res
        st.session_state["mst_runs"] = runs
        st.success(f"Saved {len(runs)} run(s) to the database history.")
    runs = st.session_state.get("mst_runs") or {}
    if not runs:
        st.caption("Showing a live preview of the selected algorithm. Press a Run button to save the run to history.")
        runs = {algorithm: ns.run_algorithm(graph, algorithm, start=start)}
    if len(runs) == 2:
        a, b = runs[ns.PRIM], runs[ns.KRUSKAL]
        same = abs(a.total_cost - b.total_cost) < 1e-6
        st.info(f"Prim cost {ui.inr(a.total_cost)} vs Kruskal cost {ui.inr(b.total_cost)} - "
                + ("**identical minimum cost** (selected edges can differ only when several MSTs exist)." if same else "**costs differ - this should never happen.**"))
    tabs = st.tabs(list(runs))
    for tab, (name, res) in zip(tabs, runs.items()):
        with tab:
            show_result(graph, res, key=f"mst_{name[:4]}")


def _dynamic_tab(graph) -> None:
    st.markdown("Change the network and see the **new minimum cost immediately**. Preview first, then apply to the database.")
    algorithm = ui.current_algorithm()
    names = ns.building_names(graph)
    ids = list(names)
    cby = {c["id"]: c for c in graph["connections"]}
    op = st.selectbox("Operation", ["Add a new building (with its first connection)", "Add a new cable connection",
                                    "Remove a possible connection", "Change cable installation costs"], key="dyn_op")
    change = None
    if op.startswith("Add a new building"):
        c1, c2 = st.columns(2)
        nonce = st.session_state.setdefault("dyn_nonce", 0)
        name = c1.text_input("New building name", key=f"dyn_b_name_{nonce}", placeholder="e.g. Sports Complex")
        target = c2.selectbox("Connect it to", ids, format_func=lambda i: names[i], key="dyn_b_target")
        d1, d2, d3, d4 = st.columns(4)
        dist = d1.number_input("Distance (m)", 0.0, value=120.0, step=10.0, key="dyn_b_dist")
        ctype = d2.selectbox("Cable type", db.CABLE_TYPES, key="dyn_b_type")
        cpm = d3.number_input("Cost per meter (₹)", 0.0, value=12.0, key="dyn_b_cpm")
        inst = d4.number_input("Installation charge (₹)", 0.0, value=800.0, step=100.0, key="dyn_b_inst")
        change = {"op": "add_building", "name": name, "connections": [
            {"connect_to": target, "distance_m": dist, "cable_type": ctype, "cost_per_meter": cpm, "install_charge": inst}]}
    elif op.startswith("Add a new cable"):
        if len(ids) < 2:
            st.info("Need at least two buildings.")
            return
        c1, c2 = st.columns(2)
        src = c1.selectbox("Source", ids, format_func=lambda i: names[i], key="dyn_c_src")
        dst = c2.selectbox("Destination", ids, index=1, format_func=lambda i: names[i], key="dyn_c_dst")
        d1, d2, d3, d4 = st.columns(4)
        dist = d1.number_input("Distance (m)", 0.0, value=100.0, step=10.0, key="dyn_c_dist")
        ctype = d2.selectbox("Cable type", db.CABLE_TYPES, key="dyn_c_type")
        cpm = d3.number_input("Cost per meter (₹)", 0.0, value=10.0, key="dyn_c_cpm")
        inst = d4.number_input("Installation charge (₹)", 0.0, value=500.0, step=100.0, key="dyn_c_inst")
        change = {"op": "add_connection", "source_id": src, "dest_id": dst, "distance_m": dist,
                  "cable_type": ctype, "cost_per_meter": cpm, "install_charge": inst}
    elif op.startswith("Remove"):
        if not cby:
            st.info("There are no connections to remove.")
            return
        cid = st.selectbox("Connection to remove", list(cby), format_func=lambda i: f"{ns.connection_label(cby[i])} - {ui.inr(cby[i]['total_cost'])}", key="dyn_r_sel")
        change = {"op": "remove_connection", "id": cid}
    else:
        if not cby:
            st.info("There are no connections to change.")
            return
        cid = st.selectbox("Connection to change", list(cby), format_func=lambda i: ns.connection_label(cby[i]), key="dyn_x_sel")
        c = cby[cid]
        d1, d2, d3 = st.columns(3)
        dist = d1.number_input("Distance (m)", 0.0, value=float(c["distance_m"]), key=f"dyn_x_dist_{cid}")
        cpm = d2.number_input("Cost per meter (₹)", 0.0, value=float(c["cost_per_meter"]), key=f"dyn_x_cpm_{cid}")
        inst = d3.number_input("Installation charge (₹)", 0.0, value=float(c["install_charge"]), step=100.0, key=f"dyn_x_inst_{cid}")
        change = {"op": "set_connection_cost", "id": cid, "distance_m": dist, "cost_per_meter": cpm, "install_charge": inst}

    if change["op"] == "add_building" and not change["name"].strip():
        st.info("Enter a name for the new building to preview its effect on the optimized network.")
        return
    try:
        new_graph = ns.apply_changes(graph, [change])
    except ValueError as e:
        st.error(str(e))
        return
    old = ns.run_algorithm(graph, algorithm, record_steps=False)
    new = ns.run_algorithm(new_graph, algorithm, record_steps=False)
    cmp = ns.compare_results(old, new)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Old minimum cost", ui.inr(cmp["old_cost"]))
    k2.metric("New minimum cost", ui.inr(cmp["new_cost"]), delta=f"{cmp['delta']:+,.0f} ₹", delta_color="inverse")
    k3.metric("Change", f"{cmp['delta_pct']:+.2f}%")
    k4.metric("Connectivity", "Connected" if new.connected else f"{new.num_components} parts")
    if not new.connected:
        st.warning("After this change the network is not fully connected.")
    nn = ns.building_names(new_graph)
    allnames = {**names, **nn}
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**Connections added to the optimized network**")
        rows = [{"Connection": f"{allnames[e.u]} - {allnames[e.v]}", "Cost": e.weight} for e in cmp["added"]]
        ui.show_df(pd.DataFrame(rows, columns=["Connection", "Cost"]))
    with cc2:
        st.markdown("**Connections dropped from the optimized network**")
        rows = [{"Connection": f"{allnames[e.u]} - {allnames[e.v]}", "Cost": e.weight} for e in cmp["removed"]]
        ui.show_df(pd.DataFrame(rows, columns=["Connection", "Cost"]))
    ui.plot(gv.build_graph_figure(new_graph, gv.mst_states(new), title="Updated optimized network",
                                  hide_states=("unprocessed",), height=380), "dyn_fig")
    if ui.button("Apply this change to the database", key="dyn_apply"):
        try:
            _apply_to_db(change)
            st.session_state["dyn_nonce"] = st.session_state.get("dyn_nonce", 0) + 1
            ui.flash("success", "Change applied. The optimized network was recalculated.")
            st.rerun()
        except db.ValidationError as e:
            st.error(str(e))


def _apply_to_db(change) -> None:
    op = change["op"]
    if op == "add_building":
        bid = db.add_building(change["name"])
        spec = change["connections"][0]
        try:
            db.add_connection(spec["connect_to"], bid, spec["distance_m"], spec["cable_type"],
                              spec["cost_per_meter"], spec["install_charge"])
        except db.ValidationError:
            db.delete_building(bid)
            raise
    elif op == "add_connection":
        db.add_connection(change["source_id"], change["dest_id"], change["distance_m"], change["cable_type"],
                          change["cost_per_meter"], change["install_charge"])
    elif op == "remove_connection":
        db.delete_connection(change["id"])
    elif op == "set_connection_cost":
        c = db.get_connection(change["id"])
        db.update_connection(c["id"], c["source_id"], c["dest_id"], change["distance_m"], c["cable_type"],
                             change["cost_per_meter"], change["install_charge"])


def _history_tab() -> None:
    results = db.get_optimization_results(limit=100)
    if not results:
        st.info("No optimization runs saved yet.")
        return
    df = pd.DataFrame([{"Run": r["id"], "Time": r["created_at"], "Algorithm": r["algorithm"],
                        "MST Cost": r["total_cost"], "Original Cost": r["original_cost"], "Savings": r["savings"],
                        "Savings %": round(r["savings_pct"], 2), "Edges": r["num_selected_edges"],
                        "Connected": bool(r["connected"]), "Time (ms)": round(r["execution_time_ms"], 4)} for r in results])
    ui.show_df(df)
    if ui.button("Clear history", key="clear_hist"):
        db.clear_history()
        st.rerun()


def render() -> None:
    ui.show_flash()
    ui.page_header("MST Optimization", "Run Prim's or Kruskal's algorithm to find the cheapest way to connect every building.")
    graph = ns.load_graph()
    if not ui.need_buildings(graph):
        return
    tab_run, tab_dyn, tab_hist = st.tabs(["Run Optimization", "Dynamic Optimization", "History"])
    with tab_run:
        _run_tab(graph)
    with tab_dyn:
        _dynamic_tab(graph)
    with tab_hist:
        _history_tab()
