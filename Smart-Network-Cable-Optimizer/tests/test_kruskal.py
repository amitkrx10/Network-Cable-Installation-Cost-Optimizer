from algorithms import kruskal_mst
from tests._mst_cases import MSTSuite
from tests.conftest import NODES, SAMPLE_EDGES


class TestKruskal(MSTSuite):
    algo = staticmethod(kruskal_mst)

    def test_edges_examined_in_ascending_order(self):
        weights = [s["weight"] for s in kruskal_mst(NODES, SAMPLE_EDGES).steps]
        assert weights == sorted(weights)

    def test_cycle_edge_rejected(self):
        r = kruskal_mst(NODES, SAMPLE_EDGES)
        rejected = [(s["u"], s["v"]) for s in r.steps if s["status"] == "rejected"]
        assert rejected == [(1, 2)]  # A-B (4000) closes the cycle A-B-C

    def test_stops_early_when_tree_complete(self):
        r = kruskal_mst(NODES, SAMPLE_EDGES)
        assert r.edges_processed == 6 and r.num_edges == 9

    def test_complexity_strings(self):
        assert kruskal_mst(NODES, SAMPLE_EDGES).time_complexity.startswith("O(E log E)")
