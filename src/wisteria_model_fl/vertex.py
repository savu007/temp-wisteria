"""Algorithmic state for one decoding-graph vertex."""

from __future__ import annotations

from .edge import Edge

class VertexState:

    def __init__(self, index: int, defect: bool) -> None:
        self.index = index
        self.cindex = index
        self.parent: VertexState = self
        self.radius = 0
        self.defect = defect
        self.parity = defect
        self.active = defect
        self.busy = False
        self.neighbors: dict[VertexState, Edge] = {}

    def connect(self, v: VertexState, weight: int = 2, pregrown: bool = False) -> Edge:
        edge = Edge(weight, pregrown)
        self.neighbors[v] = edge
        v.neighbors[self] = edge
        return edge
