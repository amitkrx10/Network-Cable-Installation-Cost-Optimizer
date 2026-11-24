import itertools
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Sample campus network: A=0.. mapped to building ids 1..6
NODES = [1, 2, 3, 4, 5, 6]
SAMPLE_EDGES = [(1, 2, 4000), (1, 3, 2000), (2, 3, 1000), (2, 4, 5000), (3, 4, 8000),
                (3, 5, 10000), (4, 5, 2000), (4, 6, 6000), (5, 6, 3000)]


def brute_force_mst_cost(nodes, edges):
    """Exhaustive minimum spanning tree cost (only for tiny graphs)."""
    from algorithms import has_cycle, is_connected
    n = len(nodes)
    best = None
    for combo in itertools.combinations(edges, n - 1):
        if not has_cycle(nodes, combo) and is_connected(nodes, combo):
            cost = sum(e[2] for e in combo)
            best = cost if best is None else min(best, cost)
    return best


@pytest.fixture
def sample():
    return list(NODES), list(SAMPLE_EDGES)


@pytest.fixture
def db_path(tmp_path):
    from database import db
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


@pytest.fixture
def sample_db(db_path):
    from database import db
    db.seed_sample_data(db_path)
    return db_path
