"""Page 11 - Scenario analysis: compare what-if cost scenarios."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database import db
from . import graph_visualizer as gv
from . import network_service as ns
from . import ui


def _row(name, base_cost, ev):
    m = ev["metrics"]
    delta = m["mst_cost"] - base_cost
    return {"Scenario": name, "Buildings": m["num_buildings"], "Connections": m["num_connections"],
            "Total Possible Cost": m["original_cost"], "Optimized MST Cost": m["mst_cost"],
            "Change vs Normal": delta, "Change %": round(delta / base_cost * 100, 2) if base_cost else 0.0,
            "Connected": "Yes" if m["connected"] else "No"}


def _chart(df, key):
    colors = [ui.GREEN if c == 0 else (ui.RED if c > 0 else ui.TEAL) for c in df["Change vs Normal"]]
    fig = go.Figure(go.Bar(x=df["Scenario"], y=df["Optimized MST Cost"], marker_color=colors,
                           text=[ui.inr(v) for v in df["Optimized MST Cost"]], textposition="outside"))
    fig.update_layout(title="Optimized MST cost by scenario (₹)", plot_bgcolor="white", height=400,
                      yaxis=dict(gridcolor="#eef2f5"), margin=dict(b=120))
    fig.update_xaxes(tickangle=-25)
    ui.plot(fig, key)


def render() -> None:
    ui.show_flash()
    ui.page_header("Scenario Analysis", "Compare the optimized network under different cost and topology assumptions.")
    graph = ns.load_graph()
    if not ui.need_buildings(graph, 2):
        return
    algorithm = ui.current_algorithm()
    base_eval = ns.evaluate_scenario(graph, [], algorithm)
    base_cost = base_eval["metrics"]["mst_cost"]

    tab_p, tab_c, tab_s = st.tabs(["Standard Scenarios", "Custom Scenario Builder", "Saved Scenarios"])

    with tab_p:
        rows, evals = [], {}
        for name, changes in ns.preset_scenarios(graph, algorithm):
            ev = ns.evaluate_scenario(graph, changes, algorithm)
            rows.append(_row(name, base_cost, ev))
            evals[name] = ev
        df = pd.DataFrame(rows)
        ui.show_df(df)
        _chart(df, "scn_preset_chart")
        pick = st.selectbox("Inspect scenario network", list(evals), key="scn_pick")
        ev = evals[pick]
        c1, c2, c3 = st.columns(3)
        c1.metric("MST cost", ui.inr(ev["metrics"]["mst_cost"]), delta=f"{ev['metrics']['mst_cost'] - base_cost:+,.0f} ₹", delta_color="inverse")
        c2.metric("Selected connections", ev["metrics"]["selected_edges"])
        c3.metric("Connectivity", "Connected" if ev["metrics"]["connected"] else "Disconnected")
        ui.plot(gv.build_graph_figure(ev["graph"], gv.mst_states(ev["result"]), title=pick, height=420,
                                      labels={"unprocessed": "Not selected"}), "scn_preset_fig")
        ui.show_df(ns.connections_df(ns.mst_connections(ev["graph"], ev["result"])))

    with tab_c:
        names = ns.building_names(graph)
        cby = {c["id"]: c for c in graph["connections"]}
        st.markdown("Combine any of the changes below, preview the result, and optionally save the scenario.")
        c1, c2 = st.columns(2)
        ctype = c1.selectbox("Cable type to re-price", ["ALL"] + db.CABLE_TYPES, key="cs_type")
        pct = c1.slider("Cable cost change (%)", -50, 200, 0, key="cs_pct")
        ipct = c2.slider("Installation charge change (%)", -100, 200, 0, key="cs_ipct")
        removed = st.multiselect("Remove connections", list(cby), format_func=lambda i: ns.connection_label(cby[i]), key="cs_rm")
        add_b = st.checkbox("Add a new building", key="cs_add")
        changes = []
        if pct:
            changes.append({"op": "scale_cable_cost", "cable_type": ctype, "percent": pct})
        if ipct:
            changes.append({"op": "scale_install_charge", "percent": ipct})
        changes += [{"op": "remove_connection", "id": i} for i in removed]
        if add_b:
            d1, d2, d3 = st.columns(3)
            bname = d1.text_input("New building name", "New Building", key="cs_bname")
            target = d2.selectbox("Connect to", list(names), format_func=lambda i: names[i], key="cs_btarget")
            dist = d3.number_input("Distance (m)", 0.0, value=150.0, step=10.0, key="cs_bdist")
            e1, e2, e3 = st.columns(3)
            bt = e1.selectbox("Cable type", db.CABLE_TYPES, key="cs_btype")
            cpm = e2.number_input("Cost per meter (₹)", 0.0, value=12.0, key="cs_bcpm")
            inst = e3.number_input("Installation charge (₹)", 0.0, value=800.0, step=100.0, key="cs_binst")
            changes.append({"op": "add_building", "name": bname, "connections": [
                {"connect_to": target, "distance_m": dist, "cable_type": bt, "cost_per_meter": cpm, "install_charge": inst}]})
        try:
            g2 = ns.apply_changes(graph, changes, strict=True)
        except ValueError as e:
            st.error(str(e))
            g2 = None
        if g2 is not None:
            res = ns.run_algorithm(g2, algorithm, record_steps=False)
            m = ns.cost_metrics(g2, res)
            k1, k2, k3 = st.columns(3)
            k1.metric("Baseline MST cost", ui.inr(base_cost))
            k2.metric("Scenario MST cost", ui.inr(m["mst_cost"]), delta=f"{m['mst_cost'] - base_cost:+,.0f} ₹", delta_color="inverse")
            k3.metric("Connectivity", "Connected" if res.connected else f"{res.num_components} parts")
            ui.plot(gv.build_graph_figure(g2, gv.mst_states(res), title="Scenario - optimized network",
                                          hide_states=("unprocessed",), height=380), "scn_custom_fig")
            sname = st.text_input("Scenario name", key="cs_name", placeholder="e.g. Fiber +50% and drop C-E")
            sdesc = st.text_input("Description (optional)", key="cs_desc")
            if ui.button("Save scenario", key="cs_save"):
                try:
                    db.save_scenario(sname, sdesc, changes, base_cost, m["mst_cost"], res.connected)
                    ui.flash("success", f"Scenario '{sname.strip()}' saved.")
                    st.rerun()
                except db.ValidationError as e:
                    st.error(str(e))

    with tab_s:
        saved = db.get_scenarios()
        if not saved:
            st.info("No saved scenarios yet. Build one in the **Custom Scenario Builder** tab.")
        else:
            rows = []
            for s in saved:
                ev = ns.evaluate_scenario(graph, s["changes"], algorithm, strict=False)
                r = _row(s["name"], base_cost, ev)
                r["Saved MST Cost"] = s["optimized_cost"]
                rows.append(r)
            df = pd.DataFrame(rows)
            ui.show_df(df)
            st.caption("'Optimized MST Cost' is recalculated on the current network; 'Saved MST Cost' is the value when the scenario was saved.")
            _chart(df, "scn_saved_chart")
            by = {s["id"]: s for s in saved}
            did = st.selectbox("Delete scenario", list(by), format_func=lambda i: by[i]["name"], key="scn_del_sel")
            if ui.button("Delete selected scenario", key="scn_del_btn"):
                db.delete_scenario(did)
                ui.flash("success", "Scenario deleted.")
                st.rerun()
