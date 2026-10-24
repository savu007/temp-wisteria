"""lowk all of this is from paper box 2 directly """

from .vertex import VertexState


def initialize(index: int, defect: bool) -> VertexState:
    return VertexState(index, defect)


def grow(u: VertexState, w_max: int) -> None:
    if u.active and u.radius <= w_max:
        u.radius += 1


def merge(
    u: VertexState, accessible_neighbors: list[VertexState]
) -> None:
    # I dont think there is a way for busy to become false according to paper?
    for v in accessible_neighbors:
        if u.cindex > v.cindex:
            u.cindex = v.cindex
            u.parent = v
            u.busy = True

        if u.parity and u.parent is not u:
            u.parent.parity = not u.parent.parity
            u.parity = False
            u.busy = True


def pick(u: VertexState) -> None:
    u.active = u.parity


def sync(
    u: VertexState, accessible_neighbors: list[VertexState]
) -> None:
    u.busy = any(v.active for v in accessible_neighbors)
    u.busy = u.busy and not u.active
    u.active = u.active or u.busy
