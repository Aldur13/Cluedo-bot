"""Guard-rail test: the exact solver's modules must never depend on the
behavioral-analysis, ML, or persistence layers built on top of it. Those
layers are read-only consumers of GameState/history -- if any of them ever
gets imported back into the solver, the "AI never influences deductions"
guarantee has silently broken."""
import ast
from pathlib import Path

import pytest

SOLVER_MODULES = [
    "cluedo/engine.py",
    "cluedo/advisor.py",
    "cluedo/probability.py",
    "cluedo/explain.py",
]

# cluedo/movement/ is deliberately NOT in this list: movement/scoring.py
# imports cluedo.advisor (one-way -- advisor.py itself stays untouched) to
# combine board reachability with expected-info-gain scoring. Don't "fix"
# this by adding movement/ here; that would break the intended dependency.

FORBIDDEN_PREFIXES = ("cluedo.analysis", "cluedo.ml", "cluedo.persistence")

REPO_ROOT = Path(__file__).resolve().parent.parent


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("relative_path", SOLVER_MODULES)
def test_solver_module_never_imports_analysis_ml_or_persistence(relative_path):
    path = REPO_ROOT / relative_path
    imported = _imported_module_names(path)
    violations = [
        name for name in imported if any(name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
    ]
    assert not violations, (
        f"{relative_path} must never import the analysis/ml/persistence layers, "
        f"but imports: {violations}"
    )
