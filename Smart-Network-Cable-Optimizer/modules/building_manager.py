"""Page 2 - Building Management (CRUD + search + data tools)."""
from __future__ import annotations

import streamlit as st

from database import db
from . import network_service as ns
from . import ui


def _label(b) -> str:
    return f"{b['code']} - {b['name']}"


def render() -> None:
    ui.page_header("Building Management", "Add, edit, search and remove the buildings that must be connected.")
    ui.show_flash()
    buildings = db.get_buildings()
    tab_view, tab_add, tab_edit, tab_del, tab_tools = st.tabs(
        ["View & Search", "Add Building", "Edit Building", "Delete Building", "Data Tools"])

    with tab_view:
        q = st.text_input("Search buildings by name, code, ID or description", key="bld_search")
        found = db.get_buildings(search=q)
        st.caption(f"Showing {len(found)} of {len(buildings)} buildings")
        ui.show_df(ns.buildings_df({"buildings": found, "connections": []}))

    with tab_add:
        with st.form("add_building_form", clear_on_submit=True):
            c1, c2 = st.columns([2, 1])
            name = c1.text_input("Building name *", placeholder="e.g. Sports Complex")
            code = c2.text_input("Building code (optional)", placeholder="auto (A, B, C ...)")
            desc = st.text_area("Description (optional)", height=80)
            submitted = st.form_submit_button("Add building")
        if submitted:
            try:
                bid = db.add_building(name, code or None, desc)
                ui.flash("success", f"Building added (ID {bid}).")
                st.rerun()
            except db.ValidationError as e:
                st.error(str(e))

    with tab_edit:
        if not buildings:
            st.info("There are no buildings to edit.")
        else:
            by_id = {b["id"]: b for b in buildings}
            bid = st.selectbox("Select building", list(by_id), format_func=lambda i: _label(by_id[i]), key="bld_edit_sel")
            b = by_id[bid]
            c1, c2 = st.columns([2, 1])
            name = c1.text_input("Building name", b["name"], key=f"bld_edit_name_{bid}")
            code = c2.text_input("Building code", b["code"], key=f"bld_edit_code_{bid}")
            desc = st.text_area("Description", b["description"], key=f"bld_edit_desc_{bid}", height=80)
            if ui.button("Save changes", key=f"bld_edit_save_{bid}"):
                try:
                    db.update_building(bid, name, code, desc)
                    ui.flash("success", "Building updated.")
                    st.rerun()
                except db.ValidationError as e:
                    st.error(str(e))

    with tab_del:
        if not buildings:
            st.info("There are no buildings to delete.")
        else:
            by_id = {b["id"]: b for b in buildings}
            bid = st.selectbox("Select building to delete", list(by_id), format_func=lambda i: _label(by_id[i]), key="bld_del_sel")
            n = by_id[bid]["connection_count"]
            st.warning(f"Deleting **{by_id[bid]['name']}** also removes its {n} cable connection(s).")
            confirm = st.checkbox("I understand this cannot be undone", key=f"bld_del_ok_{bid}")
            if ui.button("Delete building", key=f"bld_del_btn_{bid}", disabled=not confirm):
                try:
                    removed = db.delete_building(bid)
                    ui.flash("success", f"Building deleted along with {removed} connection(s).")
                    st.rerun()
                except db.ValidationError as e:
                    st.error(str(e))

    with tab_tools:
        st.markdown("**Reset to sample campus network** - replaces all buildings, connections, results and scenarios "
                    "with the six-building sample network (expected MST cost ₹13,000).")
        ok = st.checkbox("Yes, replace all current data", key="reset_ok")
        if ui.button("Reset to sample data", key="reset_btn", disabled=not ok):
            counts = db.seed_sample_data(reset=True)
            ui.flash("success", f"Sample data loaded: {counts['buildings']} buildings, {counts['connections']} connections.")
            st.rerun()
