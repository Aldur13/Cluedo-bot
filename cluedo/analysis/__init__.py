"""Read-only behavioral-analysis layer built on top of GameState/history.

Everything in this package is a *consumer* of `cluedo.game`/`cluedo.models`/
`cluedo.history` -- it never feeds conclusions back into the exact solver.
`tests/test_architecture_boundaries.py` enforces that `engine.py`,
`advisor.py`, `probability.py`, and `explain.py` never import this package.
"""
