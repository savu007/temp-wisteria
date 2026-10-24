# Verification plan

Run from the repository root:

```sh
PYTHONPATH=src python3.12 -m unittest discover -s tests -v
```

`test_stages.py` checks hand-worked initialization and Box 2 cases:

- Defect/nondefect initialization and independent vertex records.
- Active/inactive growth below, at, and above the inclusive radius limit.
- Parent selection, ties, reparenting, and neighbor-order effects.
- Parity cancellation, transfer up a chain, and repeated merges.
- Picking and syncing bit combinations, including stale busy flags.
- Unchanged fields and neighbor records where no write is expected.
- Two-defect neutralization and three-defect activity propagation.

`test_accessibility.py` tests the public PE interface with real connections:
threshold equality and overshoot, both endpoint radii, pregrown flags, shared edge
updates, blocked neighbors, connection order, and an isolated vertex. A two-defect
example grows an edge, merges, picks, and syncs through PE methods.

`test_stages.py` passes prefiltered neighbors directly to merge/sync kernels to
isolate Box 2 behavior. Its chain examples use manual passes. Neither suite
implements a controller; the caller still clears busy between merge passes.

Full graph construction, boundaries, correction extraction, and decoder-wide
convergence remain outside this suite.
