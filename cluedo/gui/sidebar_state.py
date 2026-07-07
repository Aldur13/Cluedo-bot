"""Session-scoped (never persisted to disk) UI state for the sidebar:
which cards are expanded/collapsed, plus per-card "Show All"/"Show Why"
toggle flags. Resets naturally on process restart -- there's no existing
UI-preference storage to persist into (cluedo.persistence.player_store is
game analytics, not UI layout), and adding one is out of scope for a
presentation-only redesign. A plain module-level dict is enough: every
sidebar card is rebuilt against the same running process, so state set by
one refresh cycle is still there for the next.
"""
from __future__ import annotations

_expanded: dict[str, bool] = {}
_flags: dict[str, bool] = {}


def get_expanded(key: str, default: bool = True) -> bool:
    return _expanded.get(key, default)


def set_expanded(key: str, value: bool) -> None:
    _expanded[key] = value


def get_flag(key: str, default: bool = False) -> bool:
    return _flags.get(key, default)


def set_flag(key: str, value: bool) -> None:
    _flags[key] = value


def toggle_flag(key: str, default: bool = False) -> bool:
    new_value = not get_flag(key, default)
    set_flag(key, new_value)
    return new_value
