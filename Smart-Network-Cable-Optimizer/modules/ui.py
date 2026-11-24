"""Shared Streamlit UI helpers: theme CSS, KPI cards, width-aware widgets, flash messages."""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

import pandas as pd
import streamlit as st

INK = "#14232f"
TEAL = "#0e7490"
GREEN = "#16a34a"
RED = "#dc2626"
AMBER = "#f59e0b"
GREY = "#9ca3af"
BLUE = "#2563eb"

_CSS = """
<style>
.block-container {padding-top: 4.5rem !important; padding-bottom: 3rem; max-width: 1400px;}
header[data-testid="stHeader"] {background: #f6f8fa;}
section[data-testid="stSidebar"] > div:first-child {padding-top: 1.5rem;}
section[data-testid="stSidebar"] {background: #eaf0f4; border-right: 1px solid #d3dde5;}
.brand {background: #14232f; color: #fff; padding: 14px 16px; border-radius: 10px; margin-bottom: 10px;}
.brand .t {font-size: 1.05rem; font-weight: 700; line-height: 1.25;}
.brand .s {font-size: .75rem; color: #9fb6c6; margin-top: 3px;}
.page-head {border-left: 6px solid #0e7490; padding: 6px 0 6px 14px; margin-bottom: 14px;}
.page-head h1 {font-size: 1.75rem; margin: 0; padding: 0; color: #14232f !important; line-height: 1.3;}
.page-head p {margin: 2px 0 0 0; color: #51697a; font-size: .95rem;}
.kpi {background: #fff; border: 1px solid #d9e2e9; border-top: 4px solid var(--c); border-radius: 8px;
      padding: 12px 14px; min-height: 96px; margin-bottom: 10px;}
.kpi .l {font-size: .78rem; color: #51697a; font-weight: 600;}
.kpi .v {font-size: 1.55rem; font-weight: 700; color: #14232f; line-height: 1.25; word-break: break-word;}
.kpi .s {font-size: .75rem; color: #6b8190;}
.badge {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .8rem; font-weight: 600;}
.badge.ok {background: #dcfce7; color: #166534;} .badge.bad {background: #fee2e2; color: #991b1b;}
.badge.warn {background: #fef3c7; color: #92400e;} .badge.info {background: #dbeafe; color: #1e40af;}
.stepbox {background: #fff; border: 1px solid #d9e2e9; border-radius: 8px; padding: 14px 16px;}
.stepbox.sel {border-left: 6px solid #16a34a;} .stepbox.rej {border-left: 6px solid #dc2626;}
.stepbox.idle {border-left: 6px solid #9ca3af;}
.stepbox h4 {margin: 0 0 6px 0;} .stepbox .row {margin: 2px 0; font-size: .93rem;}
div[data-testid="stMetric"] {background: #fff; border: 1px solid #d9e2e9; border-radius: 8px; padding: 8px 12px;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- width-aware widgets
def _stretch_supported() -> bool:
    m = re.match(r"(\d+)\.(\d+)", st.__version__)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (1, 50)


_WIDE = {"width": "stretch"} if _stretch_supported() else {"use_container_width": True}


def show_df(df: pd.DataFrame, **kwargs) -> None:
    st.dataframe(df, hide_index=True, **_WIDE, **kwargs)


def plot(fig, key: str) -> None:
    st.plotly_chart(fig, key=key, config={"scrollZoom": True, "displaylogo": False}, **_WIDE)


def button(label: str, key: Optional[str] = None, **kwargs) -> bool:
    return st.button(label, key=key, **_WIDE, **kwargs)


def download_button(label: str, data, file_name: str, mime: str, key: str, **kwargs) -> None:
    st.download_button(label, data=data, file_name=file_name, mime=mime, key=key, **_WIDE, **kwargs)


# ---------------------------------------------------------------- formatting
def inr(x: Optional[float]) -> str:
    if x is None:
        return "-"
    x = float(x)
    return f"₹{x:,.0f}" if abs(x - round(x)) < 0.005 else f"₹{x:,.2f}"


def current_algorithm() -> str:
    return st.session_state.get("algorithm", "Kruskal's Algorithm")


# ---------------------------------------------------------------- components
def page_header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="page-head"><h1>{title}</h1>{sub}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "", color: str = TEAL) -> str:
    return (f'<div class="kpi" style="--c:{color}"><div class="l">{label}</div>'
            f'<div class="v">{value}</div><div class="s">{sub or "&nbsp;"}</div></div>')


def kpi_row(items: Iterable[Tuple[str, str, str, str]]) -> None:
    items = list(items)
    cols = st.columns(len(items))
    for col, (label, value, sub, color) in zip(cols, items):
        col.markdown(kpi_card(label, value, sub, color), unsafe_allow_html=True)


def badge(text: str, kind: str = "info") -> str:
    return f'<span class="badge {kind}">{text}</span>'


def flash(kind: str, message: str) -> None:
    """Queue a message that survives the next st.rerun()."""
    st.session_state["_flash"] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        kind, message = item
        {"success": st.success, "error": st.error, "warning": st.warning}.get(kind, st.info)(message)


def need_buildings(graph, minimum: int = 1) -> bool:
    if len(graph["buildings"]) < minimum:
        st.info(f"Add at least {minimum} building{'s' if minimum > 1 else ''} in **Building Management** to use this page.")
        return False
    return True
