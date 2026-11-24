"""Page 10 - Network failure simulation."""
from __future__ import annotations

import streamlit as st

from . import graph_visualizer as gv
from . import network_service as ns
from . import ui


def render() -> None:
    ui.page_header("Failure Simulation", "Break an installed connection and see which buildings lose service and how to recover.")
    graph = ns.load_graph()
    if not ui.need_buildings(graph, 2):
        return
    algorithm = ui.current_algorithm()
    base = ns.run_algorithm(graph, algorithm, record_steps=False)
    if not base.mst_edges:
        st.info("There is no installed network yet - add cable connections first.")
        return
    if not base.connected:
        st.warning("The network is currently disconnected; the simulation uses the minimum spanning forest.")
    st.info("**Important:** an ordinary MST contains *no redundant paths*. It is a tree, so the failure of **any** "
            "selected connection disconnects the installed network into two parts until a replacement is built.")

    inst = ns.mst_connections(graph, base)
    by_id = {c["id"]: c for c in inst}
    fid = st.selectbox("Installed connection to fail", list(by_id), key="fail_sel",
                       format_func=lambda i: f"{ns.connection_label(by_id[i])} - {ui.inr(by_id[i]['total_cost'])}")
    sim = ns.simulate_failure(graph, fid, algorithm)
    names = ns.building_names(graph)
    pos = gv.compute_layout(graph)
    f = sim["failed"]

    ui.kpi_row([
        ("Failed link", f"{f['source_code']} - {f['dest_code']}", ui.inr(f["total_cost"]), ui.RED),
        ("Network parts", f"{len(sim['components'])}", "connected components after failure", ui.AMBER),
        ("Buildings cut off", f"{len(sim['isolated'])}", ", ".join(names[i] for i in sim["isolated"])[:60], ui.RED),
        ("Cost of recovery", ui.inr(sim["extra_cost"]) if sim["restorable"] else "n/a",
         "extra vs. original MST" if sim["restorable"] else "no alternative route", ui.GREEN if sim["restorable"] else ui.RED),
    ])

    palette = {}
    for i, comp in enumerate(sim["components"]):
        for b in comp:
            palette[b] = gv.PALETTE[i % len(gv.PALETTE)]
    states = {e.eid: "selected" for e in sim["base"].mst_edges}
    states[fid] = "failed"
    t1, t2 = st.tabs(["During the failure", "After recovery"])
    with t1:
        st.markdown("Each colour is a separate, now-disconnected part of the network. The dashed red link has failed.")
        ui.plot(gv.build_graph_figure(graph, states, positions=pos, node_colors=palette, height=480,
                                      title="Installed network with failed connection",
                                      labels={"unprocessed": "Available alternative"}), "fail_before")
        c1, c2 = st.columns(2)
        c1.markdown("**Main part** (keeps service)")
        c1.write(", ".join(names[i] for i in sim["main"]))
        c2.markdown("**Affected buildings** (isolated part)")
        c2.write(", ".join(names[i] for i in sim["isolated"]))
    with t2:
        r = sim["replacement"]
        if r is None:
            st.error("No alternative cable route exists between the two parts. The network stays split until a "
                     "new connection is added in **Cable Connections**.")
        else:
            st.success(f"Cheapest replacement: **{r['source_name']} - {r['dest_name']}** at {ui.inr(r['total_cost'])} "
                       f"(failed link cost {ui.inr(f['total_cost'])}).")
            st2 = {e.eid: "selected" for e in sim["new_result"].mst_edges}
            st2[r["id"]] = "replacement"
            ui.plot(gv.build_graph_figure(sim["new_graph"], st2, positions=pos, height=480,
                                          title="Re-optimized network after recalculating the MST",
                                          hide_states=("unprocessed",)), "fail_after")
            k1, k2, k3 = st.columns(3)
            k1.metric("Original MST cost", ui.inr(sim["base"].total_cost))
            k2.metric("New MST cost", ui.inr(sim["new_result"].total_cost), delta=f"{sim['extra_cost']:+,.0f} ₹", delta_color="inverse")
            k3.metric("Network", "Connected" if sim["new_result"].connected else "Disconnected")
            st.caption(f"Check: original cost - failed link + replacement = {ui.inr(sim['expected_cost'])} "
                       + ("matches the recalculated MST ✅" if sim["consistent"] else "does not match ❌"))
    st.subheader("Alternative connections that could restore service")
    if sim["candidates"]:
        ui.show_df(ns.connections_df(sim["candidates"]))
    else:
        st.write("None.")

    st.subheader("Criticality of every installed link")
    if len(base.mst_edges) <= 80:
        table = ns.criticality_table(graph, algorithm)
        ui.show_df(table)
        crit = int((table["Critical"] == "Yes").sum())
        st.caption(f"{crit} of {len(table)} installed links have no alternative route (bridges).")
    else:
        st.caption("Criticality table is skipped for networks larger than 80 installed links.")
