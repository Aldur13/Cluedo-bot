"""Tests for cluedo/change_tracking.py: per-card last-changed-turn tracking,
built by diffing detective_sheet() across history.build_replay_snapshots()
prefixes. See tests/test_history.py for the replay-snapshot machinery this
builds on, and tests/test_full_game.py for the truthful-game generation
pattern reused by the benchmark test below.
"""
import random
import time

import pytest

from cluedo.change_tracking import compute_last_changed_turns
from cluedo.config import load_bundled_edition
from cluedo.engine import ContradictionError
from cluedo.game import GameState
from cluedo.history import build_replay_snapshots
from cluedo.models import ENVELOPE, Player, SuggestionResponse, seat_id


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_no_suggestions_yet_everything_is_turn_zero(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    last_changed = compute_last_changed_turns(gs)
    assert set(last_changed.keys()) == set(gs.cards)
    assert all(turn == 0 for turn in last_changed.values())


def test_scripted_sequence_matches_hand_computed_turns(cfg, cards_by_name, three_players):
    """Three suggestions, each all-no_show except for the elimination effects
    they trigger, chosen so every transition is exactly predictable:

    Turn 1 (Green/Rope/Kitchen no_show from seat_1 and seat_2): each of those
    three cards is excluded from every player's hand, so the solver confirms
    them as envelope cards outright. That in turn removes "envelope" from the
    possible-owner set of every *other*, not-yet-mentioned card in the same
    category (only one envelope card per category) -- so Plum/Peacock,
    Wrench/Revolver, and every remaining room (Study/Ballroom/Library/
    Conservatory/Dining Room/Billiard Room/Lounge/Hall) also change at turn 1,
    even though they weren't part of this suggestion.

    Turn 2 (Plum/Wrench/Study no_show from seat_2 and seat_0): narrows those
    three from {seat_1, seat_2} to just {seat_1} -- confirmed to seat_1.
    Peacock/Revolver/Ballroom are untouched by this suggestion, so they don't
    change here.

    Turn 3 (Peacock/Revolver/Ballroom no_show from seat_0 and seat_1): the
    remaining unconfirmed trio narrows from {seat_1, seat_2} to {seat_2} --
    confirmed to seat_2.
    """
    gs = _basic_game(cfg, cards_by_name, three_players)

    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    gs.record_suggestion(
        2, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(0, "no_show"), SuggestionResponse(1, "no_show")],
    )

    # Sanity check the deductions this test's turn predictions depend on.
    sheet = gs.detective_sheet()
    assert sheet[cards_by_name["Reverend Green"]] == {"status": "confirmed", "owner": ENVELOPE, "possible": {ENVELOPE}}
    assert sheet[cards_by_name["Professor Plum"]]["owner"] == "seat_1"
    assert sheet[cards_by_name["Mrs. Peacock"]]["owner"] == "seat_2"

    last_changed = compute_last_changed_turns(gs)

    hand_cards = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    for name in hand_cards:
        assert last_changed[cards_by_name[name]] == 0, name

    for name in ["Reverend Green", "Rope", "Kitchen"]:
        assert last_changed[cards_by_name[name]] == 1, name

    for name in ["Library", "Conservatory", "Dining Room", "Billiard Room", "Lounge", "Hall"]:
        assert last_changed[cards_by_name[name]] == 1, name

    for name in ["Professor Plum", "Wrench", "Study"]:
        assert last_changed[cards_by_name[name]] == 2, name

    for name in ["Mrs. Peacock", "Revolver", "Ballroom"]:
        assert last_changed[cards_by_name[name]] == 3, name


def test_matches_independent_diff_of_replay_snapshots(cfg, cards_by_name, three_players):
    """Cross-check against a from-scratch diff computed directly from
    build_replay_snapshots()/detective_sheet(), independent of the
    compute_last_changed_turns implementation, over a longer scripted game
    with confirmations, ambiguous narrowings, and one shown_to_me reveal."""
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(2, "shown_unseen")],
    )
    gs.record_suggestion(
        2, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(0, "no_show"), SuggestionResponse(1, "no_show")],
    )

    snapshots = build_replay_snapshots(gs)
    expected = {card: 0 for card in gs.cards}
    previous_sheet = snapshots[0].game_state.detective_sheet()
    for snap in snapshots[1:]:
        sheet = snap.game_state.detective_sheet()
        for card in gs.cards:
            if sheet[card]["status"] != previous_sheet[card]["status"] or sheet[card]["possible"] != previous_sheet[card]["possible"]:
                expected[card] = snap.step_index
        previous_sheet = sheet

    assert compute_last_changed_turns(gs) == expected
    # The diff loop above must actually have found some real changes, or this
    # cross-check would trivially pass with everything at 0.
    assert any(turn > 0 for turn in expected.values())


def test_undo_shortens_history_and_recomputation_reflects_it(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    before_undo = compute_last_changed_turns(gs)
    assert before_undo[cards_by_name["Rope"]] == 1

    gs.undo_last_suggestion()
    after_undo = compute_last_changed_turns(gs)
    assert all(turn == 0 for turn in after_undo.values())


# --------------------------------------------------------------- benchmark

def _deal(rng, cfg, players):
    cards = list(cfg.all_cards())
    rng.shuffle(cards)
    by_type = {}
    for c in cards:
        by_type.setdefault(c.type, []).append(c)

    owner_of = {}
    remaining = []
    for group in by_type.values():
        owner_of[group[0]] = ENVELOPE
        remaining.extend(group[1:])
    rng.shuffle(remaining)

    idx = 0
    hands = {}
    for p in players:
        hands[p.owner_id] = remaining[idx: idx + p.hand_size]
        idx += p.hand_size
        for c in hands[p.owner_id]:
            owner_of[c] = p.owner_id
    return owner_of, hands


def _default_hand_sizes(total, n):
    base, extra = divmod(total, n)
    return [base + (1 if i < extra else 0) for i in range(n)]


def test_compute_last_changed_turns_stays_fast_over_an_80_turn_game():
    """Basic performance guard, not a strict benchmark: an ~80-turn synthetic
    truthful game (built the same way as tests/test_full_game.py) should
    still let compute_last_changed_turns finish in well under a minute, even
    though it internally replays the whole history from scratch once per
    history prefix (the engine's constraint solve is the dominant cost, not
    this module's diffing, so the bound here is generous)."""
    rng = random.Random(4242)
    cfg = load_bundled_edition("classic_uk")
    n_players = 3
    max_turns = 80
    total_non_envelope = len(cfg.suspects) + len(cfg.weapons) + len(cfg.rooms) - 3
    sizes = _default_hand_sizes(total_non_envelope, n_players)
    players = [Player(f"P{i}", i, sizes[i]) for i in range(n_players)]
    owner_of, hands = _deal(rng, cfg, players)

    gs = GameState(cfg, players, user_seat=0)
    gs.set_user_hand(hands["seat_0"])

    all_cards = cfg.all_cards()
    suspects = [c for c in all_cards if c.type.value == "suspect"]
    weapons = [c for c in all_cards if c.type.value == "weapon"]
    rooms = [c for c in all_cards if c.type.value == "room"]

    for i in range(max_turns):
        suggester_seat = i % n_players
        suspect = rng.choice(suspects)
        weapon = rng.choice(weapons)
        room = rng.choice(rooms)
        order = gs.responders_in_order(suggester_seat)

        responses = []
        for seat in order:
            owner = seat_id(seat)
            held = [c for c in (suspect, weapon, room) if owner_of.get(c) == owner]
            if held:
                if seat == 0 or suggester_seat == 0:
                    responses.append(SuggestionResponse(seat, "shown_to_me", rng.choice(held)))
                else:
                    responses.append(SuggestionResponse(seat, "shown_unseen"))
                break
            responses.append(SuggestionResponse(seat, "no_show"))

        try:
            gs.record_suggestion(suggester_seat, suspect, weapon, room, responses)
        except ContradictionError:
            break

        if gs.is_solved():
            break

    start = time.perf_counter()
    last_changed = compute_last_changed_turns(gs)
    elapsed = time.perf_counter() - start

    assert set(last_changed.keys()) == set(gs.cards)
    assert all(0 <= turn <= len(gs.history) for turn in last_changed.values())
    assert elapsed < 30.0, f"compute_last_changed_turns took {elapsed:.2f}s over {len(gs.history)} turns"
