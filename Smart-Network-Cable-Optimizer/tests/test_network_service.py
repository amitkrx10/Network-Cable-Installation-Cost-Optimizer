import pytest

from algorithms import has_cycle, is_connected
from database import db
from modules import benchmarking as bm
from modules import network_service as ns


@pytest.fixture
def graph(sample_db):
    return ns.load_graph(sample_db)


def cid(graph, a, b):
    return next(c["id"] for c in graph["connections"] if {c["source_code"], c["dest_code"]} == {a, b})


@pytest.mark.parametrize("algo", ns.ALGORITHMS)
def test_sample_network_end_to_end(graph, algo):
    r = ns.run_algorithm(graph, algo)
    m = ns.cost_metrics(graph, r)
    assert m["mst_cost"] == 13000 and m["original_cost"] == 41000 and m["savings"] == 28000
    assert round(m["savings_pct"], 2) == 68.29 and m["selected_edges"] == 5 and m["connected"]
    sel = {(c["source_code"] + c["dest_code"]) for c in ns.mst_connections(graph, r)}
    assert sel == {"BC", "AC", "DE", "EF", "BD"}


def test_networkx_validation_flags(graph):
    checks = ns.networkx_validate(graph, ns.run_algorithm(graph))
    assert all(checks.values())


# ---------------------------------------------------------------- failure simulation
@pytest.mark.parametrize("algo", ns.ALGORITHMS)
def test_failure_of_bd_isolates_two_sides_and_finds_replacement(graph, algo):
    sim = ns.simulate_failure(graph, cid(graph, "B", "D"), algo)
    assert sorted(len(c) for c in sim["components"]) == [3, 3]
    assert {graph["buildings"][i - 1]["code"] for i in sim["isolated"]} <= {"A", "B", "C", "D", "E", "F"}
    r = sim["replacement"]
    assert {r["source_code"], r["dest_code"]} == {"C", "D"} and r["total_cost"] == 8000
    assert sim["new_result"].total_cost == 16000 and sim["extra_cost"] == 3000
    assert sim["consistent"] and sim["new_result"].connected


def test_failure_of_leaf_link_isolates_one_building(graph):
    sim = ns.simulate_failure(graph, cid(graph, "E", "F"))
    assert len(sim["isolated"]) == 1 and sim["replacement"]["total_cost"] == 6000  # D-F
    assert sim["new_result"].total_cost == 13000 - 3000 + 6000


def test_failure_without_alternative_leaves_network_split(sample_db):
    for a, b in ((1, 2), (4, 6), (3, 4), (3, 5)):
        for c in db.get_connections(db_path=sample_db):
            if {c["source_id"], c["dest_id"]} == {a, b}:
                db.delete_connection(c["id"], sample_db)
    g = ns.load_graph(sample_db)
    sim = ns.simulate_failure(g, cid(g, "E", "F"))
    assert sim["replacement"] is None and not sim["restorable"] and not sim["new_result"].connected


def test_failure_of_non_installed_edge_rejected(graph):
    with pytest.raises(ValueError):
        ns.simulate_failure(graph, cid(graph, "A", "B"))  # A-B is not in the MST


def test_mst_has_no_redundancy_every_edge_failure_disconnects(graph):
    base = ns.run_algorithm(graph)
    nodes, _ = ns.algo_inputs(graph)
    for e in base.mst_edges:
        remaining = [x for x in base.mst_edges if x.eid != e.eid]
        assert not is_connected(nodes, remaining)


def test_criticality_table(graph):
    t = ns.criticality_table(graph)
    assert len(t) == 5 and (t["Critical"] == "No").all()


# ---------------------------------------------------------------- dynamic updates
def test_add_connection_cheaper_changes_mst(graph):
    a, f = graph["buildings"][0]["id"], graph["buildings"][5]["id"]
    ch = [{"op": "add_connection", "source_id": a, "dest_id": f, "distance_m": 10, "cable_type": "Cat6",
           "cost_per_meter": 10, "install_charge": 100}]  # cost 200
    old = ns.run_algorithm(graph)
    g2 = ns.apply_changes(graph, ch)
    new = ns.run_algorithm(g2)
    cmp = ns.compare_results(old, new)
    assert len(graph["connections"]) == 9 and len(g2["connections"]) == 10  # original untouched
    assert new.total_cost < old.total_cost and len(cmp["added"]) >= 1 and len(cmp["removed"]) >= 1


def test_add_building_with_connection(graph):
    ch = [{"op": "add_building", "name": "Gym", "connections": [
        {"connect_to": 1, "distance_m": 100, "cable_type": "Ethernet", "cost_per_meter": 10, "install_charge": 500}]}]
    g2 = ns.apply_changes(graph, ch)
    r = ns.run_algorithm(g2)
    assert len(g2["buildings"]) == 7 and r.connected and r.selected_count == 6 and r.total_cost == 13000 + 1500


def test_remove_connection_and_disconnect(graph):
    g2 = ns.apply_changes(graph, [{"op": "remove_building", "id": 6}])
    assert len(g2["buildings"]) == 5 and ns.run_algorithm(g2).total_cost == 10000
    g3 = ns.apply_changes(graph, [{"op": "remove_connection", "id": cid(graph, "D", "F")},
                                  {"op": "remove_connection", "id": cid(graph, "E", "F")}])
    assert not ns.run_algorithm(g3).connected


def test_change_costs(graph):
    bd = cid(graph, "B", "D")
    g2 = ns.apply_changes(graph, [{"op": "set_connection_cost", "id": bd, "cost_per_meter": 100}])
    assert next(c for c in g2["connections"] if c["id"] == bd)["total_cost"] == 150 * 100 + 1250
    g3 = ns.apply_changes(graph, [{"op": "scale_cable_cost", "cable_type": "Fiber Optic", "percent": 30}])
    assert ns.run_algorithm(g3).total_cost == 14125
    g4 = ns.apply_changes(graph, [{"op": "scale_install_charge", "percent": -25}])
    assert ns.run_algorithm(g4).total_cost == 12000


def test_apply_changes_validation(graph):
    bad = [
        {"op": "add_connection", "source_id": 1, "dest_id": 1, "distance_m": 1, "cable_type": "x", "cost_per_meter": 1},
        {"op": "add_connection", "source_id": 1, "dest_id": 2, "distance_m": 1, "cable_type": "x", "cost_per_meter": 1},
        {"op": "add_connection", "source_id": 1, "dest_id": 6, "distance_m": -1, "cable_type": "x", "cost_per_meter": 1},
        {"op": "add_connection", "source_id": 1, "dest_id": 99, "distance_m": 1, "cable_type": "x", "cost_per_meter": 1},
        {"op": "set_connection_cost", "id": 1, "cost_per_meter": -3},
        {"op": "remove_connection", "id": 999}, {"op": "add_building", "name": "Library"},
        {"op": "scale_cable_cost", "percent": -150}, {"op": "nope"},
    ]
    for ch in bad:
        with pytest.raises(ValueError):
            ns.apply_changes(graph, [ch])
        ns.apply_changes(graph, [ch], strict=False)  # tolerated silently for saved scenarios


def test_preset_scenarios(graph):
    results = {n: ns.evaluate_scenario(graph, ch)["metrics"]["mst_cost"] for n, ch in ns.preset_scenarios(graph)}
    assert len(results) == 5
    vals = list(results.values())
    assert vals[0] == 13000 and vals[1] == 14125 and vals[2] == 12000 and vals[3] == 16000


# ---------------------------------------------------------------- benchmarking
def test_random_graph_is_connected_with_requested_size():
    for n, m in [(2, None), (10, 30), (50, 49), (30, 435)]:
        nodes, edges = bm.generate_random_graph(n, m, seed=3)
        assert is_connected(nodes, edges)
        assert len({(min(u, v), max(u, v)) for u, v, *_ in edges}) == len(edges)
        if m:
            assert len(edges) == min(m, n * (n - 1) // 2)


def test_benchmark_runs_and_costs_match():
    df = bm.benchmark_sizes([10, 50], runs=2)
    assert len(df) == 4 and df["Costs Match"].all() and (df["Avg Time (ms)"] > 0).all()
    assert bm.benchmark_edge_counts(30, [60, 200], runs=2)["Costs Match"].all()
