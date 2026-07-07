"""Local SQLite-backed cross-game player history store (Phase 6 of the v2.0
plan). stdlib `sqlite3` only -- no new dependency.

This module is a read-only-in-spirit consumer of `GameState`/`cluedo.models`:
it records what happened, once a caller (future dashboard wiring) chooses to
tell it, and never feeds anything back into `cluedo/engine.py`,
`cluedo/probability.py`, `cluedo/advisor.py`, or `cluedo/explain.py`. See
`tests/test_architecture_boundaries.py`.

Schema (matches the plan exactly, no column changes)::

    CREATE TABLE games(
      game_id TEXT PRIMARY KEY, edition TEXT, started_at TEXT, ended_at TEXT,
      player_count INTEGER, solved INTEGER, solved_turn INTEGER, solution_json TEXT
    );
    CREATE TABLE players_in_game(
      game_id TEXT, seat_index INTEGER, player_name TEXT, hand_size INTEGER
    );
    CREATE TABLE suggestions(
      game_id TEXT, suggestion_index INTEGER, suggester_seat INTEGER,
      suspect TEXT, weapon TEXT, room TEXT, responses_json TEXT
    );
    CREATE TABLE player_profile(
      player_name TEXT PRIMARY KEY, games_played INTEGER, games_solved INTEGER,
      avg_solve_turn REAL, bluff_signal_rate REAL, favorite_suspect TEXT,
      favorite_weapon TEXT, favorite_room TEXT, strategy_label TEXT, last_updated TEXT
    );
    CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);

No columns were added or removed relative to the plan. Two honest notes on
what `player_profile` can and can't compute *today*, from *this* schema alone
(documented here rather than silently guessed at):

- `bluff_signal_rate` is left NULL by `rebuild_player_profiles()`. The plan
  defines a bluff signal as "the suggested triple contains a card later
  confirmed to be in the *suggester's own hand*" -- but this schema (by
  design) never stores hand *contents*, only `hand_size`, so as not to persist
  what amounts to other players' revealed cards outside of what the solver
  already derives live. Phase 7's `cluedo/ml/features.py` computes this label
  correctly by replaying that game's own history/engine state directly (which
  does have hand contents in memory for the live game), not by reading it back
  out of this aggregate store. A future writer could pass a precomputed rate
  into a dedicated update path if that turns out to be useful; until then this
  column stays honestly NULL instead of showing a fabricated number.
- `strategy_label` is likewise left NULL here. It's Phase 5's
  `cluedo.analysis.strategy.classify_strategy()` output; this module only
  aggregates raw counts, it doesn't duplicate that classification logic.

Fail-closed reliability, matching `cluedo.game.save_game`/`load_game`'s
established style:

- Every write goes through `_safe_write`, which is wrapped in
  try/except sqlite3.Error and never raises -- a persistence hiccup must never
  crash the app.
- If the DB file is corrupt/unreadable at startup (`sqlite3.DatabaseError`),
  it is moved aside as `<name>.corrupt.bak` (rolling: any previous
  `.corrupt.bak` is replaced) and a fresh, empty database is created in its
  place, mirroring the rolling `.bak` pattern `save_game()` already uses for
  the JSON autosave file.
- All `record_*` methods no-op quickly (no exception, no work) when
  `is_learning_enabled()` is False, so call sites never need to guard on the
  setting themselves.
"""
from __future__ import annotations

import os
import json
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from cluedo.models import Player, Suggestion

DEFAULT_DB_NAME = "player_history.sqlite3"
LEARNING_ENABLED_KEY = "cross_game_learning_enabled"

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    edition TEXT,
    started_at TEXT,
    ended_at TEXT,
    player_count INTEGER,
    solved INTEGER,
    solved_turn INTEGER,
    solution_json TEXT
);
CREATE TABLE IF NOT EXISTS players_in_game (
    game_id TEXT,
    seat_index INTEGER,
    player_name TEXT,
    hand_size INTEGER
);
CREATE TABLE IF NOT EXISTS suggestions (
    game_id TEXT,
    suggestion_index INTEGER,
    suggester_seat INTEGER,
    suspect TEXT,
    weapon TEXT,
    room TEXT,
    responses_json TEXT
);
CREATE TABLE IF NOT EXISTS player_profile (
    player_name TEXT PRIMARY KEY,
    games_played INTEGER,
    games_solved INTEGER,
    avg_solve_turn REAL,
    bluff_signal_rate REAL,
    favorite_suspect TEXT,
    favorite_weapon TEXT,
    favorite_room TEXT,
    strategy_label TEXT,
    last_updated TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

_PROFILE_COLUMNS = (
    "player_name",
    "games_played",
    "games_solved",
    "avg_solve_turn",
    "bluff_signal_rate",
    "favorite_suspect",
    "favorite_weapon",
    "favorite_room",
    "strategy_label",
    "last_updated",
)


def default_store_path() -> Path:
    """Same directory as `cluedo.game.default_autosave_path()`, sibling file."""
    base = Path(os.environ.get("APPDATA") or Path.home() / ".cluedo_assistant")
    return base / "CluedoAssistant" / DEFAULT_DB_NAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _most_common(values) -> Optional[str]:
    values = [v for v in values if v]
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


class PlayerStore:
    """Local cross-game history store. Never raises out of any public method
    (aside from constructor arguments that are simply wrong types) -- every
    failure mode degrades to "no data recorded / nothing read back" rather
    than an exception bubbling into the GUI.
    """

    def __init__(self, path: "Path | str | None" = None):
        self.path = Path(path) if path is not None else default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection = self._open_or_recover()

    # ------------------------------------------------------------- lifecycle

    def _open_or_recover(self) -> sqlite3.Connection:
        try:
            conn = self._connect_and_init(self.path)
            return conn
        except sqlite3.DatabaseError:
            self._quarantine_corrupt_file()
            # Fresh file: if this second attempt still fails, something more
            # fundamental is wrong (e.g. an unwritable directory) -- at that
            # point we let it raise rather than looping forever, but a plain
            # corrupt-bytes file is guaranteed fixed by the quarantine above.
            return self._connect_and_init(self.path)

    def _connect_and_init(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            conn.executescript(_CREATE_TABLES_SQL)
            conn.commit()
            # Force an actual read so header/page corruption that
            # executescript's CREATE TABLE IF NOT EXISTS might not touch is
            # still detected here, at construction time, rather than on the
            # first real write later.
            conn.execute("SELECT COUNT(*) FROM settings").fetchone()
        except sqlite3.DatabaseError:
            conn.close()
            raise
        return conn

    def _quarantine_corrupt_file(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
        if self.path.exists():
            backup_path = self.path.with_name(self.path.name + ".corrupt.bak")
            try:
                if backup_path.exists():
                    backup_path.unlink()
                self.path.replace(backup_path)
            except OSError:
                try:
                    self.path.unlink()
                except OSError:
                    pass
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = self.path.with_name(self.path.name + suffix)
            try:
                if sidecar.exists():
                    sidecar.unlink()
            except OSError:
                pass

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> "PlayerStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ------------------------------------------------------------ safe I/O

    def _safe_write(self, fn: Callable[[sqlite3.Connection], None]) -> None:
        try:
            with self._lock:
                fn(self._conn)
                self._conn.commit()
        except sqlite3.Error:
            try:
                self._conn.rollback()
            except sqlite3.Error:
                pass

    def _safe_read(self, fn: Callable[[sqlite3.Connection], object], default):
        try:
            with self._lock:
                return fn(self._conn)
        except sqlite3.Error:
            return default

    # --------------------------------------------------------------- settings

    def is_learning_enabled(self) -> bool:
        """Defaults to ON.

        Reasoning: this store is entirely local (no network access), records
        only data the user already typed into this app (player display names,
        seat indices, hand *sizes*, suggestion triples, and game outcomes),
        and exists specifically to power the on-device pattern/ML insights
        the user asked for in this rebuild. A visible opt-out toggle and a
        one-click `reset_all_data()` wipe ship in this same phase (Phase 8
        surfaces both in Settings), so choosing ON-by-default doesn't create
        any data that isn't trivially reversible. Defaulting OFF would make
        cross-game learning a dead feature for the overwhelming majority of
        users who never open Settings, defeating the point of building it.
        """
        row = self._safe_read(
            lambda conn: conn.execute(
                "SELECT value FROM settings WHERE key = ?", (LEARNING_ENABLED_KEY,)
            ).fetchone(),
            None,
        )
        if row is None:
            return True
        return row[0] == "1"

    def set_learning_enabled(self, enabled: bool) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (LEARNING_ENABLED_KEY, "1" if enabled else "0"),
            )

        self._safe_write(_do)

    # ----------------------------------------------------------------- writes

    def record_game_start(self, game_id: str, edition: str, players: list[Player]) -> None:
        if not self.is_learning_enabled():
            return

        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO games(game_id, edition, started_at, ended_at, player_count, "
                "solved, solved_turn, solution_json) VALUES (?, ?, ?, NULL, ?, 0, NULL, NULL) "
                "ON CONFLICT(game_id) DO UPDATE SET edition = excluded.edition, "
                "player_count = excluded.player_count",
                (game_id, edition, _now_iso(), len(players)),
            )
            conn.execute("DELETE FROM players_in_game WHERE game_id = ?", (game_id,))
            conn.executemany(
                "INSERT INTO players_in_game(game_id, seat_index, player_name, hand_size) "
                "VALUES (?, ?, ?, ?)",
                [(game_id, p.seat_index, p.name, p.hand_size) for p in players],
            )

        self._safe_write(_do)

    def record_suggestion(self, game_id: str, suggestion_index: int, suggestion: Suggestion) -> None:
        """Upserts a single suggestion row, keyed by (game_id, suggestion_index).
        Safe to call repeatedly for the same index (e.g. after an edit/undo
        rebuilds history) -- matches the plan's "treat it like autosave"
        trigger of firing after every mutation with the full current history.
        """
        if not self.is_learning_enabled():
            return

        responses_json = json.dumps(
            [
                {
                    "responder_seat": r.responder_seat,
                    "outcome": r.outcome,
                    "shown_card": r.shown_card.name if r.shown_card else None,
                }
                for r in suggestion.responses
            ]
        )

        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "DELETE FROM suggestions WHERE game_id = ? AND suggestion_index = ?",
                (game_id, suggestion_index),
            )
            conn.execute(
                "INSERT INTO suggestions(game_id, suggestion_index, suggester_seat, suspect, "
                "weapon, room, responses_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    suggestion_index,
                    suggestion.suggester_seat,
                    suggestion.suspect.name,
                    suggestion.weapon.name,
                    suggestion.room.name,
                    responses_json,
                ),
            )

        self._safe_write(_do)

    def record_game_end(self, game_id: str, solved: bool, solved_turn: Optional[int], solution) -> None:
        """`solution` is the `(suspect_card, weapon_card, room_card)` tuple
        `GameState.solution()`/`ConstraintEngine.solution()` return, or None.
        """
        if not self.is_learning_enabled():
            return

        solution_json = None
        if solution is not None:
            suspect, weapon, room = solution
            solution_json = json.dumps(
                {"suspect": suspect.name, "weapon": weapon.name, "room": room.name}
            )

        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE games SET ended_at = ?, solved = ?, solved_turn = ?, solution_json = ? "
                "WHERE game_id = ?",
                (_now_iso(), 1 if solved else 0, solved_turn, solution_json, game_id),
            )

        self._safe_write(_do)

    # ------------------------------------------------------------------ reads

    def get_player_profile(self, player_name: str) -> Optional[dict]:
        row = self._safe_read(
            lambda conn: conn.execute(
                f"SELECT {', '.join(_PROFILE_COLUMNS)} FROM player_profile WHERE player_name = ?",
                (player_name,),
            ).fetchone(),
            None,
        )
        if row is None:
            return None
        return dict(zip(_PROFILE_COLUMNS, row))

    # ------------------------------------------------------------ maintenance

    def reset_all_data(self) -> None:
        """Wipes gameplay history (games/players_in_game/suggestions/
        player_profile) for the privacy "reset" control. Deliberately leaves
        `settings` (the learning opt-out flag itself, theme prefs) intact --
        those are app preferences, not recorded gameplay data, and wiping the
        opt-out choice on every reset would be a surprising, likely unwanted
        side effect (e.g. silently re-enabling learning).
        """

        def _do(conn: sqlite3.Connection) -> None:
            for table in ("games", "players_in_game", "suggestions", "player_profile"):
                conn.execute(f"DELETE FROM {table}")

        self._safe_write(_do)

    def rebuild_player_profiles(self) -> None:
        """Recomputes `player_profile` from `games`/`players_in_game`/
        `suggestions` from scratch. Treated as a rebuildable cache, not
        authoritative, per the plan -- safe to call any time (e.g. after
        `reset_all_data`, after a corrupt-DB recovery, or periodically).
        """

        def _do(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM player_profile")
            player_names = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT player_name FROM players_in_game"
                ).fetchall()
            ]
            now = _now_iso()
            for player_name in player_names:
                seat_rows = conn.execute(
                    "SELECT pig.game_id, pig.seat_index, g.solved, g.solved_turn "
                    "FROM players_in_game pig JOIN games g ON g.game_id = pig.game_id "
                    "WHERE pig.player_name = ?",
                    (player_name,),
                ).fetchall()
                games_played = len(seat_rows)
                games_solved = sum(1 for (_, _, solved, _) in seat_rows if solved)
                solve_turns = [
                    solved_turn
                    for (_, _, solved, solved_turn) in seat_rows
                    if solved and solved_turn is not None
                ]
                avg_solve_turn = (sum(solve_turns) / len(solve_turns)) if solve_turns else None

                suspects: list[str] = []
                weapons: list[str] = []
                rooms: list[str] = []
                for game_id, seat_index, _, _ in seat_rows:
                    triple_rows = conn.execute(
                        "SELECT suspect, weapon, room FROM suggestions "
                        "WHERE game_id = ? AND suggester_seat = ?",
                        (game_id, seat_index),
                    ).fetchall()
                    for suspect, weapon, room in triple_rows:
                        suspects.append(suspect)
                        weapons.append(weapon)
                        rooms.append(room)

                conn.execute(
                    "INSERT INTO player_profile(player_name, games_played, games_solved, "
                    "avg_solve_turn, bluff_signal_rate, favorite_suspect, favorite_weapon, "
                    "favorite_room, strategy_label, last_updated) "
                    "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, NULL, ?)",
                    (
                        player_name,
                        games_played,
                        games_solved,
                        avg_solve_turn,
                        _most_common(suspects),
                        _most_common(weapons),
                        _most_common(rooms),
                        now,
                    ),
                )

        self._safe_write(_do)
