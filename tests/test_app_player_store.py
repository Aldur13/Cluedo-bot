"""Tests for App's player_store lifecycle plumbing (cluedo/gui/app.py):
_start_tracking_game / _sync_player_store, called from _on_setup_confirmed,
load(), _maybe_offer_recovery(), and after_mutation().

Bypasses App.__init__ (via App.__new__) rather than constructing a real App
-- __init__ creates a real Tk root and may pop a real "recover autosave?"
messagebox dialog, neither of which belongs in an automated test. Only the
handful of attributes _start_tracking_game/_sync_player_store actually read
(game_state, player_store, _game_id, _game_end_recorded) are set directly,
and a fake in-memory store stands in for PlayerStore so each hook's call
count can be asserted precisely.
"""
from cluedo.game import GameState
from cluedo.gui.app import App
from cluedo.models import SuggestionResponse


class _FakeStore:
    def __init__(self):
        self.game_starts = []
        self.suggestions = []
        self.game_ends = []

    def record_game_start(self, game_id, edition, players):
        self.game_starts.append((game_id, edition, tuple(players)))

    def record_suggestion(self, game_id, index, suggestion):
        self.suggestions.append((game_id, index, suggestion))

    def record_game_end(self, game_id, solved, solved_turn, solution):
        self.game_ends.append((game_id, solved, solved_turn, solution))


def _bare_app(game_state):
    app = App.__new__(App)
    app.game_state = game_state
    app.player_store = _FakeStore()
    app._game_id = None
    app._game_end_recorded = False
    app.refresh_main_screen = lambda: None
    return app


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_start_tracking_game_records_start_and_assigns_id(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _bare_app(gs)

    app._start_tracking_game()

    assert app._game_id is not None
    assert len(app.player_store.game_starts) == 1
    game_id, edition, players = app.player_store.game_starts[0]
    assert game_id == app._game_id
    assert edition == cfg.edition
    assert players == tuple(gs.players)


def test_sync_player_store_records_each_suggestion_by_index(cfg, cards_by_name, three_players, tmp_path, monkeypatch):
    # after_mutation() also calls _autosave(), which writes to
    # default_autosave_path() -- redirect it into tmp_path so this test never
    # touches the real user's AppData autosave file.
    monkeypatch.setattr("cluedo.gui.app.default_autosave_path", lambda: tmp_path / "autosave.json")

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _bare_app(gs)
    app._start_tracking_game()

    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    app.after_mutation()

    assert [idx for (_gid, idx, _s) in app.player_store.suggestions] == [0]

    gs.record_suggestion(
        2, cards_by_name["Mrs. Peacock"], cards_by_name["Wrench"], cards_by_name["Ballroom"],
        [SuggestionResponse(0, "no_show"), SuggestionResponse(1, "no_show")],
    )
    app.after_mutation()

    # Re-syncs the *whole* current history each time (upsert-by-index,
    # matching PlayerStore's own "treat it like autosave" design) -- so
    # suggestion 0 is recorded again alongside the new suggestion 1.
    assert [idx for (_gid, idx, _s) in app.player_store.suggestions] == [0, 0, 1]


def test_game_end_recorded_exactly_once(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr("cluedo.gui.app.default_autosave_path", lambda: tmp_path / "autosave.json")

    from cluedo.models import Card, CardType, Player

    all_cards = cfg.all_cards()
    withheld = {
        next(c for c in all_cards if c.type == CardType.SUSPECT),
        next(c for c in all_cards if c.type == CardType.WEAPON),
        next(c for c in all_cards if c.type == CardType.ROOM),
    }
    hand = [c for c in all_cards if c not in withheld]

    gs = GameState(cfg, [Player("Alice", 0, len(hand)), Player("Bob", 1, 0)], user_seat=0)
    app = _bare_app(gs)
    app._start_tracking_game()  # hand not yet set: not solved yet, no game_end

    gs.set_user_hand(hand)  # this alone solves it (mirrors test_advisor.py's fixture)
    assert gs.is_solved()

    app.after_mutation()
    app.after_mutation()  # calling again post-solve must not double-record

    assert len(app.player_store.game_ends) == 1
    game_id, solved, solved_turn, solution = app.player_store.game_ends[0]
    assert game_id == app._game_id
    assert solved is True
    assert solution == gs.solution()


def test_start_tracking_game_is_a_noop_without_a_game_state():
    app = App.__new__(App)
    app.game_state = None
    app.player_store = _FakeStore()
    app._game_id = None
    app._game_end_recorded = False

    app._start_tracking_game()

    assert app._game_id is None
    assert app.player_store.game_starts == []
