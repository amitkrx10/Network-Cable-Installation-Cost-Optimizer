import random

import pytest

from algorithms import GraphError, kruskal_mst, prim_mst, verify_mst
from modules.benchmarking import generate_random_graph
from tests._mst_cases import MSTSuite
from tests.conftest import NODES, SAMPLE_EDGES


class TestPrim(MSTSuite):
    algo = staticmethod(prim_mst)

    def test_start_vertex_does_not_change_cost(self):
        costs = {prim_mst(NODES, SAMPLE_EDGES, start=s).total_cost for s in NODES}
        assert costs == {13000}

    def test_unknown_start_rejected(self):
        with pytest.raises(GraphError):
            prim_mst(NODES, SAMPLE_EDGES, start=99)

    def test_first_selected_edge_touches_start(self):
        r = prim_mst(NODES, SAMPLE_EDGES, start=4)
        first = r.mst_edges[0]
        assert 4 in (first.u, first.v) and first.weight == 2000  # D-E

    def test_complexity_strings(self):
        assert prim_mst(NODES, SAMPLE_EDGES).time_complexity == "O((V + E) log V)"


@pytest.mark.parametrize("seed", range(10))
def test_prim_equals_kruskal_on_random_graphs(seed):
    nodes, edges = generate_random_graph(40, 120, seed=seed, max_weight=20)  # many ties
    p, k = prim_mst(nodes, edges), kruskal_mst(nodes, edges)
    assert p.total_cost == k.total_cost
    assert verify_mst(nodes, edges, p)["Valid MST"] and verify_mst(nodes, edges, k)["Valid MST"]
