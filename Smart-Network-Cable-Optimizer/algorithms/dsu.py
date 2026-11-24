"""Disjoint Set Union (Union-Find).

Optimisations implemented manually:
  * Path compression  - find() flattens the tree it walks along.
  * Union by rank     - the shallower tree is attached below the deeper one.
With both, a sequence of m operations on n elements costs O(m * alpha(n)),
where alpha is the inverse Ackermann function (< 5 for any practical n).
"""
from __future__ import annotations

from typing import Dict, Hashable, Iterable, List


class DSU:
    def __init__(self, items: Iterable[Hashable] = ()):
        self.parent: Dict[Hashable, Hashable] = {}
        self.rank: Dict[Hashable, int] = {}
        self.size: Dict[Hashable, int] = {}
        self.components = 0
        for item in items:
            self.make_set(item)

    def make_set(self, x: Hashable) -> None:
        """Create a singleton set {x} (no-op if x already exists)."""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            self.size[x] = 1
            self.components += 1

    def find(self, x: Hashable) -> Hashable:
        """Return the representative of x's set (with path compression)."""
        if x not in self.parent:
            raise KeyError(f"Unknown element: {x!r}")
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # second pass: compress the path
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: Hashable, b: Hashable) -> bool:
        """Merge the sets of a and b (union by rank).

        Returns True if a merge happened, False if a and b were already in the
        same set (i.e. adding edge a-b would create a cycle).
        """
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        self.components -= 1
        return True

    def connected(self, a: Hashable, b: Hashable) -> bool:
        return self.find(a) == self.find(b)

    def component_size(self, x: Hashable) -> int:
        return self.size[self.find(x)]

    def groups(self) -> Dict[Hashable, List[Hashable]]:
        """Map representative -> list of members."""
        out: Dict[Hashable, List[Hashable]] = {}
        for x in self.parent:
            out.setdefault(self.find(x), []).append(x)
        return out
