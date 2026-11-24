"""Smart Network Cable Installation Cost Optimizer - Streamlit entry point.

Run with:  python -m streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Smart Network Cable Optimizer", page_icon="🔌", layout="wide",
                   initial_sidebar_state="expanded")

from database import db  # noqa: E402
from modules import (about, algorithm_comparison, animation, building_manager, cable_manager,  # noqa: E402
                     cost_analysis, dashboard, failure_simulation, graph_visualizer,
                     mst_optimization, network_service, report_generator, scenario_analysis, ui)

PAGES = {
    "📊 Dashboard": dashboard.render,
    "🏢 Building Management": building_manager.render,
    "🔌 Cable Connections": cable_manager.render,
    "🌲 MST Optimization": mst_optimization.render,
    "🕸️ Graph Visualization": graph_visualizer.render,
    "🎞️ Algorithm Animation": animation.render,
    "⚖️ Algorithm Comparison": algorithm_comparison.render,
    "💰 Cost Analysis": cost_analysis.render,
    "🛠️ Failure Simulation": failure_simulation.render,
    "🧪 Scenario Analysis": scenario_analysis.render,
    "📄 Reports": report_generator.render,
    "ℹ️ About Project": about.render,
}


@st.cache_resource
def _init_database() -> bool:
    db.ensure_ready()
    return True


def main() -> None:
    _init_database()
    ui.inject_css()
    with st.sidebar:
        st.markdown('<div class="brand"><div class="t">Smart Network Cable<br>Installation Cost Optimizer</div>'
                    '<div class="s">DAA PBL - Prim, Kruskal, MST, DSU</div></div>', unsafe_allow_html=True)
        page = st.radio("Navigation", list(PAGES), label_visibility="collapsed", key="nav_page")
        st.divider()
        st.selectbox("Active algorithm", network_service.ALGORITHMS, index=1, key="algorithm",
                     help="Used by the dashboard, visualisation, cost analysis, failure simulation, scenarios and reports.")
        try:
            graph = network_service.load_graph()
            res = network_service.run_algorithm(graph, ui.current_algorithm(), record_steps=False)
            st.caption(f"{len(graph['buildings'])} buildings - {len(graph['connections'])} routes")
            if graph["buildings"]:
                st.markdown(ui.badge("Network connected", "ok") if res.connected
                            else ui.badge(f"{res.num_components} disconnected parts", "bad"), unsafe_allow_html=True)
        except Exception as exc:  # keep the sidebar alive even if the DB is unreadable
            st.error(f"Database error: {exc}")
    try:
        PAGES[page]()
    except Exception as exc:  # last-resort guard so one page never crashes the whole app
        st.error(f"Something went wrong on this page: {exc}")
        st.exception(exc)


main()
