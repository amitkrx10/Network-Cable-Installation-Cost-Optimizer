"""Page 12 - Report generation: PDF (ReportLab) and CSV exports."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import graph_visualizer as gv
from . import network_service as ns
from . import ui

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
NAVY, TEAL, GREEN = colors.HexColor("#14232f"), colors.HexColor("#0e7490"), colors.HexColor("#16a34a")


def rs(x) -> str:
    """Rupee amount for the PDF. Built-in PDF fonts have no rupee glyph, so 'Rs.' is used."""
    return f"Rs. {float(x):,.0f}" if abs(float(x) - round(float(x))) < 0.005 else f"Rs. {float(x):,.2f}"


# ------------------------------------------------------------------ CSV
def build_csv_exports(graph: ns.Graph, result, metrics: dict) -> Dict[str, bytes]:
    sel = ns.mst_connections(graph, result)
    sel_ids = {c["id"] for c in sel}
    mst_df = ns.connections_df(sel)
    mst_df.insert(0, "Algorithm", result.algorithm)
    cost_rows = [
        ("Algorithm", result.algorithm), ("Buildings", metrics["num_buildings"]),
        ("Possible connections", metrics["num_connections"]),
        ("Total cost of all possible connections", metrics["original_cost"]),
        ("Minimum (MST) installation cost", metrics["mst_cost"]), ("Selected connections", metrics["selected_edges"]),
        ("Savings", metrics["savings"]), ("Savings percentage", round(metrics["savings_pct"], 4)),
        ("Connected", metrics["connected"]), ("Execution time (ms)", round(result.execution_time_ms, 6)),
        ("Time complexity", result.time_complexity), ("Space complexity", result.space_complexity)]
    cost_df = pd.DataFrame(cost_rows, columns=["Metric", "Value"])
    by_type = ns.cost_by_cable_type(graph["connections"]).rename(columns={"Total Cost": "All Possible Cost", "Connections": "All Possible Connections"})
    sel_type = ns.cost_by_cable_type(sel).rename(columns={"Total Cost": "Selected MST Cost", "Connections": "Selected Connections"})
    type_df = by_type.merge(sel_type, on="Cable Type", how="left").fillna(0)
    enc = lambda df: df.to_csv(index=False).encode("utf-8-sig")
    return {"buildings.csv": enc(ns.buildings_df(graph)),
            "cable_connections.csv": enc(ns.connections_df(graph["connections"], sel_ids)),
            "mst_results.csv": enc(mst_df), "cost_analysis.csv": enc(cost_df),
            "cost_by_cable_type.csv": enc(type_df)}


def zip_csvs(files: Dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


# ------------------------------------------------------------------ PDF
def _graph_drawing(graph: ns.Graph, result, width=480, height=300) -> Drawing:
    d = Drawing(width, height)
    pos = gv.compute_layout(graph)
    if not pos:
        return d
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad_x, pad_y = 70, 40

    def sc(p):
        x = pad_x + ((p[0] - minx) / (maxx - minx) if maxx > minx else 0.5) * (width - 2 * pad_x - 90)
        y = pad_y + ((p[1] - miny) / (maxy - miny) if maxy > miny else 0.5) * (height - 2 * pad_y)
        return x, y
    sel = {e.eid for e in result.mst_edges}
    small = len(graph["connections"]) <= 40
    for c in sorted(graph["connections"], key=lambda c: c["id"] in sel):
        (x0, y0), (x1, y1) = sc(pos[c["source_id"]]), sc(pos[c["dest_id"]])
        chosen = c["id"] in sel
        d.add(Line(x0, y0, x1, y1, strokeColor=GREEN if chosen else colors.HexColor("#b8c0c8"),
                   strokeWidth=3 if chosen else 1))
        if small:
            d.add(String((x0 + x1) / 2, (y0 + y1) / 2 + 3, f"{c['total_cost']:,.0f}", fontSize=6.5,
                         fillColor=GREEN if chosen else colors.HexColor("#6b7280"), textAnchor="middle"))
    show_names = len(graph["buildings"]) <= 30
    for b in graph["buildings"]:
        x, y = sc(pos[b["id"]])
        d.add(Circle(x, y, 9, fillColor=NAVY, strokeColor=colors.white))
        d.add(String(x, y - 2.5, b["code"][:3], fontSize=7, fillColor=colors.white, textAnchor="middle"))
        if show_names:
            d.add(String(x, y - 19, b["name"][:24], fontSize=7, fillColor=NAVY, textAnchor="middle"))
    lx = width - 95
    d.add(Rect(lx - 6, height - 52, 96, 44, fillColor=colors.white, strokeColor=colors.HexColor("#d9e2e9")))
    d.add(Line(lx, height - 22, lx + 18, height - 22, strokeColor=GREEN, strokeWidth=3))
    d.add(String(lx + 23, height - 25, "Selected (MST)", fontSize=7))
    d.add(Line(lx, height - 40, lx + 18, height - 40, strokeColor=colors.HexColor("#b8c0c8"), strokeWidth=1))
    d.add(String(lx + 23, height - 43, "Not selected", fontSize=7))
    return d


def _table(data, widths, header_color=NAVY, align_right=()):
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), header_color), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
             ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5dc")),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f8")]),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for col in align_right:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def build_pdf_report(graph: ns.Graph, result, metrics: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, title="Smart Network Cable Installation Cost Optimizer",
                            author="Smart Network Cable Optimizer")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=NAVY, fontSize=20, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=TEAL, fontSize=13, spaceBefore=10, spaceAfter=5)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    cell = ParagraphStyle("c", parent=body, fontSize=8, leading=10)
    P = lambda t, s=body: Paragraph(escape(str(t)), s)
    story = [P("Smart Network Cable Installation Cost Optimizer", h1),
             P(f"Network planning report - generated {datetime.now():%d %b %Y, %H:%M}", body), Spacer(1, 8)]

    story.append(P("1. Problem and result summary", h2))
    story.append(P("Connect every building of the campus with the minimum total cable installation cost. The network is "
                   "modelled as a weighted undirected graph and solved as a Minimum Spanning Tree (MST).", body))
    summary = [["Metric", "Value"],
               ["Algorithm used", result.algorithm], ["Buildings", metrics["num_buildings"]],
               ["Possible cable connections", metrics["num_connections"]],
               ["Total cost of all possible connections", rs(metrics["original_cost"])],
               ["Total minimum installation cost (MST)", rs(metrics["mst_cost"])],
               ["Selected connections", metrics["selected_edges"]],
               ["Cost savings", rs(metrics["savings"])], ["Savings percentage", f"{metrics['savings_pct']:.2f}%"],
               ["Network connected", "Yes" if result.connected else f"No ({result.num_components} separate parts)"]]
    story += [Spacer(1, 4), _table(summary, [8.5 * cm, 8.5 * cm])]

    story.append(P("2. Building information", h2))
    rows = [["ID", "Code", "Name", "Description", "Links"]] + [
        [b["id"], b["code"], Paragraph(escape(b["name"]), cell), Paragraph(escape(b["description"] or "-"), cell),
         b["connection_count"]] for b in graph["buildings"]]
    story.append(_table(rows, [1.2 * cm, 1.5 * cm, 5 * cm, 7.3 * cm, 1.5 * cm]))

    story.append(P("3. All possible cable connections", h2))
    sel_ids = {e.eid for e in result.mst_edges}
    rows = [["From", "To", "Dist (m)", "Cable", "Rs./m", "Install", "Total", "MST"]]
    for c in graph["connections"]:
        rows.append([Paragraph(escape(c["source_name"]), cell), Paragraph(escape(c["dest_name"]), cell),
                     f"{c['distance_m']:g}", Paragraph(escape(c["cable_type"]), cell), f"{c['cost_per_meter']:g}",
                     f"{c['install_charge']:,.0f}", f"{c['total_cost']:,.0f}", "Yes" if c["id"] in sel_ids else "-"])
    story.append(_table(rows, [3.3 * cm, 3.3 * cm, 1.6 * cm, 2.4 * cm, 1.4 * cm, 1.7 * cm, 2 * cm, 1.3 * cm], align_right=(2, 4, 5, 6)))

    story.append(P("4. Selected MST connections", h2))
    rows = [["#", "From", "To", "Cable", "Cost"]]
    for i, c in enumerate(ns.mst_connections(graph, result), 1):
        rows.append([i, Paragraph(escape(c["source_name"]), cell), Paragraph(escape(c["dest_name"]), cell),
                     Paragraph(escape(c["cable_type"]), cell), rs(c["total_cost"])])
    rows.append(["", "", "", "Total", rs(result.total_cost)])
    story.append(_table(rows, [1 * cm, 5.5 * cm, 5.5 * cm, 2.5 * cm, 2.5 * cm], header_color=GREEN, align_right=(4,)))

    story.append(P("5. Network graph", h2))
    story.append(_graph_drawing(graph, result))
    story.append(P("Green edges are the installed MST connections; grey edges are possible connections that were not selected.", body))

    story.append(PageBreak())
    story.append(P("6. Algorithm performance and complexity", h2))
    prim = ns.run_algorithm(graph, ns.PRIM, record_steps=False)
    kru = ns.run_algorithm(graph, ns.KRUSKAL, record_steps=False)
    rows = [["Property", "Prim's Algorithm", "Kruskal's Algorithm"],
            ["Minimum cost", rs(prim.total_cost), rs(kru.total_cost)],
            ["Selected edges", prim.selected_count, kru.selected_count],
            ["Edges processed", prim.edges_processed, kru.edges_processed],
            ["Edges rejected", prim.edges_rejected, kru.edges_rejected],
            ["Execution time (single run)", f"{prim.execution_time_ms:.4f} ms", f"{kru.execution_time_ms:.4f} ms"],
            ["Time complexity", prim.time_complexity, kru.time_complexity],
            ["Space complexity", prim.space_complexity, kru.space_complexity]]
    story.append(_table(rows, [5 * cm, 6 * cm, 6 * cm]))
    story.append(P(f"Selected algorithm for this report: {result.algorithm} "
                   f"(execution time {result.execution_time_ms:.4f} ms, measured with time.perf_counter()).", body))

    story.append(P("7. Final conclusion", h2))
    if result.connected:
        concl = (f"Using {result.algorithm}, all {metrics['num_buildings']} buildings can be connected with "
                 f"{metrics['selected_edges']} cable links for a minimum total installation cost of {rs(metrics['mst_cost'])}. "
                 f"Compared with installing all {metrics['num_connections']} possible links ({rs(metrics['original_cost'])}), "
                 f"this saves {rs(metrics['savings'])} ({metrics['savings_pct']:.2f}%). Prim's and Kruskal's algorithms "
                 f"produce the same minimum cost ({rs(prim.total_cost)}). An MST has no redundant paths, so the failure of any "
                 "installed link disconnects the network until a replacement route is built.")
    else:
        concl = ("The available connections do not link every building, so only a minimum spanning forest could be computed. "
                 "Additional cable routes between the separate parts are required for a fully connected network.")
    story.append(P(concl, body))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(2 * cm, 1 * cm, "Smart Network Cable Installation Cost Optimizer - DAA PBL")
        canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Page {d.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ------------------------------------------------------------------ page
def render() -> None:
    ui.page_header("Reports", "Download the optimized network as a PDF report or as CSV files.")
    graph = ns.load_graph()
    if not ui.need_buildings(graph):
        return
    algorithm = ui.current_algorithm()
    result = ns.run_algorithm(graph, algorithm, record_steps=False)
    metrics = ns.cost_metrics(graph, result)
    st.caption(f"Reports use the selected algorithm: **{algorithm}** - minimum cost {ui.inr(metrics['mst_cost'])}, "
               f"savings {ui.inr(metrics['savings'])} ({metrics['savings_pct']:.2f}%).")

    st.subheader("PDF report")
    st.markdown("Includes buildings, all connections, the selected MST, algorithm used, minimum cost, savings, complexity, "
                "execution time, the network graph and the conclusion.")
    if ui.button("Generate PDF report", key="rep_pdf_gen"):
        try:
            pdf = build_pdf_report(graph, result, metrics)
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            fname = f"network_report_{datetime.now():%Y%m%d_%H%M%S}.pdf"
            (REPORT_DIR / fname).write_bytes(pdf)
            st.session_state["rep_pdf"] = (fname, pdf)
        except Exception as exc:  # surface any ReportLab problem instead of crashing the page
            st.error(f"Could not generate the PDF: {exc}")
    if st.session_state.get("rep_pdf"):
        fname, pdf = st.session_state["rep_pdf"]
        st.success(f"Report ready ({len(pdf) / 1024:.1f} KB) and saved to the reports/ folder as {fname}.")
        ui.download_button("Download PDF report", pdf, fname, "application/pdf", key="rep_pdf_dl")

    st.subheader("CSV exports")
    files = build_csv_exports(graph, result, metrics)
    cols = st.columns(len(files))
    labels = {"buildings.csv": "Buildings", "cable_connections.csv": "Cable connections", "mst_results.csv": "MST results",
              "cost_analysis.csv": "Cost analysis", "cost_by_cable_type.csv": "Cost by cable type"}
    for col, (name, data) in zip(cols, files.items()):
        with col:
            ui.download_button(labels[name], data, name, "text/csv", key=f"rep_csv_{name}")
    ui.download_button("Download all CSV files (ZIP)", zip_csvs(files), "network_csv_exports.zip", "application/zip", key="rep_zip")
    with st.expander("Preview MST results CSV"):
        st.dataframe(pd.read_csv(io.BytesIO(files["mst_results.csv"])), hide_index=True)
