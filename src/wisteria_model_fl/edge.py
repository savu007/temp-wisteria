"""edge class for neighbor accsibility"""


class Edge:
    def __init__(self, weight: int = 2, pregrown: bool = False) -> None:
        self.weight = weight
        self.pregrown = pregrown
