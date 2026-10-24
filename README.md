# wisteria-model
Ref-model repository for FPGA QEC decoding project, Wisteria

## Initial scope

A functional model of **one processing element (PE) owning one vertex**.
The PE is the public interface; its vertex record stores algorithmic state, and
its methods delegate to separate stage kernels. The four stage kernels implement
LCD Box 2; initialization follows the accompanying vertex-state definitions.
The full decoder remains unimplemented.

The functional model retains algorithmic state but does not model clock cycles.
A cycle-level model can follow once the functional rules and hardware timing
contract are defined. A hardware PE may eventually own multiple vertex records.

## Layout

```text
src/wisteria_model_fl/
    __init__.py
    pe.py           # One-vertex PE interface and stage delegation
    vertex.py       # Vertex state and neighbor connections
    edge.py         # Shared edge weight and pregrown flag
    stages.py       # Initialization and Box 2 stage kernels
tests/
    README.md       # Planned verification scope
    test_stages.py  # Kernel regression tests
    test_accessibility.py  # PE accessibility and integration tests
```

## Development

Requires Python 3.10 or newer. The commands below use Python 3.12, available in
this workspace. The model currently uses only the standard library.
From the repository root, check imports without installing the package:

```sh
PYTHONPATH=src python3.12 -c "from wisteria_model_fl import ProcessingElement, VertexState"
```

Run tests with:

```sh
PYTHONPATH=src python3.12 -m unittest discover -s tests
```

## Decisions to work through

- Controller rules, following LCD Box 1.
- Full graph construction and boundary handling.
- Scheduling of PE calls and their shared-state updates.
- When busy flags are cleared and how a future controller detects convergence.

Vertices store neighbor references mapped to shared edge records. The PE computes
accessibility from current radii, edge weights, and pregrown flags. Parents are
direct vertex references. No scheduling, PE communication timing, or correction
extraction is implemented yet.

## PE interface

`ProcessingElement(vertex, w_max)` accepts an explicit vertex record, allowing
tests to start from intermediate algorithm states. The PE exposes:

| Entry point | Purpose |
| --- | --- |
| `ProcessingElement.from_syndrome(index, defect, w_max)` | Initialize a vertex and construct its PE |
| `pe.grow()` | Apply one growing operation |
| `pe.merge()` | Apply one merging operation, including parent parity effects |
| `pe.pick()` | Apply one picking operation |
| `pe.sync()` | Apply one syncing operation |
| `pe.vertex` | Inspect the owned vertex's current state |
| `pe.accessible_neighbors` | Compute the currently accessible neighbor records |
| `u.connect(v, weight=2, pregrown=False)` | Connect both vertices using one shared edge record |

Initialization and all four stage methods are implemented.

Connect vertices once, then invoke the PE without passing neighbor lists:

```python
from wisteria_model_fl import ProcessingElement

first = ProcessingElement.from_syndrome(0, True, w_max=2)
second = ProcessingElement.from_syndrome(1, True, w_max=2)
u, v = first.vertex, second.vertex
edge = u.connect(v, weight=2)
first.grow()
second.grow()
second.merge()  # The radii now sum to the edge weight.
```

`u.neighbors[v]` and `v.neighbors[u]` refer to the same `Edge`. Calling
`connect` again replaces the existing edge between those vertices. Set
`edge.pregrown = True` to make the connection accessible regardless of radii.
An external caller supplies this flag; there is no adaptivity engine in the model.

Accessibility is recomputed on each `merge()` or `sync()` call:
`edge.pregrown or u.radius + v.radius >= edge.weight`. Edge weights default to 2
for an unweighted graph. Supply each PE's `w_max` as its maximum incident weight;
if weights change, keep `w_max` consistent with them.

Neighbors are visited in connection insertion order, with writes immediately
visible. This ordering is a model convention; the paper prescribes no neighbor
order. The kernels still accept prefiltered records for isolated kernel tests.
Parity transfer stays inside the merge loop. Merging only sets busy; the caller
must clear stale busy flags before a new pass when needed. Syncing overwrites
busy; growing and picking leave it unchanged. The inclusive `<= w_max` growth
condition permits a radius of `w_max + 1`.

Kernel arguments use `u` for the current vertex and `v` for a neighbor, following
Box 2. The PE exposes its owned record through the descriptive `pe.vertex` name.

`VertexState(index, defect)` is a regular class. Its constructor initializes a
singleton cluster and assigns `self.parent = self`. To build intermediate test
states, construct a vertex and assign the desired fields, such as `u.parent = v`
or `u.radius = 2`. Root checks use `is` to compare vertex identity.

One method call represents one local kernel execution, not an entire globally
converged stage. A future controller will decide which operations to repeat.

Reference: [Local clustering decoder as a fast and adaptive hardware decoder
for the surface code](https://www.nature.com/articles/s41467-025-66773-x).
