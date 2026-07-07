from cluedo.game import GameState
from cluedo.gui.snapshot_cache import SnapshotCache
from cluedo.models import SuggestionResponse


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_cache_reuses_snapshots_when_nothing_changed(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    cache = SnapshotCache()
    first = cache.get(gs)
    second = cache.get(gs)
    assert first is second


def test_cache_recomputes_after_mutation(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    cache = SnapshotCache()
    before = cache.get(gs)

    gs.record_suggestion(
        0,
        cards_by_name["Professor Plum"],
        cards_by_name["Wrench"],
        cards_by_name["Study"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )

    after = cache.get(gs)
    assert after is not before
    assert len(after) == len(before) + 1


def test_cache_does_not_return_stale_snapshots_for_a_different_game_state(
    cfg, cards_by_name, three_players
):
    gs1 = _basic_game(cfg, cards_by_name, three_players)
    cache = SnapshotCache()
    first = cache.get(gs1)

    gs2 = _basic_game(cfg, cards_by_name, three_players)
    second = cache.get(gs2)

    # Both are freshly constructed (mutation_seq == 0 for each), but they are
    # different GameState instances -- the cache must not collide on seq alone.
    assert second is not first
    assert second[-1].game_state.history == gs2.history
