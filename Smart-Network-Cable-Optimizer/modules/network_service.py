"""Business logic between the database, the algorithms and the UI (no Streamlit here)."""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from algorithms import (DSU, Edge, GraphError, MSTResult, connected_components,
                        kruskal_mst, prim_mst)
from database import db

PRIM = "Prim's Algorithm"
KRUSKAL = "Kruskal's Algorithm"
ALGORITHMS = [PRIM, KRUSKAL]

Graph = Dict[str, List[Dict[str, Any]]]


# ------------------------------------------------------------------ graph access
def load_graph(db_path: Optional[str] = None) -> Graph:
    return {"buildings": db.get_buildings(db_path=db_path),
            "connections": db.get_connections(db_path=db_path)}


def algo_inputs(graph: Graph) -> Tuple[List[int], List[Edge]]:
    nodes = [b["id"] for b in graph["buildings"]]
    edges = [Edge(c["source_id"], c["dest_id"], c["total_cost"], c["id"]) for c in graph["connections"]]
    return nodes, edges


def building_names(graph: Graph) -> Dict[int, str]:
    return {b["id"]: b["name"] for b in graph["buildings"]}


def building_codes(graph: Graph) -> Dict[int, str]:
    return {b["id"]: b["code"] for b in graph["buildings"]}


def connection_label(c: Dict[str, Any]) -> str:
    return f"{c['source_code']} - {c['dest_code']}  ({c['source_name']} <-> {c['dest_name']})"


def run_algorithm(graph: Graph, algorithm: str = KRUSKAL, record_steps: bool = True,
                  start: Optional[int] = None) -> MSTResult:
    nodes, edges = algo_inputs(graph)
    if algorithm == PRIM:
        return prim_mst(nodes, edges, start=start, record_steps=record_steps)
    if algorithm == KRUSKAL:
        return kruskal_mst(nodes, edges, record_steps=record_steps)
    raise ValueError(f"Unknown algorithm: {algorithm}")


# ------------------------------------------------------------------ cost analysis
def total_possible_cost(graph: Graph) -> float:
    return float(sum(c["total_cost"] for c in graph["connections"]))


def cost_metrics(graph: Graph, result: MSTResult) -> Dict[str, Any]:
    """Savings = Original total - MST cost; Savings % = Savings / Original x 100."""
    original = total_possible_cost(graph)
    mst_cost = float(result.total_cost)
    savings = original - mst_cost
    pct = (savings / original * 100.0) if original > 0 else 0.0
    return {
        "num_buildings": len(graph["buildings"]), "num_connections": len(graph["connections"]),
        "original_cost": original, "mst_cost": mst_cost, "savings": savings, "savings_pct": pct,
        "selected_edges": result.selected_count, "connected": result.connected,
        "components": result.num_components, "algorithm": result.algorithm,
    }


def mst_connections(graph: Graph, result: MSTResult) -> List[Dict[str, Any]]:
    by_id = {c["id"]: c for c in graph["connections"]}
    return [by_id[e.eid] for e in result.mst_edges if e.eid in by_id]


def cost_by_cable_type(connections: List[Dict[str, Any]]) -> pd.DataFrame:
    if not connections:
        return pd.DataFrame(columns=["Cable Type", "Connections", "Total Cost"])
    df = pd.DataFrame(connections)
    out = df.groupby("cable_type").agg(Connections=("id", "count"), **{"Total Cost": ("total_cost", "sum")})
    return out.reset_index().rename(columns={"cable_type": "Cable Type"}).sort_values("Total Cost", ascending=False)


def buildings_df(graph: Graph) -> pd.DataFrame:
    return pd.DataFrame([{"ID": b["id"], "Code": b["code"], "Name": b["name"],
                          "Description": b["description"], "Connections": b.get("connection_count", 0)}
                         for b in graph["buildings"]],
                        columns=["ID", "Code", "Name", "Description", "Connections"])


def connections_df(connections: List[Dict[str, Any]], selected_ids: Optional[set] = None) -> pd.DataFrame:
    rows = []
    for c in connections:
        row = {"ID": c["id"], "From": f"{c['source_code']} - {c['source_name']}",
               "To": f"{c['dest_code']} - {c['dest_name']}", "Distance (m)": c["distance_m"],
               "Cable Type": c["cable_type"], "Cost / m": c["cost_per_meter"],
               "Installation": c["install_charge"], "Total Cost": c["total_cost"]}
        if selected_ids is not None:
            row["In MST"] = "Yes" if c["id"] in selected_ids else "No"
        rows.append(row)
    cols = ["ID", "From", "To", "Distance (m)", "Cable Type", "Cost / m", "Installation", "Total Cost"]
    if selected_ids is not None:
        cols.append("In MST")
    return pd.DataFrame(rows, columns=cols)


def steps_df(graph: Graph, result: MSTResult, upto: Optional[int] = None) -> pd.DataFrame:
    names = building_names(graph)
    steps = result.steps if upto is None else result.steps[:upto]
    return pd.DataFrame([{
        "Step": s["step"], "Edge": f"{names.get(s['u'], s['u'])} - {names.get(s['v'], s['v'])}",
        "Cost": s["weight"], "Status": s["status"].capitalize(), "Reason": s["reason"],
        "MST Cost": s["mst_cost"], "Selected Edges": s["selected_count"], "Info": s["info"]}
        for s in steps], columns=["Step", "Edge", "Cost", "Status", "Reason", "MST Cost",
                                  "Selected Edges", "Info"])


def result_to_record(graph: Graph, result: MSTResult) -> Dict[str, Any]:
    """Flatten a result into the dict stored by db.save_optimization_result."""
    m = cost_metrics(graph, result)
    return {
        "algorithm": result.algorithm, "total_cost": m["mst_cost"], "original_cost": m["original_cost"],
        "savings": m["savings"], "savings_pct": m["savings_pct"], "num_buildings": m["num_buildings"],
        "num_connections": m["num_connections"], "num_selected_edges": m["selected_edges"],
        "connected": result.connected, "execution_time_ms": result.execution_time_ms,
        "edges_processed": result.edges_processed, "edges_rejected": result.edges_rejected,
        "edges": [{"connection_id": e.eid, "source_id": e.u, "dest_id": e.v, "cost": e.weight}
                  for e in result.mst_edges]}


def networkx_validate(graph: Graph, result: MSTResult) -> Dict[str, bool]:
    """Cross-check structure with NetworkX (validation only - NOT used for optimisation)."""
    import networkx as nx
    nodes, edges = algo_inputs(graph)
    G = nx.Graph()
    G.add_nodes_from(nodes)
    G.add_edges_from((e.u, e.v) for e in edges)
    T = nx.Graph()
    T.add_nodes_from(nodes)
    T.add_edges_from((e.u, e.v) for e in result.mst_edges)
    n = len(nodes)
    return {
        "Graph is connected (NetworkX)": bool(n) and nx.is_connected(G),
        "MST is a tree (NetworkX)": bool(n) and result.connected and nx.is_tree(T),
        "MST has V-1 edges": result.connected and T.number_of_edges() == n - 1,
    }


# ------------------------------------------------------------------ comparing results
def compare_results(old: MSTResult, new: MSTResult) -> Dict[str, Any]:
    def key(e: Edge):
        return (min(e.u, e.v), max(e.u, e.v))
    old_k, new_k = {key(e): e for e in old.mst_edges}, {key(e): e for e in new.mst_edges}
    delta = new.total_cost - old.total_cost
    return {
        "old_cost": old.total_cost, "new_cost": new.total_cost, "delta": delta,
        "delta_pct": (delta / old.total_cost * 100.0) if old.total_cost else 0.0,
        "added": [new_k[k] for k in new_k if k not in old_k],
        "removed": [old_k[k] for k in old_k if k not in new_k],
        "kept": [new_k[k] for k in new_k if k in old_k],
    }


# ------------------------------------------------------------------ what-if changes
def _recompute(c: Dict[str, Any]) -> None:
    c["total_cost"] = round(c["distance_m"] * c["cost_per_meter"] + c["install_charge"], 2)


def apply_changes(graph: Graph, changes: List[Dict[str, Any]], strict: bool = True) -> Graph:
    """Return a modified deep copy of `graph`; the original is never touched.

    Supported ops: scale_cable_cost, scale_install_charge, remove_connection, remove_building,
    add_building (with optional `connections`), add_connection, set_connection_cost.
    strict=False silently skips operations that no longer apply (used for saved scenarios).
    """
    g = copy.deepcopy(graph)
    B, C = g["buildings"], g["connections"]

    def bld(bid):
        return next((b for b in B if b["id"] == bid), None)

    def pair_exists(a, b):
        return any({c["source_id"], c["dest_id"]} == {a, b} for c in C)

    def new_connection(src, dst, dist, ctype, cpm, inst):
        a, b = bld(src), bld(dst)
        if a is None or b is None:
            raise ValueError("Connection endpoint does not exist")
        if src == dst:
            raise ValueError("Self-loop is not allowed")
        if pair_exists(src, dst):
            raise ValueError("Connection already exists between these buildings")
        vals = [float(dist), float(cpm), float(inst)]
        if any((not math.isfinite(v)) or v < 0 for v in vals):
            raise ValueError("Distance, cost per meter and installation charge must be non-negative numbers")
        c = {"id": max([x["id"] for x in C], default=0) + 1, "source_id": src, "dest_id": dst,
             "source_name": a["name"], "source_code": a["code"], "dest_name": b["name"],
             "dest_code": b["code"], "distance_m": vals[0], "cable_type": ctype,
             "cost_per_meter": vals[1], "install_charge": vals[2], "total_cost": 0.0}
        _recompute(c)
        C.append(c)

    for ch in changes:
        op = ch.get("op")
        try:
            if op in ("scale_cable_cost", "scale_install_charge"):
                factor = 1 + float(ch["percent"]) / 100.0
                if factor < 0 or not math.isfinite(factor):
                    raise ValueError("Percentage change would make costs negative")
                field = "cost_per_meter" if op == "scale_cable_cost" else "install_charge"
                ctype = ch.get("cable_type")
                for c in C:
                    if op == "scale_install_charge" or ctype in (None, "", "ALL", c["cable_type"]):
                        c[field] = round(c[field] * factor, 4)
                        _recompute(c)
            elif op == "remove_connection":
                idx = next((i for i, c in enumerate(C) if c["id"] == ch["id"]), None)
                if idx is None:
                    raise ValueError("Connection to remove does not exist")
                C.pop(idx)
            elif op == "remove_building":
                if bld(ch["id"]) is None:
                    raise ValueError("Building to remove does not exist")
                B[:] = [b for b in B if b["id"] != ch["id"]]
                C[:] = [c for c in C if ch["id"] not in (c["source_id"], c["dest_id"])]
            elif op == "add_building":
                name = " ".join(str(ch.get("name", "")).split())
                if len(name) < 2:
                    raise ValueError("Building name must have at least 2 characters")
                if any(b["name"].lower() == name.lower() for b in B):
                    raise ValueError("A building with this name already exists")
                used = {b["code"].upper() for b in B}
                code = next(chr(65 + i) for i in range(26) if chr(65 + i) not in used) \
                    if len(used) < 26 else f"N{len(B) + 1}"
                nb = {"id": max([b["id"] for b in B], default=0) + 1, "code": code, "name": name,
                      "description": ch.get("description", ""), "connection_count": 0}
                B.append(nb)
                for spec in ch.get("connections", []):
                    new_connection(spec["connect_to"], nb["id"], spec["distance_m"], spec["cable_type"],
                                   spec["cost_per_meter"], spec.get("install_charge", 0))
            elif op == "add_connection":
                new_connection(ch["source_id"], ch["dest_id"], ch["distance_m"], ch["cable_type"],
                               ch["cost_per_meter"], ch.get("install_charge", 0))
            elif op == "set_connection_cost":
                c = next((c for c in C if c["id"] == ch["id"]), None)
                if c is None:
                    raise ValueError("Connection does not exist")
                for key in ("distance_m", "cost_per_meter", "install_charge"):
                    if ch.get(key) is not None:
                        v = float(ch[key])
                        if not math.isfinite(v) or v < 0:
                            raise ValueError("Costs cannot be negative")
                        c[key] = v
                _recompute(c)
            else:
                raise ValueError(f"Unknown change operation: {op!r}")
        except (KeyError, TypeError) as exc:
            if strict:
                raise ValueError(f"Invalid change {ch!r}: {exc}") from None
        except ValueError:
            if strict:
                raise
    for b in B:
        b["connection_count"] = sum(1 for c in C if b["id"] in (c["source_id"], c["dest_id"]))
    return g


def evaluate_scenario(graph: Graph, changes: List[Dict[str, Any]], algorithm: str = KRUSKAL,
                      strict: bool = False) -> Dict[str, Any]:
    g = apply_changes(graph, changes, strict=strict)
    res = run_algorithm(g, algorithm)
    return {"graph": g, "result": res, "metrics": cost_metrics(g, res)}


def preset_scenarios(graph: Graph, algorithm: str = KRUSKAL) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """The five standard what-if scenarios shown on the Scenario Analysis page."""
    presets: List[Tuple[str, List[Dict[str, Any]]]] = [
        ("Normal installation costs", []),
        ("Fiber-optic cable cost +30%", [{"op": "scale_cable_cost", "cable_type": "Fiber Optic", "percent": 30}]),
        ("Installation charges -25%", [{"op": "scale_install_charge", "percent": -25}]),
    ]
    base = run_algorithm(graph, algorithm, record_steps=False)
    chosen = mst_connections(graph, base)
    if chosen:
        worst = max(chosen, key=lambda c: c["total_cost"])
        presets.append((f"Remove costliest MST link ({worst['source_code']}-{worst['dest_code']})",
                        [{"op": "remove_connection", "id": worst["id"]}]))
    if len(graph["buildings"]) >= 2:
        first, second = graph["buildings"][0], graph["buildings"][1]
        name = "Sports Complex"
        taken = {b["name"].lower() for b in graph["buildings"]}
        while name.lower() in taken:
            name += " 2"
        presets.append((f"Add new building ({name})", [{
            "op": "add_building", "name": name, "connections": [
                {"connect_to": first["id"], "distance_m": 120, "cable_type": "Ethernet",
                 "cost_per_meter": 12, "install_charge": 800},
                {"connect_to": second["id"], "distance_m": 180, "cable_type": "Ethernet",
                 "cost_per_meter": 12, "install_charge": 800}]}]))
    return presets


# ------------------------------------------------------------------ failure simulation
def simulate_failure(graph: Graph, failed_id: int, algorithm: str = KRUSKAL) -> Dict[str, Any]:
    """Fail one installed MST connection and analyse the consequences."""
    base = run_algorithm(graph, algorithm, record_steps=False)
    installed = {e.eid: e for e in base.mst_edges}
    if failed_id not in installed:
        raise ValueError("The selected connection is not part of the installed MST network")
    failed_edge = installed[failed_id]
    by_id = {c["id"]: c for c in graph["connections"]}
    nodes = [b["id"] for b in graph["buildings"]]

    remaining = [e for e in base.mst_edges if e.eid != failed_id]
    components = connected_components(nodes, remaining)
    dsu = DSU(nodes)
    for e in remaining:
        dsu.union(e.u, e.v)
    root_u, root_v = dsu.find(failed_edge.u), dsu.find(failed_edge.v)
    part_u = sorted(x for x in nodes if dsu.find(x) == root_u)
    part_v = sorted(x for x in nodes if dsu.find(x) == root_v)
    # The larger fragment keeps the bulk of the network; the other one is cut off.
    main, isolated = (part_u, part_v) if len(part_u) >= len(part_v) else (part_v, part_u)

    candidates = [c for c in graph["connections"]
                  if c["id"] not in installed and {dsu.find(c["source_id"]), dsu.find(c["dest_id"])} == {root_u, root_v}]
    candidates.sort(key=lambda c: (c["total_cost"], c["id"]))
    replacement = candidates[0] if candidates else None

    new_graph = apply_changes(graph, [{"op": "remove_connection", "id": failed_id}])
    new_result = run_algorithm(new_graph, algorithm, record_steps=False)
    failed_conn = by_id[failed_id]
    expected = None
    consistent = None
    if replacement is not None:
        expected = base.total_cost - failed_conn["total_cost"] + replacement["total_cost"]
        consistent = math.isclose(expected, new_result.total_cost, abs_tol=1e-6)
    return {
        "base": base, "failed": failed_conn, "components": components, "main": main,
        "isolated": isolated, "candidates": candidates, "replacement": replacement,
        "new_graph": new_graph, "new_result": new_result, "expected_cost": expected,
        "consistent": consistent, "restorable": replacement is not None,
        "extra_cost": (new_result.total_cost - base.total_cost) if replacement is not None else None,
    }


def criticality_table(graph: Graph, algorithm: str = KRUSKAL) -> pd.DataFrame:
    """For every installed link: what happens if it fails (replacement + extra cost)."""
    base = run_algorithm(graph, algorithm, record_steps=False)
    rows = []
    for e in base.mst_edges:
        sim = simulate_failure(graph, e.eid, algorithm)
        f, r = sim["failed"], sim["replacement"]
        rows.append({
            "Failed Link": f"{f['source_code']} - {f['dest_code']}", "Cost": f["total_cost"],
            "Buildings Cut Off": len(sim["isolated"]),
            "Cheapest Replacement": f"{r['source_code']} - {r['dest_code']}" if r else "None (bridge)",
            "Replacement Cost": r["total_cost"] if r else None,
            "Extra Cost": sim["extra_cost"], "Critical": "Yes" if r is None else "No"})
    return pd.DataFrame(rows, columns=["Failed Link", "Cost", "Buildings Cut Off", "Cheapest Replacement",
                                       "Replacement Cost", "Extra Cost", "Critical"])
