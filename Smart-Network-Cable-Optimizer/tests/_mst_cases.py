"""Shared behavioural test-suite applied to both algorithms."""
import math

import networkx as nx
import pytest

from algorithms import GraphError, has_cycle, is_connected, verify_mst
from tests.conftest import NODES, SAMPLE_EDGES, brute_force_mst_cost


class MSTSuite:
    algo = None  # set by subclass (staticmethod)

    def run(self, nodes, edges, **kw):
        return type(self).algo(nodes, edges, **kw)

    def test_sample_network_cost_and_edges(self):
        r = self.run(NODES, SAMPLE_EDGES)
        assert r.total_cost == 13000
        assert r.connected and r.selected_count == 5
        chosen = {frozenset((e.u, e.v)): e.weight for e in r.mst_edges}
        assert chosen == {frozenset((2, 3)): 1000, frozenset((1, 3)): 2000, frozenset((4, 5)): 2000,
                          frozenset((5, 6)): 3000, frozenset((2, 4)): 5000}

    def test_all_possible_cost_and_savings(self):
        total = sum(e[2] for e in SAMPLE_EDGES)
        r = self.run(NODES, SAMPLE_EDGES)
        assert total == 41000 and total - r.total_cost == 28000
        assert round((total - r.total_cost) / total * 100, 2) == 68.29

    def test_valid_mst_properties(self):
        r = self.run(NODES, SAMPLE_EDGES)
        assert len(r.mst_edges) == len(NODES) - 1
        assert not has_cycle(NODES, r.mst_edges)
        assert is_connected(NODES, r.mst_edges)
        assert verify_mst(NODES, SAMPLE_EDGES, r)["Valid MST"]

    def test_cost_is_minimum_vs_brute_force(self):
        assert self.run(NODES, SAMPLE_EDGES).total_cost == brute_force_mst_cost(NODES, SAMPLE_EDGES)

    def test_cost_matches_networkx_reference(self):
        G = nx.Graph()
        G.add_weighted_edges_from(SAMPLE_EDGES)
        ref = sum(d["weight"] for _, _, d in nx.minimum_spanning_edges(G, data=True))
        assert self.run(NODES, SAMPLE_EDGES).total_cost == ref

    def test_disconnected_graph(self):
        r = self.run([1, 2, 3, 4], [(1, 2, 5), (3, 4, 7)])
        assert not r.connected and r.num_components == 2
        assert r.total_cost == 12 and r.selected_count == 2  # spanning forest

    def test_isolated_building_is_disconnected(self):
        r = self.run([1, 2, 3], [(1, 2, 5)])
        assert not r.connected and r.num_components == 2

    def test_single_building(self):
        r = self.run([1], [])
        assert r.connected and r.total_cost == 0 and r.mst_edges == []

    def test_two_buildings(self):
        r = self.run([1, 2], [(1, 2, 9)])
        assert r.connected and r.total_cost == 9 and r.selected_count == 1

    def test_two_buildings_without_edge(self):
        assert not self.run([1, 2], []).connected

    def test_equal_weight_edges(self):
        edges = [(1, 2, 5), (2, 3, 5), (1, 3, 5), (3, 4, 5)]
        r = self.run([1, 2, 3, 4], edges)
        assert r.total_cost == 15 and r.selected_count == 3
        assert not has_cycle([1, 2, 3, 4], r.mst_edges)

    def test_parallel_duplicate_edges_pick_cheapest(self):
        r = self.run([1, 2], [(1, 2, 9), (1, 2, 4), (2, 1, 6)])
        assert r.total_cost == 4 and r.selected_count == 1

    def test_zero_cost_edges_allowed(self):
        r = self.run([1, 2, 3], [(1, 2, 0), (2, 3, 0), (1, 3, 5)])
        assert r.total_cost == 0 and r.selected_count == 2

    @pytest.mark.parametrize("bad", [(1, 2, -1), (1, 2, float("nan")), (1, 2, float("inf")), (1, 2, "abc")])
    def test_invalid_weights_rejected(self, bad):
        with pytest.raises(GraphError):
            self.run([1, 2], [bad])

    def test_self_loop_and_unknown_vertex_rejected(self):
        with pytest.raises(GraphError):
            self.run([1, 2], [(1, 1, 3)])
        with pytest.raises(GraphError):
            self.run([1, 2], [(1, 9, 3)])

    def test_steps_are_recorded_and_consistent(self):
        r = self.run(NODES, SAMPLE_EDGES)
        assert len(r.steps) == r.edges_processed
        assert sum(s["status"] == "selected" for s in r.steps) == r.selected_count
        assert sum(s["status"] == "rejected" for s in r.steps) == r.edges_rejected
        assert r.steps[-1]["mst_cost"] == r.total_cost
        assert all(s["reason"] for s in r.steps)

    def test_no_steps_when_disabled(self):
        assert self.run(NODES, SAMPLE_EDGES, record_steps=False).steps == []

    def test_execution_time_and_complexity_reported(self):
        r = self.run(NODES, SAMPLE_EDGES)
        assert r.execution_time >= 0 and r.time_complexity and r.space_complexity

    def test_edge_ids_preserved(self):
        edges = [(1, 2, 3, "x"), (2, 3, 1, "y"), (1, 3, 2, "z")]
        r = self.run([1, 2, 3], edges)
        assert {e.eid for e in r.mst_edges} == {"y", "z"}
