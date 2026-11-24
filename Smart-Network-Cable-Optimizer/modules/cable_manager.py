"""Page 3 - Cable Connection Management (CRUD, filters, live cost preview)."""
from __future__ import annotations

import streamlit as st

from database import db
from . import network_service as ns
from . import ui


def _cost_inputs(prefix: str, defaults: dict):
    c1, c2, c3 = st.columns(3)
    dist = c1.number_input("Cable distance (m)", min_value=0.0, value=float(defaults["distance_m"]), step=10.0, key=f"{prefix}_dist")
    cpm = c2.number_input("Cost per meter (₹)", min_value=0.0, value=float(defaults["cost_per_meter"]), step=1.0, key=f"{prefix}_cpm")
    inst = c3.number_input("Additional installation charge (₹)", min_value=0.0, value=float(defaults["install_charge"]), step=100.0, key=f"{prefix}_inst")
    st.info(f"**Total cost** = ({dist:g} m × {ui.inr(cpm)}/m) + {ui.inr(inst)} = **{ui.inr(dist * cpm + inst)}**")
    return dist, cpm, inst


def render() -> None:
    ui.page_header("Cable Connections", "Define every possible cable route between buildings and its installation cost.")
    ui.show_flash()
    buildings = db.get_buildings()
    conns = db.get_connections()
    by_id = {b["id"]: b for b in buildings}
    tab_view, tab_add, tab_edit, tab_del = st.tabs(["All Connections", "Add Connection", "Edit Connection", "Delete Connection"])

    with tab_view:
        if not conns:
            st.info("No connections yet. Use **Add Connection**.")
        else:
            f1, f2, f3 = st.columns([2, 2, 2])
            types = sorted({c["cable_type"] for c in conns})
            sel_types = f1.multiselect("Cable type", types, default=types, key="cab_f_type")
            sel_b = f2.multiselect("Involving building", list(by_id), format_func=lambda i: by_id[i]["name"], key="cab_f_bld")
            hi = max(c["total_cost"] for c in conns)
            lo_hi = f3.slider("Total cost range (₹)", 0.0, float(hi), (0.0, float(hi)), key="cab_f_cost") if hi > 0 else (0.0, 0.0)
            shown = [c for c in conns if c["cable_type"] in sel_types and lo_hi[0] <= c["total_cost"] <= lo_hi[1]
                     and (not sel_b or c["source_id"] in sel_b or c["dest_id"] in sel_b)]
            st.caption(f"Showing {len(shown)} of {len(conns)} connections - total {ui.inr(sum(c['total_cost'] for c in shown))}")
            ui.show_df(ns.connections_df(shown))

    with tab_add:
        if len(buildings) < 2:
            st.info("Add at least two buildings first.")
        else:
            n = st.session_state.setdefault("cab_nonce", 0)
            ids = list(by_id)
            c1, c2, c3 = st.columns(3)
            src = c1.selectbox("Source building", ids, format_func=lambda i: _fmt(by_id[i]), key=f"cab_src_{n}")
            dst = c2.selectbox("Destination building", ids, index=1, format_func=lambda i: _fmt(by_id[i]), key=f"cab_dst_{n}")
            ctype = c3.selectbox("Cable type", db.CABLE_TYPES, key=f"cab_type_{n}")
            dist, cpm, inst = _cost_inputs(f"cab_add_{n}", {"distance_m": 100.0, "cost_per_meter": 10.0, "install_charge": 500.0})
            if src == dst:
                st.error("Source and destination must be different buildings (self-loops are not allowed).")
            if ui.button("Add connection", key=f"cab_add_btn_{n}", disabled=(src == dst)):
                try:
                    db.add_connection(src, dst, dist, ctype, cpm, inst)
                    st.session_state["cab_nonce"] = n + 1
                    ui.flash("success", "Connection added.")
                    st.rerun()
                except db.ValidationError as e:
                    st.error(str(e))

    with tab_edit:
        if not conns:
            st.info("There are no connections to edit.")
        else:
            cby = {c["id"]: c for c in conns}
            cid = st.selectbox("Select connection", list(cby), format_func=lambda i: ns.connection_label(cby[i]), key="cab_edit_sel")
            c = cby[cid]
            ids = list(by_id)
            e1, e2, e3 = st.columns(3)
            src = e1.selectbox("Source building", ids, index=ids.index(c["source_id"]), format_func=lambda i: _fmt(by_id[i]), key=f"cab_e_src_{cid}")
            dst = e2.selectbox("Destination building", ids, index=ids.index(c["dest_id"]), format_func=lambda i: _fmt(by_id[i]), key=f"cab_e_dst_{cid}")
            types = db.CABLE_TYPES if c["cable_type"] in db.CABLE_TYPES else db.CABLE_TYPES + [c["cable_type"]]
            ctype = e3.selectbox("Cable type", types, index=types.index(c["cable_type"]), key=f"cab_e_type_{cid}")
            dist, cpm, inst = _cost_inputs(f"cab_e_{cid}", c)
            if ui.button("Save changes", key=f"cab_e_save_{cid}"):
                try:
                    db.update_connection(cid, src, dst, dist, ctype, cpm, inst)
                    ui.flash("success", "Connection updated.")
                    st.rerun()
                except db.ValidationError as e:
                    st.error(str(e))

    with tab_del:
        if not conns:
            st.info("There are no connections to delete.")
        else:
            cby = {c["id"]: c for c in conns}
            cid = st.selectbox("Select connection to delete", list(cby), format_func=lambda i: ns.connection_label(cby[i]), key="cab_del_sel")
            st.warning(f"This removes the route costing {ui.inr(cby[cid]['total_cost'])}.")
            if ui.button("Delete connection", key=f"cab_del_btn_{cid}"):
                try:
                    db.delete_connection(cid)
                    ui.flash("success", "Connection deleted.")
                    st.rerun()
                except db.ValidationError as e:
                    st.error(str(e))


def _fmt(b) -> str:
    return f"{b['code']} - {b['name']}"
