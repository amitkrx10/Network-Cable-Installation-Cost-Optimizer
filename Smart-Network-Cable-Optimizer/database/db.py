"""SQLite persistence layer: schema, validation and CRUD for the optimizer."""
from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from itertools import count
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "network.db"
SAMPLE_CSV = BASE_DIR / "data" / "sample_network.csv"

CABLE_TYPES = ["Fiber Optic", "Ethernet", "Cat6", "Cat6A", "Coaxial"]

SAMPLE_BUILDINGS = [
    ("A", "Administration Block", "Main administrative office"),
    ("B", "Library", "Central library and reading halls"),
    ("C", "Computer Science Block", "CS department and server room"),
    ("D", "Mechanical Department", "Mechanical workshops and classrooms"),
    ("E", "Hostel", "Student residential block"),
    ("F", "Laboratory", "Central research laboratory"),
]
# (source code, dest code, distance_m, cable_type, cost_per_meter, installation_charge)
SAMPLE_CONNECTIONS = [
    ("A", "B", 200, "Ethernet", 15, 1000), ("A", "C", 100, "Ethernet", 10, 1000),
    ("B", "C", 50, "Ethernet", 10, 500), ("B", "D", 150, "Fiber Optic", 25, 1250),
    ("C", "D", 250, "Fiber Optic", 28, 1000), ("C", "E", 300, "Fiber Optic", 30, 1000),
    ("D", "E", 100, "Ethernet", 15, 500), ("D", "F", 200, "Fiber Optic", 25, 1000),
    ("E", "F", 150, "Ethernet", 15, 750),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cable_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    dest_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    distance_m REAL NOT NULL CHECK (distance_m >= 0),
    cable_type TEXT NOT NULL,
    cost_per_meter REAL NOT NULL CHECK (cost_per_meter >= 0),
    install_charge REAL NOT NULL CHECK (install_charge >= 0),
    total_cost REAL NOT NULL CHECK (total_cost >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (source_id <> dest_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_connection_pair
    ON cable_connections (MIN(source_id, dest_id), MAX(source_id, dest_id));
CREATE TABLE IF NOT EXISTS optimization_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    algorithm TEXT NOT NULL,
    total_cost REAL NOT NULL,
    original_cost REAL NOT NULL,
    savings REAL NOT NULL,
    savings_pct REAL NOT NULL,
    num_buildings INTEGER NOT NULL,
    num_selected_edges INTEGER NOT NULL,
    connected INTEGER NOT NULL,
    execution_time_ms REAL NOT NULL,
    edges_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS algorithm_execution_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id INTEGER REFERENCES optimization_results(id) ON DELETE SET NULL,
    algorithm TEXT NOT NULL,
    num_nodes INTEGER NOT NULL,
    num_edges INTEGER NOT NULL,
    execution_time_ms REAL NOT NULL,
    edges_processed INTEGER NOT NULL,
    edges_rejected INTEGER NOT NULL,
    mst_cost REAL NOT NULL,
    connected INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    changes_json TEXT NOT NULL,
    base_cost REAL NOT NULL,
    optimized_cost REAL NOT NULL,
    connected INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class ValidationError(ValueError):
    """User-facing validation problem (bad input, duplicate, not found...)."""


@contextmanager
def connect(db_path: Optional[str] = None):
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


# ------------------------------------------------------------------ validation
def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{label} must be a number")
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if not math.isfinite(f):
        raise ValidationError(f"{label} must be a finite number")
    if f < 0:
        raise ValidationError(f"{label} cannot be negative")
    return f


def _int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} is invalid") from None


def _clean_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Building name cannot be empty")
    name = " ".join(name.split())
    if len(name) < 2 or len(name) > 60:
        raise ValidationError("Building name must be 2-60 characters long")
    return name


def _next_code(conn: sqlite3.Connection) -> str:
    used = {r["code"].upper() for r in conn.execute("SELECT code FROM buildings")}
    for n in count(1):
        s, x = "", n
        while x:
            x, rem = divmod(x - 1, 26)
            s = chr(65 + rem) + s
        if s not in used:
            return s
    return "?"  # pragma: no cover


def _clean_code(code: Any) -> str:
    code = str(code).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,10}", code):
        raise ValidationError("Building code must be 1-10 letters, digits, '-' or '_'")
    return code.upper()


def _integrity_message(err: sqlite3.IntegrityError) -> str:
    msg = str(err)
    if "buildings.name" in msg:
        return "A building with this name already exists"
    if "buildings.code" in msg:
        return "A building with this code already exists"
    if "ux_connection_pair" in msg or "cable_connections" in msg and "UNIQUE" in msg:
        return "A connection between these two buildings already exists"
    return f"Database constraint failed: {msg}"


# ------------------------------------------------------------------ buildings
def add_building(name: str, code: Optional[str] = None, description: str = "",
                 db_path: Optional[str] = None) -> int:
    name = _clean_name(name)
    description = (description or "").strip()[:200]
    try:
        with connect(db_path) as conn:
            code = _clean_code(code) if code not in (None, "") else _next_code(conn)
            cur = conn.execute("INSERT INTO buildings (code, name, description) VALUES (?,?,?)",
                               (code, name, description))
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        raise ValidationError(_integrity_message(e)) from None


def get_buildings(search: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = ("SELECT b.*, (SELECT COUNT(*) FROM cable_connections c "
           "WHERE c.source_id = b.id OR c.dest_id = b.id) AS connection_count FROM buildings b")
    params: tuple = ()
    if search and search.strip():
        like = f"%{search.strip()}%"
        sql += " WHERE b.name LIKE ? OR b.code LIKE ? OR b.description LIKE ? OR CAST(b.id AS TEXT) = ?"
        params = (like, like, like, search.strip())
    sql += " ORDER BY b.id"
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def get_building(building_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM buildings WHERE id = ?", (building_id,)).fetchone()
        return dict(row) if row else None


def update_building(building_id: int, name: str, code: str, description: str = "",
                    db_path: Optional[str] = None) -> None:
    name = _clean_name(name)
    code = _clean_code(code)
    try:
        with connect(db_path) as conn:
            cur = conn.execute("UPDATE buildings SET name=?, code=?, description=? WHERE id=?",
                               (name, code, (description or "").strip()[:200], building_id))
            if cur.rowcount == 0:
                raise ValidationError("Building not found")
    except sqlite3.IntegrityError as e:
        raise ValidationError(_integrity_message(e)) from None


def delete_building(building_id: int, db_path: Optional[str] = None) -> int:
    """Delete a building; its connections are removed by ON DELETE CASCADE.

    Returns the number of connections that were removed with it.
    """
    with connect(db_path) as conn:
        if not conn.execute("SELECT 1 FROM buildings WHERE id=?", (building_id,)).fetchone():
            raise ValidationError("Building not found")
        n = conn.execute("SELECT COUNT(*) FROM cable_connections WHERE source_id=? OR dest_id=?",
                         (building_id, building_id)).fetchone()[0]
        conn.execute("DELETE FROM buildings WHERE id=?", (building_id,))
        return n


# ------------------------------------------------------------------ connections
_CONN_SELECT = """
SELECT c.*, s.name AS source_name, s.code AS source_code,
       d.name AS dest_name, d.code AS dest_code
FROM cable_connections c
JOIN buildings s ON s.id = c.source_id
JOIN buildings d ON d.id = c.dest_id
"""


def _validate_connection(conn, source_id, dest_id, distance_m, cable_type, cost_per_meter,
                         install_charge, exclude_id=None):
    source_id, dest_id = _int(source_id, "Source building"), _int(dest_id, "Destination building")
    if source_id == dest_id:
        raise ValidationError("A building cannot be connected to itself (self-loop)")
    for bid, label in ((source_id, "Source"), (dest_id, "Destination")):
        if not conn.execute("SELECT 1 FROM buildings WHERE id=?", (bid,)).fetchone():
            raise ValidationError(f"{label} building does not exist")
    distance_m = _number(distance_m, "Cable distance")
    cost_per_meter = _number(cost_per_meter, "Cost per meter")
    install_charge = _number(install_charge, "Installation charge")
    cable_type = " ".join(str(cable_type or "").split())
    if not cable_type or len(cable_type) > 40:
        raise ValidationError("Cable type is required (max 40 characters)")
    dup = conn.execute(
        "SELECT id FROM cable_connections WHERE MIN(source_id,dest_id)=? AND MAX(source_id,dest_id)=?",
        (min(source_id, dest_id), max(source_id, dest_id))).fetchone()
    if dup and dup["id"] != exclude_id:
        raise ValidationError("A connection between these two buildings already exists")
    total = round(distance_m * cost_per_meter + install_charge, 2)
    return source_id, dest_id, distance_m, cable_type, cost_per_meter, install_charge, total


def calculate_total_cost(distance_m: float, cost_per_meter: float, install_charge: float) -> float:
    """Total Cost = (Distance x Cost per meter) + Installation charges."""
    return round(_number(distance_m, "Cable distance") * _number(cost_per_meter, "Cost per meter")
                 + _number(install_charge, "Installation charge"), 2)


def add_connection(source_id: int, dest_id: int, distance_m: float, cable_type: str,
                   cost_per_meter: float, install_charge: float = 0.0,
                   db_path: Optional[str] = None) -> int:
    try:
        with connect(db_path) as conn:
            vals = _validate_connection(conn, source_id, dest_id, distance_m, cable_type,
                                        cost_per_meter, install_charge)
            cur = conn.execute(
                "INSERT INTO cable_connections (source_id, dest_id, distance_m, cable_type, "
                "cost_per_meter, install_charge, total_cost) VALUES (?,?,?,?,?,?,?)", vals)
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        raise ValidationError(_integrity_message(e)) from None


def get_connections(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(_CONN_SELECT + " ORDER BY c.id")]


def get_connection(connection_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with connect(db_path) as conn:
        row = conn.execute(_CONN_SELECT + " WHERE c.id = ?", (connection_id,)).fetchone()
        return dict(row) if row else None


def update_connection(connection_id: int, source_id: int, dest_id: int, distance_m: float,
                      cable_type: str, cost_per_meter: float, install_charge: float = 0.0,
                      db_path: Optional[str] = None) -> None:
    try:
        with connect(db_path) as conn:
            if not conn.execute("SELECT 1 FROM cable_connections WHERE id=?", (connection_id,)).fetchone():
                raise ValidationError("Connection not found")
            vals = _validate_connection(conn, source_id, dest_id, distance_m, cable_type,
                                        cost_per_meter, install_charge, exclude_id=connection_id)
            conn.execute(
                "UPDATE cable_connections SET source_id=?, dest_id=?, distance_m=?, cable_type=?, "
                "cost_per_meter=?, install_charge=?, total_cost=? WHERE id=?", vals + (connection_id,))
    except sqlite3.IntegrityError as e:
        raise ValidationError(_integrity_message(e)) from None


def delete_connection(connection_id: int, db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM cable_connections WHERE id=?", (connection_id,))
        if cur.rowcount == 0:
            raise ValidationError("Connection not found")


# ------------------------------------------------------------------ results / history
def save_optimization_result(result: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Persist an optimisation run (+ a history row). `result` is a plain dict."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO optimization_results (algorithm, total_cost, original_cost, savings, "
            "savings_pct, num_buildings, num_selected_edges, connected, execution_time_ms, edges_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (result["algorithm"], result["total_cost"], result["original_cost"], result["savings"],
             result["savings_pct"], result["num_buildings"], result["num_selected_edges"],
             int(result["connected"]), result["execution_time_ms"], json.dumps(result["edges"])))
        rid = cur.lastrowid
        conn.execute(
            "INSERT INTO algorithm_execution_history (result_id, algorithm, num_nodes, num_edges, "
            "execution_time_ms, edges_processed, edges_rejected, mst_cost, connected) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (rid, result["algorithm"], result["num_buildings"], result["num_connections"],
             result["execution_time_ms"], result["edges_processed"], result["edges_rejected"],
             result["total_cost"], int(result["connected"])))
        return rid


def get_optimization_results(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM optimization_results ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = dict(r)
            d["edges"] = json.loads(d.pop("edges_json"))
            out.append(d)
        return out


def get_execution_history(limit: int = 100, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM algorithm_execution_history ORDER BY id DESC LIMIT ?", (limit,))]


def clear_history(db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM algorithm_execution_history")
        conn.execute("DELETE FROM optimization_results")


# ------------------------------------------------------------------ scenarios
def save_scenario(name: str, description: str, changes: List[Dict[str, Any]], base_cost: float,
                  optimized_cost: float, connected: bool = True, db_path: Optional[str] = None) -> int:
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Scenario name cannot be empty")
    name = " ".join(name.split())[:80]
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO scenarios (name, description, changes_json, base_cost, optimized_cost, connected) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET description=excluded.description, "
            "changes_json=excluded.changes_json, base_cost=excluded.base_cost, "
            "optimized_cost=excluded.optimized_cost, connected=excluded.connected",
            (name, (description or "").strip()[:300], json.dumps(changes), base_cost,
             optimized_cost, int(connected)))
        return conn.execute("SELECT id FROM scenarios WHERE name=?", (name,)).fetchone()["id"]


def get_scenarios(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect(db_path) as conn:
        out = []
        for r in conn.execute("SELECT * FROM scenarios ORDER BY id"):
            d = dict(r)
            d["changes"] = json.loads(d.pop("changes_json"))
            out.append(d)
        return out


def delete_scenario(scenario_id: int, db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM scenarios WHERE id=?", (scenario_id,))
        if cur.rowcount == 0:
            raise ValidationError("Scenario not found")


# ------------------------------------------------------------------ sample data
def _read_sample_rows() -> List[tuple]:
    if SAMPLE_CSV.exists():
        try:
            with open(SAMPLE_CSV, newline="", encoding="utf-8") as fh:
                return [(r["source"].strip(), r["destination"].strip(), float(r["distance_m"]),
                         r["cable_type"].strip(), float(r["cost_per_meter"]),
                         float(r["installation_charge"])) for r in csv.DictReader(fh)]
        except (KeyError, ValueError, OSError):
            pass
    return list(SAMPLE_CONNECTIONS)


def clear_all_data(db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        for table in ("algorithm_execution_history", "optimization_results", "scenarios",
                      "cable_connections", "buildings"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")


def seed_sample_data(db_path: Optional[str] = None, reset: bool = False) -> Dict[str, int]:
    """Load the sample campus network. With reset=True all existing data is replaced."""
    init_db(db_path)
    if reset:
        clear_all_data(db_path)
    elif get_buildings(db_path=db_path):
        raise ValidationError("Database already contains buildings; use reset=True to replace them")
    ids = {}
    for code, name, desc in SAMPLE_BUILDINGS:
        ids[code] = add_building(name, code, desc, db_path)
    n = 0
    for s, d, dist, ctype, cpm, inst in _read_sample_rows():
        add_connection(ids[s], ids[d], dist, ctype, cpm, inst, db_path)
        n += 1
    with connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('seeded', ?)",
                     (datetime.now().isoformat(timespec="seconds"),))
    return {"buildings": len(ids), "connections": n}


def ensure_ready(db_path: Optional[str] = None) -> None:
    """Create the schema and load sample data on the very first launch only."""
    init_db(db_path)
    with connect(db_path) as conn:
        seeded = conn.execute("SELECT 1 FROM app_meta WHERE key='seeded'").fetchone()
        empty = conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0] == 0
    if not seeded and empty:
        seed_sample_data(db_path)
    elif not seeded:
        with connect(db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('seeded', 'existing')")
