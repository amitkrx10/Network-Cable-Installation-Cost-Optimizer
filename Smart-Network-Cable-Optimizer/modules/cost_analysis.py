"""Page 8 - Cost optimization and analysis."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import network_service as ns
from . import ui


def render() -> None:
    ui.page_header("Cost Analysis", "How much the optimized network saves compared with laying every possible cable.")
    graph = ns.load_graph()
    if not ui.need_buildings(graph):
        return
    algorithm = ui.current_algorithm()
    result = ns.run_algorithm(graph, algorithm, record_steps=False)
    m = ns.cost_metrics(graph, result)
    sel = ns.mst_connections(graph, result)

    st.markdown(f"**Total cost of all possible connections** is what you would pay if every candidate route were installed. "
                f"**Optimized MST cost** is what you actually pay for the selected network ({algorithm}).")
    ui.kpi_row([
        ("All possible connections", ui.inr(m["original_cost"]), f"{m['num_connections']} routes", ui.AMBER),
        ("Optimized MST cost", ui.inr(m["mst_cost"]), f"{m['selected_edges']} routes installed", ui.GREEN),
        ("Money saved", ui.inr(m["savings"]), "Original - MST", ui.GREEN),
        ("Savings percentage", f"{m['savings_pct']:.2f}%", "Savings / Original x 100", ui.GREEN),
    ])
    st.latex(r"\text{Savings} = \text{Original Total} - \text{MST Cost} = "
             rf"{m['original_cost']:,.0f} - {m['mst_cost']:,.0f} = {m['savings']:,.0f}")
    if m["original_cost"] > 0:
        st.latex(r"\text{Savings \%} = \frac{\text{Savings}}{\text{Original Total}} \times 100 = "
                 rf"{m['savings_pct']:.2f}\%")

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Pie(labels=["Installed (MST)", "Saved"], values=[m["mst_cost"], max(m["savings"], 0)],
                               hole=0.55, marker_colors=[ui.GREEN, ui.GREY], textinfo="label+percent"))
        fig.update_layout(title="Share of total possible cost", height=340, margin=dict(l=10, r=10, t=50, b=10))
        ui.plot(fig, "cost_pie")
    with c2:
        if sel:
            df = ns.connections_df(sel)
            df["Link"] = df["From"].str.split(" - ").str[0] + " - " + df["To"].str.split(" - ").str[0]
            fig = px.bar(df, x="Link", y="Total Cost", color="Cable Type", text="Total Cost",
                         title="Cost of each selected connection (₹)")
            fig.update_layout(plot_bgcolor="white", height=340, yaxis=dict(gridcolor="#eef2f5"))
            ui.plot(fig, "cost_sel_bar")
        else:
            st.info("No connections selected.")

    st.subheader("Cost distribution by cable type")
    allc, selc = ns.cost_by_cable_type(graph["connections"]), ns.cost_by_cable_type(sel)
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**All possible connections**")
        ui.show_df(allc)
    with c4:
        st.markdown("**Selected (installed) network**")
        ui.show_df(selc)
    if not allc.empty:
        fig = go.Figure()
        fig.add_bar(x=allc["Cable Type"], y=allc["Total Cost"], name="All possible", marker_color=ui.GREY)
        fig.add_bar(x=selc["Cable Type"], y=selc["Total Cost"], name="Selected MST", marker_color=ui.GREEN)
        fig.update_layout(barmode="group", title="Cost by cable type: possible vs installed (₹)", height=340,
                          plot_bgcolor="white", yaxis=dict(gridcolor="#eef2f5"))
        ui.plot(fig, "cost_type_bar")

    st.subheader("Selected connection breakdown")
    ui.show_df(ns.connections_df(sel))
    if sel:
        top = max(sel, key=lambda c: c["total_cost"])
        st.caption(f"Most expensive installed link: {top['source_name']} - {top['dest_name']} at {ui.inr(top['total_cost'])} "
                   f"({top['total_cost'] / m['mst_cost'] * 100:.1f}% of the installed cost)." if m["mst_cost"] else "")
