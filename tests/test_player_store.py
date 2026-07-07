import sqlite3
import tempfile
from pathlib import Path

import pytest

from cluedo.models import Player, Suggestion, SuggestionResponse
from cluedo.persistence.player_store import PlayerStore

GAME_ID = "game-1"


def _players():
    return [Player("Alice", 0, 6), Player("Bob", 1, 6), Player("Carol", 2, 6)]


def _suggestion(idx, cards_by_name, suggester_seat, suspect, weapon, room, responses):
    return Suggestion(
        f"s{idx}",
        suggester_seat,
        cards_by_name[suspect],
        cards_by_name[weapon],
        cards_by_name[room],
        tuple(responses),
    )


def test_schema_created_from_scratch():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "store.sqlite3"
        store = PlayerStore(db_path)
        try:
            tables = {
                row[0]
                for row in store._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            assert {
                "games",
                "players_in_game",
                "suggestions",
                "player_profile",
                "settings",
            } <= tables
        finally:
            store.close()


def test_record_full_game_and_rebuild_profile(cards_by_name):
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "store.sqlite3"
        store = PlayerStore(db_path)
        try:
            assert store.is_learning_enabled() is True  # documented default: ON

            store.record_game_start(GAME_ID, "classic_uk", _players())

            s1 = _suggestion(
                1, cards_by_name, 0, "Reverend Green", "Rope", "Kitchen",
                [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
            )
            store.record_suggestion(GAME_ID, 0, s1)

            s2 = _suggestion(
                2, cards_by_name, 1, "Professor Plum", "Wrench", "Study",
                [SuggestionResponse(2, "shown_unseen")],
            )
            store.record_suggestion(GAME_ID, 1, s2)

            solution = (cards_by_name["Miss Scarlett"], cards_by_name["Candlestick"], cards_by_name["Library"])
            store.record_game_end(GAME_ID, solved=True, solved_turn=2, solution=solution)

            store.rebuild_player_profiles()

            profile = store.get_player_profile("Alice")
            assert profile is not None
            assert profile["games_played"] == 1
            assert profile["games_solved"] == 1
            assert profile["avg_solve_turn"] == 2
            assert profile["favorite_suspect"] == "Reverend Green"
            assert profile["favorite_weapon"] == "Rope"
            assert profile["favorite_room"] == "Kitchen"

            bob_profile = store.get_player_profile("Bob")
            assert bob_profile is not None
            assert bob_profile["favorite_suspect"] == "Professor Plum"

            # a player_name never seen should read back cleanly as None
            assert store.get_player_profile("Nobody") is None

            games_row = store._conn.execute(
                "SELECT solved, solved_turn, solution_json FROM games WHERE game_id = ?", (GAME_ID,)
            ).fetchone()
            assert games_row[0] == 1
            assert games_row[1] == 2
            assert games_row[2] is not None

            suggestion_rows = store._conn.execute(
                "SELECT COUNT(*) FROM suggestions WHERE game_id = ?", (GAME_ID,)
            ).fetchone()[0]
            assert suggestion_rows == 2
        finally:
            store.close()


def test_record_suggestion_upserts_same_index(cards_by_name):
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "store.sqlite3"
        store = PlayerStore(db_path)
        try:
            store.record_game_start(GAME_ID, "classic_uk", _players())
            s1 = _suggestion(
                1, cards_by_name, 0, "Reverend Green", "Rope", "Kitchen",
                [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
            )
            store.record_suggestion(GAME_ID, 0, s1)
            # Same index re-recorded (e.g. after an edit) should replace, not duplicate.
            s1_edited = _suggestion(
                1, cards_by_name, 0, "Professor Plum", "Wrench", "Study",
                [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
            )
            store.record_suggestion(GAME_ID, 0, s1_edited)

            rows = store._conn.execute(
                "SELECT suspect FROM suggestions WHERE game_id = ? AND suggestion_index = 0", (GAME_ID,)
            ).fetchall()
            assert len(rows) == 1
            assert rows[0][0] == "Professor Plum"
        finally:
            store.close()


def test_corrupt_db_recovers_to_fresh_db():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "store.sqlite3"
        db_path.write_bytes(b"this is not a sqlite database, just garbage bytes")

        store = PlayerStore(db_path)  # must not raise
        try:
            backup_path = db_path.with_name(db_path.name + ".corrupt.bak")
            assert backup_path.exists()
            assert backup_path.read_bytes().startswith(b"this is not a sqlite database")

            # fresh DB is usable
            tables = {
                row[0]
                for row in store._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            assert "games" in tables
            assert store.get_player_profile("Anyone") is None
        finally:
            store.close()


def test_opt_out_disables_record_methods(cards_by_name):
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "store.sqlite3"
        store = PlayerStore(db_path)
        try:
            store.set_learning_enabled(False)
            assert store.is_learning_enabled() is False

            store.record_game_start(GAME_ID, "classic_uk", _players())
            s1 = _suggestion(
                1, cards_by_name, 0, "Reverend Green", "Rope", "Kitchen",
                [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
            )
            store.record_suggestion(GAME_ID, 0, s1)
            store.record_game_end(GAME_ID, solved=True, solved_turn=1, solution=None)

            game_count = store._conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            suggestion_count = store._conn.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
            assert game_count == 0
            assert suggestion_count == 0

            # re-enabling makes record_* live again
            store.set_learning_enabled(True)
            store.record_game_start(GAME_ID, "classic_uk", _players())
            game_count_after = store._conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            assert game_count_after == 1
        finally:
            store.close()


def test_reset_all_data_wipes_gameplay_but_keeps_settings(cards_by_name):
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "store.sqlite3"
        store = PlayerStore(db_path)
        try:
            store.set_learning_enabled(True)
            store.record_game_start(GAME_ID, "classic_uk", _players())
            s1 = _suggestion(
                1, cards_by_name, 0, "Reverend Green", "Rope", "Kitchen",
                [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
            )
            store.record_suggestion(GAME_ID, 0, s1)
            store.record_game_end(GAME_ID, solved=True, solved_turn=1, solution=None)
            store.rebuild_player_profiles()

            assert store.get_player_profile("Alice") is not None

            store.reset_all_data()

            for table in ("games", "players_in_game", "suggestions", "player_profile"):
                count = store._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                assert count == 0, f"{table} not wiped"

            # settings (the opt-out flag itself) survives a reset
            assert store.is_learning_enabled() is True
        finally:
            store.close()


def test_construction_creates_parent_directory():
    with tempfile.TemporaryDirectory() as d:
        nested = Path(d) / "nested" / "dir" / "store.sqlite3"
        store = PlayerStore(nested)
        try:
            assert nested.parent.is_dir()
        finally:
            store.close()
