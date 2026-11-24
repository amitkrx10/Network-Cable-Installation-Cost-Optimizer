import pytest

from database import db


def test_sample_data_loaded(sample_db):
    b, c = db.get_buildings(db_path=sample_db), db.get_connections(db_path=sample_db)
    assert [x["code"] for x in b] == list("ABCDEF") and len(c) == 9
    assert sum(x["total_cost"] for x in c) == 41000


def test_sample_costs_match_formula(sample_db):
    for c in db.get_connections(db_path=sample_db):
        assert c["total_cost"] == c["distance_m"] * c["cost_per_meter"] + c["install_charge"]


def test_building_crud(db_path):
    bid = db.add_building("Sports Complex", description="Gym", db_path=db_path)
    assert db.get_building(bid, db_path)["code"] == "A"  # auto code
    db.update_building(bid, "Sports Centre", "SC", "Updated", db_path)
    assert db.get_building(bid, db_path)["name"] == "Sports Centre"
    assert [b["id"] for b in db.get_buildings(search="centre", db_path=db_path)] == [bid]
    assert db.get_buildings(search="zzz", db_path=db_path) == []
    assert db.delete_building(bid, db_path) == 0
    assert db.get_building(bid, db_path) is None


def test_building_validation(db_path):
    db.add_building("Library", db_path=db_path)
    for bad in ("", "   ", "A", None, "x" * 61):
        with pytest.raises(db.ValidationError):
            db.add_building(bad, db_path=db_path)
    with pytest.raises(db.ValidationError):
        db.add_building("library", db_path=db_path)  # duplicate, case-insensitive
    with pytest.raises(db.ValidationError):
        db.add_building("Other", code="a", db_path=db_path)  # duplicate code
    with pytest.raises(db.ValidationError):
        db.add_building("Bad code", code="no spaces!", db_path=db_path)
    with pytest.raises(db.ValidationError):
        db.update_building(999, "Ghost", "G", db_path=db_path)
    with pytest.raises(db.ValidationError):
        db.delete_building(999, db_path)


def test_connection_crud_and_cost_formula(sample_db):
    before = len(db.get_connections(db_path=sample_db))
    cid = db.add_connection(1, 6, 100, "Cat6", 12, 300, db_path=sample_db)
    c = db.get_connection(cid, sample_db)
    assert c["total_cost"] == 100 * 12 + 300 and c["source_name"] == "Administration Block"
    db.update_connection(cid, 1, 6, 200, "Fiber Optic", 20, 100, db_path=sample_db)
    assert db.get_connection(cid, sample_db)["total_cost"] == 4100
    db.delete_connection(cid, sample_db)
    assert len(db.get_connections(db_path=sample_db)) == before
    with pytest.raises(db.ValidationError):
        db.delete_connection(cid, sample_db)


def test_connection_validation(sample_db):
    with pytest.raises(db.ValidationError, match="itself"):
        db.add_connection(1, 1, 10, "Ethernet", 1, 0, db_path=sample_db)  # self-loop
    with pytest.raises(db.ValidationError, match="already exists"):
        db.add_connection(1, 2, 10, "Ethernet", 1, 0, db_path=sample_db)  # duplicate
    with pytest.raises(db.ValidationError, match="already exists"):
        db.add_connection(2, 1, 10, "Ethernet", 1, 0, db_path=sample_db)  # duplicate reversed
    for args in [(-1, 1, 0), (10, -1, 0), (10, 1, -5), ("x", 1, 0), (float("nan"), 1, 0), (float("inf"), 1, 0)]:
        with pytest.raises(db.ValidationError):
            db.add_connection(1, 6, args[0], "Ethernet", args[1], args[2], db_path=sample_db)
    with pytest.raises(db.ValidationError):
        db.add_connection(1, 99, 10, "Ethernet", 1, 0, db_path=sample_db)  # unknown building
    with pytest.raises(db.ValidationError):
        db.add_connection(1, 6, 10, "  ", 1, 0, db_path=sample_db)  # empty cable type


def test_zero_cost_connection_allowed(sample_db):
    cid = db.add_connection(1, 6, 0, "Ethernet", 0, 0, db_path=sample_db)
    assert db.get_connection(cid, sample_db)["total_cost"] == 0


def test_update_duplicate_rejected(sample_db):
    cid = [c for c in db.get_connections(db_path=sample_db) if c["source_code"] == "A" and c["dest_code"] == "C"][0]["id"]
    with pytest.raises(db.ValidationError):
        db.update_connection(cid, 1, 2, 10, "Ethernet", 1, 0, db_path=sample_db)  # A-B exists


def test_delete_building_cascades_connections(sample_db):
    removed = db.delete_building(3, sample_db)  # C touches A, B, D, E
    assert removed == 4
    assert all(3 not in (c["source_id"], c["dest_id"]) for c in db.get_connections(db_path=sample_db))


def test_persistence_across_connections(sample_db):
    db.add_building("Cafeteria", db_path=sample_db)
    assert "Cafeteria" in [b["name"] for b in db.get_buildings(db_path=sample_db)]  # fresh connection each call


def test_ensure_ready_seeds_once(tmp_path):
    p = str(tmp_path / "x.db")
    db.ensure_ready(p)
    assert len(db.get_buildings(db_path=p)) == 6
    db.clear_all_data(p)
    db.ensure_ready(p)  # must NOT re-seed after the user emptied the data
    assert db.get_buildings(db_path=p) == []


def test_seed_refuses_to_overwrite_without_reset(sample_db):
    with pytest.raises(db.ValidationError):
        db.seed_sample_data(sample_db)
    assert db.seed_sample_data(sample_db, reset=True) == {"buildings": 6, "connections": 9}


def test_optimization_result_and_history(sample_db):
    rec = {"algorithm": "Kruskal's Algorithm", "total_cost": 13000, "original_cost": 41000, "savings": 28000,
           "savings_pct": 68.29, "num_buildings": 6, "num_connections": 9, "num_selected_edges": 5,
           "connected": True, "execution_time_ms": 0.05, "edges_processed": 6, "edges_rejected": 1,
           "edges": [{"connection_id": 3, "cost": 1000}]}
    rid = db.save_optimization_result(rec, sample_db)
    assert db.get_optimization_results(db_path=sample_db)[0]["id"] == rid
    hist = db.get_execution_history(db_path=sample_db)
    assert hist[0]["result_id"] == rid and hist[0]["mst_cost"] == 13000
    db.clear_history(sample_db)
    assert db.get_execution_history(db_path=sample_db) == []


def test_scenarios_crud(sample_db):
    sid = db.save_scenario("Fiber +30%", "x", [{"op": "scale_cable_cost", "percent": 30}], 13000, 14125, True, sample_db)
    assert db.get_scenarios(sample_db)[0]["changes"][0]["percent"] == 30
    assert db.save_scenario("fiber +30%", "y", [], 13000, 13000, True, sample_db) == sid  # upsert, case-insensitive
    with pytest.raises(db.ValidationError):
        db.save_scenario("  ", "", [], 0, 0, db_path=sample_db)
    db.delete_scenario(sid, sample_db)
    assert db.get_scenarios(sample_db) == []
    with pytest.raises(db.ValidationError):
        db.delete_scenario(sid, sample_db)
