"""Tests for cluedo/timeseries.py: pure time-series data built on top of
history.build_replay_snapshots(). See tests/test_change_tracking.py for the
sibling module this mirrors (same scripted-sequence + 80-turn-benchmark
style), and tests/test_full_game.py for the truthful-game generation pattern
reused by the benchmark test below.
"""
import random
import time
from types import SimpleNamespace

import pytest

from cluedo.config import load_bundled_edition
from cluedo.engine import ContradictionError
from cluedo.game import GameState
from cluedo.history import build_replay_snapshots
from cluedo.models import ENVELOPE, Player, SuggestionResponse, seat_id
from cluedo.timeseries import (
    envelope_probability_over_time,
    info_gained_per_turn,
    solver_progress_over_time,
    worlds_over_time,
)


def _fake_snapshot(valid_worlds):
    """Minimal stand-in for a ReplaySnapshot, exposing just the
    `.game_state.last_solver_stats.valid_worlds_last_counted` attribute path
    `info_gained_per_turn`/`worlds_over_time` actually read. Used to test the
    arithmetic in isolation from the real solver: as noted below, a real
    GameState essentially never surfaces a non-None
    `valid_worlds_last_counted` today because of a separate, pre-existing
    aliasing bug in `cluedo/engine.py`'s `recompute()` (the world-search path
    writes to a stale `SolverStats` instance that gets discarded before the
    caller ever sees it) -- out of scope to fix here (engine.py is a
    standing-invariant file for this module), but it means real-game-based
    tests alone can't exercise the "both known" branch of
    `info_gained_per_turn`."""
    stats = SimpleNamespace(valid_worlds_last_counted=valid_worlds)
    game_state = SimpleNamespace(last_solver_stats=stats)
    return SimpleNamespace(game_state=game_state)


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


# --------------------------------------------------------------- scripted sequence

def _scripted_game(cfg, cards_by_name, three_players):
    """Same three-suggestion scripted sequence used in
    tests/test_change_tracking.py, with a known effect at each turn:

    Turn 1: Green/Rope/Kitchen no_show from seat_1 and seat_2 -> all three
    confirmed as envelope cards outright (eliminates a large chunk of worlds).
    Turn 2: Plum/Wrench/Study no_show from seat_2 and seat_0 -> narrows those
    three from {seat_1, seat_2} to {seat_1} (a smaller, but nonzero, world
    reduction).
    Turn 3: the user (seat_0) suggests Peacock/Revolver/Ballroom and seat_1
    directly shows Peacock (a shown_to_me reveal) -> confirms Peacock to
    seat_1 immediately, a clean example of a suggestion that must produce a
    strictly positive info gain. (Note: seat_0's own hand is already fixed
    from `set_user_hand`, so Peacock -- which isn't in that hand -- can only
    ever be shown *to* the user, never *by* them; the reveal must come from
    seat_1 or seat_2.)
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
        0, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(1, "shown_to_me", cards_by_name["Mrs. Peacock"]), SuggestionResponse(2, "no_show")],
    )
    return gs


def test_worlds_over_time_length_and_pass_through(cfg, cards_by_name, three_players):
    gs = _scripted_game(cfg, cards_by_name, three_players)
    snapshots = build_replay_snapshots(gs)
    assert len(snapshots) == 4  # prefixes of length 0..3

    worlds = worlds_over_time(snapshots)
    assert len(worlds) == 4
    # worlds_over_time is a pure pass-through of
    # last_solver_stats.valid_worlds_last_counted, so it must match the raw
    # attribute exactly for every snapshot (not necessarily non-None -- see
    # the module docstring on that field being Optional).
    assert worlds == [
        snap.game_state.last_solver_stats.valid_worlds_last_counted for snap in snapshots
    ]
    # Known (non-None) values must never suggest worlds *increasing* across a
    # game that only ever adds information.
    known = [w for w in worlds if w is not None]
    for before, after in zip(known, known[1:]):
        assert after <= before


def test_info_gained_per_turn_arithmetic_with_known_world_counts():
    """Exercises the "both worlds_before and worlds_after known" branch
    directly via stub snapshots, since a real GameState practically never
    surfaces a non-None valid_worlds_last_counted today (see the
    aliasing-bug note on _fake_snapshot above) -- this keeps the arithmetic
    itself under test independent of that upstream limitation."""
    snapshots = [_fake_snapshot(100), _fake_snapshot(100), _fake_snapshot(25), _fake_snapshot(0)]
    gains = info_gained_per_turn(snapshots)
    assert gains == [0.0, 0.75, 1.0]


def test_info_gained_per_turn_falls_back_to_zero_when_worlds_unknown():
    snapshots = [_fake_snapshot(None), _fake_snapshot(50), _fake_snapshot(None), _fake_snapshot(None)]
    gains = info_gained_per_turn(snapshots)
    # None -> 50: before unknown, can't compute a ratio -> 0.0.
    # 50 -> None: after unknown -> 0.0.
    # None -> None: both unknown -> 0.0.
    assert gains == [0.0, 0.0, 0.0]


def test_info_gained_per_turn_handles_zero_worlds_before_without_dividing_by_zero():
    snapshots = [_fake_snapshot(0), _fake_snapshot(0)]
    assert info_gained_per_turn(snapshots) == [0.0]


def test_solver_progress_over_time_non_decreasing_and_matches_confirmed(cfg, cards_by_name, three_players):
    gs = _scripted_game(cfg, cards_by_name, three_players)
    snapshots = build_replay_snapshots(gs)
    progress = solver_progress_over_time(snapshots)
    assert len(progress) == len(snapshots)
    for before, after in zip(progress, progress[1:]):
        assert after >= before
    # Last entry must match the live game's own confirmed count.
    assert progress[-1] == len(gs.engine.confirmed)
    # Turn 1 confirms Green/Rope/Kitchen as envelope cards outright, so
    # progress must have grown by the time we reach snapshot 1.
    assert progress[1] > progress[0]


def test_info_gained_per_turn_length_and_bounds(cfg, cards_by_name, three_players):
    gs = _scripted_game(cfg, cards_by_name, three_players)
    snapshots = build_replay_snapshots(gs)
    gains = info_gained_per_turn(snapshots)
    # One value per turn transition: len(snapshots) - 1, not len(snapshots).
    assert len(gains) == len(snapshots) - 1 == 3
    for g in gains:
        assert 0.0 <= g <= 1.0
    # This particular scripted game never gets a non-None
    # valid_worlds_last_counted out of the real engine (see
    # test_info_gained_per_turn_arithmetic_with_known_world_counts's docstring
    # for why), so every transition here legitimately falls back to the
    # documented 0.0 "unknown" default rather than a real elimination ratio.
    assert gains == [0.0, 0.0, 0.0]


def test_envelope_probability_over_time_reaches_certainty_for_confirmed_envelope_card(
    cfg, cards_by_name, three_players
):
    gs = _scripted_game(cfg, cards_by_name, three_players)
    snapshots = build_replay_snapshots(gs)
    rope = cards_by_name["Rope"]

    probs = envelope_probability_over_time(snapshots, rope)
    assert len(probs) == len(snapshots)
    # Snapshot 0 (only the initial hand known) has 15 unconfirmed cards,
    # above card_probabilities()'s default max_ambiguous=14 gate -- so this
    # is the documented None fallback for "not computed", not a real 0..1
    # probability.
    assert probs[0] is None
    assert probs[-1] == pytest.approx(1.0)
    # Once confirmed as an envelope card (end of turn 1), stays confirmed for
    # every subsequent snapshot too.
    for p in probs[1:]:
        assert p == pytest.approx(1.0)


def test_envelope_probability_over_time_never_crashes_on_a_hand_card(cfg, cards_by_name, three_players):
    """A card in the user's own starting hand is always confirmed to the
    user, never to the envelope -- probability should be 0.0 throughout,
    exercising the confirmed-card branch of full_probabilities()."""
    gs = _scripted_game(cfg, cards_by_name, three_players)
    snapshots = build_replay_snapshots(gs)
    scarlett = cards_by_name["Miss Scarlett"]

    probs = envelope_probability_over_time(snapshots, scarlett)
    assert len(probs) == len(snapshots)
    # Snapshot 0 hits the same too-many-ambiguous-cards gate as the Rope test
    # above -> documented None fallback.
    assert probs[0] is None
    for p in probs[1:]:
        assert p == pytest.approx(0.0)


def test_single_snapshot_list_is_handled(cfg, cards_by_name, three_players):
    """A brand-new game (no suggestions yet) still has one snapshot (the
    zero-suggestion prefix); every function must handle a length-1 list
    without crashing, and info_gained_per_turn must return an empty list
    (there's no turn transition yet)."""
    gs = _basic_game(cfg, cards_by_name, three_players)
    snapshots = build_replay_snapshots(gs)
    assert len(snapshots) == 1

    assert len(worlds_over_time(snapshots)) == 1
    assert len(solver_progress_over_time(snapshots)) == 1
    assert info_gained_per_turn(snapshots) == []
    probs = envelope_probability_over_time(snapshots, cards_by_name["Rope"])
    assert len(probs) == 1


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


def test_timeseries_functions_stay_fast_over_a_40_turn_game():
    """Basic performance guard, not a strict benchmark: an ~40-turn synthetic
    truthful game (built the same way as tests/test_full_game.py and
    tests/test_change_tracking.py's 80-turn benchmark) should let all four
    timeseries functions finish comfortably in well under a minute, even
    though building the snapshot list itself replays the whole history from
    scratch once per prefix -- the engine's constraint solve dominates the
    cost, not this module's own O(1)-per-snapshot work, so the bound here is
    generous, matching the precedent test_change_tracking.py already set."""
    rng = random.Random(99)
    cfg = load_bundled_edition("classic_uk")
    n_players = 3
    max_turns = 40
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
    snapshots = build_replay_snapshots(gs)
    worlds = worlds_over_time(snapshots)
    progress = solver_progress_over_time(snapshots)
    gains = info_gained_per_turn(snapshots)
    probs = envelope_probability_over_time(snapshots, cards_by_name_for(cfg)["Miss Scarlett"])
    elapsed = time.perf_counter() - start

    assert len(worlds) == len(snapshots)
    assert len(progress) == len(snapshots)
    assert len(gains) == len(snapshots) - 1
    assert len(probs) == len(snapshots)
    assert all(0.0 <= g <= 1.0 for g in gains)
    assert elapsed < 30.0, f"timeseries functions took {elapsed:.2f}s over {len(gs.history)} turns"


def cards_by_name_for(cfg):
    return {c.name: c for c in cfg.all_cards()}
