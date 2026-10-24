"""1-vertex PE interface"""

from dataclasses import dataclass

from . import stages
from .vertex import VertexState


@dataclass
class ProcessingElement:

    vertex: VertexState
    w_max: int

    @classmethod
    def from_syndrome(
        cls, index: int, defect: bool, w_max: int
    ) -> "ProcessingElement":
        return cls(vertex=stages.initialize(index, defect), w_max=w_max)

    def grow(self) -> None:
        stages.grow(self.vertex, self.w_max)

    @property
    def accessible_neighbors(self) -> list[VertexState]:
        u = self.vertex
        return [v for v, edge in u.neighbors.items()
                if edge.pregrown or u.radius + v.radius >= edge.weight]

    def merge(self) -> None:
        stages.merge(self.vertex, self.accessible_neighbors)

    def pick(self) -> None:
        stages.pick(self.vertex)

    def sync(self) -> None:
        stages.sync(self.vertex, self.accessible_neighbors)
