"""Cross-game persistence layer (Phase 6).

Read-only-in-spirit consumer of GameState/history: records what happened for
later behavioral analysis (Phase 5) and ML (Phase 7). Never imported by
cluedo/engine.py, cluedo/probability.py, cluedo/advisor.py, or
cluedo/explain.py -- see tests/test_architecture_boundaries.py.
"""
from cluedo.persistence.player_store import PlayerStore, default_store_path

__all__ = ["PlayerStore", "default_store_path"]
