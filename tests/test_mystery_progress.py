import pytest

from cluedo.game import GameState
from cluedo.models import ENVELOPE, CardType, Player
from cluedo.mystery_progress import (
    _MAX_AMBIGUOUS_FOR_SOLVE_CHANCE,
    _chance_of_solving_next_turn,
    compute_mystery_progress,
)


def test_fresh_game_low_known_cards_and_valid_chance(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])

    progress = compute_mystery_progress(gs)

    assert progress.total_cards == len(gs.cards)
    assert progress.turns_played == 0
    assert 0 <= progress.known_cards < progress.total_cards
    assert progress.deductions_made == progress.known_cards
    if progress.chance_of_solving_next_turn is not None:
        assert 0.0 <= progress.chance_of_solving_next_turn <= 1.0 + 1e-9


def test_already_solved_game_has_no_chance_value(cfg):
    # Mirrors tests/test_advisor.py's solved-game fixture: a 2-player game
    # where Alice's hand is every card except exactly one suspect/weapon/room,
    # which are therefore forced straight into the envelope.
    all_cards = cfg.all_cards()
    withheld = {
        next(c for c in all_cards if c.type == CardType.SUSPECT),
        next(c for c in all_cards if c.type == CardType.WEAPON),
        next(c for c in all_cards if c.type == CardType.ROOM),
    }
    hand = [c for c in all_cards if c not in withheld]

    gs = GameState(cfg, [Player("Alice", 0, len(hand)), Player("Bob", 1, 0)], user_seat=0)
    gs.set_user_hand(hand)

    assert gs.is_solved()

    progress = compute_mystery_progress(gs)

    assert progress.chance_of_solving_next_turn is None
    assert progress.known_cards == progress.total_cards


def test_one_suggestion_from_solved_has_high_chance(cfg):
    # Set Alice's hand to everything except one suspect (S), one room (R), and
    # two weapons (W1, W2). With Carol holding no cards and Bob holding
    # exactly one card, the engine's capacity-exhaustion rule immediately
    # forces S and R into the envelope (each is the sole remaining candidate
    # for its category's one envelope slot), leaving only the weapon category
    # undecided: either W1 or W2 is the envelope weapon, the other is Bob's.
    #
    # Suggesting (S, W1, R) -- or symmetrically (S, W2, R) -- then resolves
    # the mystery no matter how Bob/Carol respond:
    #   - no_show from both: W1 can no longer be Bob's, so W1 is forced into
    #     the envelope -> solved.
    #   - Bob shows: W1 must be Bob's (S/R are already envelope-owned, so the
    #     "at least one of these three" fact can only be satisfied by W1),
    #     which forces the other weapon, W2, into the envelope -> solved.
    # So both of the advisor's only two candidate suggestions solve the
    # mystery with probability 1.0, and the top-3 mean should be ~1.0.
    suspects = list(cfg.suspects)
    weapons = list(cfg.weapons)
    rooms = list(cfg.rooms)
    assert len(weapons) >= 2 and len(suspects) >= 1 and len(rooms) >= 1

    from cluedo.models import Card

    envelope_suspect = Card(suspects[0], CardType.SUSPECT)
    envelope_room = Card(rooms[0], CardType.ROOM)
    w1 = Card(weapons[0], CardType.WEAPON)
    w2 = Card(weapons[1], CardType.WEAPON)

    alice_hand = (
        [Card(n, CardType.SUSPECT) for n in suspects[1:]]
        + [Card(n, CardType.WEAPON) for n in weapons[2:]]
        + [Card(n, CardType.ROOM) for n in rooms[1:]]
    )

    players = [Player("Alice", 0, len(alice_hand)), Player("Bob", 1, 1), Player("Carol", 2, 0)]
    gs = GameState(cfg, players, user_seat=0)
    gs.set_user_hand(alice_hand)

    assert not gs.is_solved()
    # Sanity-check the setup did what the comment above claims: suspect/room
    # already confirmed to the envelope, weapon still open between W1/W2.
    assert gs.engine.owner_of(envelope_suspect) == ENVELOPE
    assert gs.engine.owner_of(envelope_room) == ENVELOPE
    assert gs.engine.owner_of(w1) is None
    assert gs.engine.owner_of(w2) is None

    progress = compute_mystery_progress(gs)

    assert progress.chance_of_solving_next_turn is not None
    assert progress.chance_of_solving_next_turn == pytest.approx(1.0, abs=1e-6)


def test_many_ambiguous_cards_returns_none_chance_instead_of_computing(cfg, cards_by_name):
    # 6 players over a 21-card deck (3-card envelope) leaves 18 cards split
    # 3 each -- the user's own 3 known cards still leave 18 ambiguous, well
    # past _MAX_AMBIGUOUS_FOR_SOLVE_CHANCE (15). Computing an exact chance
    # here would mean up to 3 candidates x 6 responders of full-history
    # whatif replays for one dashboard readout, mirroring the exact cost
    # cliff advisor.py already guards against -- so this should short-circuit
    # to None rather than pay that cost (or silently return a bogus 0.0).
    players = [Player(f"P{i}", i, 3) for i in range(6)]
    gs = GameState(cfg, players, user_seat=0)
    hand = [c for c in cfg.all_cards()][:3]
    gs.set_user_hand(hand)

    ci = gs.engine.counting_input()
    assert len(ci.ambiguous) > _MAX_AMBIGUOUS_FOR_SOLVE_CHANCE

    assert _chance_of_solving_next_turn(gs) is None
    progress = compute_mystery_progress(gs)
    assert progress.chance_of_solving_next_turn is None


def test_unexpected_exception_is_not_silently_swallowed(cfg, monkeypatch):
    # _p_candidate_solves used to wrap its calls in a bare `except Exception`,
    # which would silently turn any real bug (e.g. a programming error deep in
    # probability_of_response_outcome) into a quiet "contributes 0" instead of
    # surfacing it. Now only the two specific, expected exceptions
    # (TooManyAmbiguousCardsError, ContradictionError) are caught -- anything
    # else must propagate.
    import cluedo.mystery_progress as mp

    def _boom(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(mp, "probability_of_response_outcome", _boom)

    from cluedo.models import Card

    suspect, weapon, room = (
        Card(cfg.suspects[0], CardType.SUSPECT),
        Card(cfg.weapons[0], CardType.WEAPON),
        Card(cfg.rooms[0], CardType.ROOM),
    )
    hand = [c for c in cfg.all_cards() if c not in (suspect, weapon, room)][:6]

    players = [Player("Alice", 0, len(hand)), Player("Bob", 1, 6), Player("Carol", 2, 6)]
    gs = GameState(cfg, players, user_seat=0)
    gs.set_user_hand(hand)

    with pytest.raises(ValueError):
        mp._p_candidate_solves(gs, suspect, weapon, room)


def test_mystery_progress_is_cached_per_mutation(cfg, cards_by_name, three_players, monkeypatch):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])

    first = compute_mystery_progress(gs)

    # Same (GameState, mutation_seq) must not recompute -- the chance
    # estimate is the most expensive derived figure in the app.
    import cluedo.mystery_progress as mp

    def _boom(_gs):
        raise AssertionError("cached call should not recompute solve chance")

    monkeypatch.setattr(mp, "_chance_of_solving_next_turn", _boom)
    assert compute_mystery_progress(gs) is first
    monkeypatch.undo()

    # Any mutation invalidates: recomputed against the new state.
    from cluedo.models import SuggestionResponse

    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    updated = compute_mystery_progress(gs)
    assert updated is not first
    assert updated.turns_played == 1
