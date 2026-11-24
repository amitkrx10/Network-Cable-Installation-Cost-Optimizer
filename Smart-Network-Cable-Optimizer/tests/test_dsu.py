import pytest

from algorithms import DSU


def test_union_find_basic():
    d = DSU(range(5))
    assert d.components == 5
    assert d.union(0, 1) and d.union(1, 2)
    assert d.connected(0, 2) and not d.connected(0, 3)
    assert d.components == 3


def test_cycle_detection_union_returns_false():
    d = DSU("abc")
    assert d.union("a", "b") and d.union("b", "c")
    assert d.union("a", "c") is False  # would close a cycle


def test_path_compression_flattens_tree():
    d = DSU(range(6))
    d.parent.update({0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4})  # chain 5->4->3->2->1->0
    assert d.find(5) == 0
    assert all(d.parent[x] == 0 for x in range(1, 6))


def test_union_by_rank_keeps_trees_shallow():
    d = DSU(range(8))
    for a, b in [(0, 1), (2, 3), (0, 2), (4, 5), (6, 7), (4, 6), (0, 4)]:
        d.union(a, b)
    assert d.components == 1
    assert max(d.rank.values()) <= 3  # log2(8)
    assert d.component_size(5) == 8


def test_unknown_element():
    with pytest.raises(KeyError):
        DSU([1]).find(2)
