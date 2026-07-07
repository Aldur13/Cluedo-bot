"""Per-card "last changed turn" tracking, built on top of
history.build_replay_snapshots. Pure-core, GUI-agnostic: the sheet grid
(Phase 3) and hover tooltips (mystery_progress) use this to highlight cards
whose detective-sheet entry recently changed.
"""
from __future__ import annotations

from cluedo.game import GameState
from cluedo.history import build_replay_snapshots
from cluedo.models import Card


def compute_last_changed_turns(game_state: GameState) -> dict[Card, int]:
    """For every card, the highest history-prefix-index (0 = right after the
    initial hand is applied, before any suggestions; i = after the i-th
    suggestion) at which its detective_sheet() entry last differed from the
    immediately preceding snapshot.

    Snapshot 0 has no predecessor to diff against, so every card is defined
    to be last-changed-at-turn-0 there. Later snapshots (i = 1..N) are diffed
    against snapshot i-1; whenever a card's status/owner/possible-set differs,
    turn i becomes its new last-changed turn (the highest such i wins, since
    we walk forward in order).
    """
    snapshots = build_replay_snapshots(game_state)

    last_changed: dict[Card, int] = {card: 0 for card in game_state.cards}

    previous_sheet = snapshots[0].game_state.detective_sheet()
    for snap in snapshots[1:]:
        sheet = snap.game_state.detective_sheet()
        for card in game_state.cards:
            prev_entry = previous_sheet[card]
            entry = sheet[card]
            if entry["status"] != prev_entry["status"] or entry["possible"] != prev_entry["possible"]:
                last_changed[card] = snap.step_index
        previous_sheet = sheet

    return last_changed
